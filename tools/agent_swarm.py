#!/usr/bin/env python3
"""Concurrent repository audit workers with shared findings and final arbitration."""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"

def files():
    try:
        names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
        return [ROOT / n for n in names if n and (ROOT / n).is_file()]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]

def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.stat().st_size < 1000000 else ""
    except OSError:
        return ""

def integrity(fs):
    names = [str(p.relative_to(ROOT)) for p in fs]
    missing = [n for n in [".github/workflows/agent-swarm.yml", "tools/agent_swarm.py"] if n not in names]
    bad = [str(p.relative_to(ROOT)) for p in fs if re.search(r"(?i)\brender\.com\b|\bonrender\.com\b|\bRender\s+service\b", read(p))]
    return finding("repository-integrity", "BLOCK" if missing or bad else "PASS", "Required files and prohibited hosting references.", missing + bad)

def tests(fs):
    tf = [p for p in fs if str(p.relative_to(ROOT)).startswith("tests/") and p.suffix == ".py"]
    text = "\n".join(read(p) for p in tf)
    missing = [x for x in ["historical_failure_gate", "double_chance_failure_gate", "failure_incident_ledger"] if x not in text]
    return finding("test-coverage", "WARN" if not tf or missing else "PASS", "Regression-test presence for core gates and ledger.", [f"Python test files: {len(tf)}"] + ["Missing marker: " + x for x in missing])

def gates(fs):
    targets = {"historical_failure_gate.py", "double_chance_failure_gate.py", "market_arbiter.py", "umios_arbiter.py", "failure_incident_ledger.py"}
    rs = [p for p in fs if p.name in targets]
    text = "\n".join(read(p) for p in rs)
    checks = {"NO_BET marker": "NO_BET" in text, "exception/fail-closed handling": bool(re.search(r"except\s+Exception|fail.closed|fail_closed", text, re.I)), "selection checks": "selection" in text.lower()}
    missing = [k for k,v in checks.items() if not v]
    return finding("fail-closed-audit", "BLOCK" if missing else "PASS", "Static audit of fail-closed certification controls; not a substitute for tests.", ["Passed: " + k for k,v in checks.items() if v] + ["Missing: " + x for x in missing])

def storage(fs):
    text = "\n".join(read(p) for p in fs if p.suffix in {".py", ".md", ".txt", ".yml", ".yaml"})
    checks = {"DATABASE_URL adapter": "DATABASE_URL" in text, "psycopg dependency": "psycopg" in text, "persistence caveat": "Vercel" in text and ("durable" in text.lower() or "persistent" in text.lower())}
    missing = [k for k,v in checks.items() if not v]
    return finding("durable-storage", "WARN" if missing else "PASS", "Checks database adapter and documentation; cannot inspect Vercel secrets or prove live database I/O.", ["Passed: " + k for k,v in checks.items() if v] + ["Missing: " + x for x in missing] + ["Live database configuration remains unverified."])

def secrets(fs):
    patterns = [re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9_]{20,}"), re.compile(r"""(?i)postgres(?:ql)?://[^\s:'"]+:[^\s@'"]+@"""), re.compile(r"(?i)\bsk-[A-Za-z0-9]{20,}")]
    hits = [str(p.relative_to(ROOT)) for p in fs if any(pat.search(read(p)) for pat in patterns)]
    return finding("secret-hygiene", "BLOCK" if hits else "PASS", "Heuristic scan for common hard-coded credentials.", hits + ["Heuristic only; use GitHub secret scanning as well."])

def workflow_security(fs):
    text = read(ROOT / ".github/workflows/agent-swarm.yml")
    checks = {"read-only contents permission": bool(re.search(r"contents:\s*read", text)), "timeout bound": bool(re.search(r"timeout-minutes:\s*\d+", text)), "concurrency guard": "concurrency:" in text, "no database credential embedded": "DATABASE_URL:" not in text}
    missing = [k for k,v in checks.items() if not v]
    return finding("workflow-security", "BLOCK" if missing else "PASS", "Basic workflow privilege and runaway-run checks.", ["Passed: " + k for k,v in checks.items() if v] + ["Missing: " + x for x in missing])

def finding(agent, status, summary, evidence):
    return {"agent": agent, "status": status, "summary": summary, "evidence": evidence, "observed_at": datetime.now(timezone.utc).isoformat()}

def main():
    OUT.mkdir(exist_ok=True)
    fs = files()
    agents = [integrity, tests, gates, storage, secrets, workflow_security]
    results = []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = {pool.submit(agent, fs): agent.__name__ for agent in agents}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append(finding(futures[fut], "BLOCK", "Agent crashed; final arbiter fails closed.", [type(exc).__name__ + ": " + str(exc)]))
    results.sort(key=lambda x: x["agent"])
    blockers = [x for x in results if x["status"] == "BLOCK"]
    warnings = [x for x in results if x["status"] == "WARN"]
    overall = "BLOCK" if blockers else ("WARN" if warnings else "PASS")
    payload = {"schema_version": 1, "commit": os.getenv("GITHUB_SHA", "local"), "event": os.getenv("GITHUB_EVENT_NAME", "local"), "generated_at": datetime.now(timezone.utc).isoformat(), "overall": overall, "arbiter": {"blockers": len(blockers), "warnings": len(warnings), "rule": "Any BLOCK blocks certification; WARN requires human review."}, "agents": results}
    (OUT / "agent-findings.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Elite MatchMaster Agent Swarm", "", "- Final arbiter: " + overall, "- Concurrent agents: " + str(len(results)), "- Blockers: " + str(len(blockers)), "- Warnings: " + str(len(warnings)), "", "Agents are concurrent deterministic audit workers, not millions of autonomous AI models. Results are shared through a common report and final arbiter.", "", "## Findings", ""]
    for item in results:
        lines += ["### " + item["agent"] + " — " + item["status"], "", item["summary"], ""]
        lines += ["- " + e for e in item["evidence"]]
        lines.append("")
    lines += ["## Limits", "", "- Scheduled every six hours and manually triggerable in GitHub Actions.", "- JSON and Markdown findings are published as workflow artifacts.", "- This workflow does not place bets, change predictions, provision databases, or prove production health.", ""]
    (OUT / "agent-swarm-report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"overall": overall, "agents": len(results), "blockers": len(blockers), "warnings": len(warnings)}))

if __name__ == "__main__":
    main()
