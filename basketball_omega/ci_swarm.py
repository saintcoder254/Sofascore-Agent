"""Basketball OMEGA CI swarm: deterministic, fail-closed quality bots."""
from dataclasses import dataclass
from pathlib import Path
import ast
import importlib
import sys
import unittest


@dataclass(frozen=True)
class BotResult:
    name: str
    passed: bool
    findings: tuple[str, ...] = ()


class StaticBot:
    name = "static"

    def run(self):
        findings = []
        for path in Path("basketball_omega").rglob("*.py"):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError as exc:
                findings.append(f"{path}:syntax:{exc}")
                continue
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                elif isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                for module in modules:
                    if module.startswith(("umios", "football")):
                        findings.append(f"{path}:forbidden-import:{module}")
        return BotResult(self.name, not findings, tuple(findings))


class BoundaryBot:
    name = "boundary"

    def run(self):
        findings = []
        for name in ("basketball_omega.router", "basketball_omega.service",
                     "basketball_omega.snapshot_store"):
            try:
                importlib.import_module(name)
            except Exception as exc:
                findings.append(f"{name}:import:{type(exc).__name__}:{exc}")
        return BotResult(self.name, not findings, tuple(findings))


class ContractBot:
    name = "contracts"

    def run(self):
        findings = []
        try:
            from basketball_omega.contracts import BasketballContext
            c = BasketballContext(home="H", away="A")
            if (c.home, c.away) != ("H", "A"):
                findings.append("context-construction-failed")
        except Exception as exc:
            findings.append(f"contract:{type(exc).__name__}:{exc}")
        return BotResult(self.name, not findings, tuple(findings))


class TestBot:
    name = "tests"

    def run(self):
        suite = unittest.TestLoader().discover("tests", pattern="test_basketball_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        findings = tuple(f"{e[0]}: {e[1]}" for e in result.errors + result.failures)
        return BotResult(self.name, result.wasSuccessful(), findings)


class SwarmGate:
    def __init__(self):
        self.bots = [StaticBot(), BoundaryBot(), ContractBot(), TestBot()]

    def run(self):
        results = [bot.run() for bot in self.bots]
        failed = [r for r in results if not r.passed]
        for r in results:
            print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name}")
            for finding in r.findings:
                print(f"  - {finding}")
        print("SWARM_GATE=" + ("FAIL" if failed else "PASS"))
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(SwarmGate().run())
