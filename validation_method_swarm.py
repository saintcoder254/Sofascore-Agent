"""Independent validation-method bots for Elite MatchMaster OMEGA.

These bots are diagnostic validators, not autonomous betting agents. They publish
structured messages to a shared in-memory run ledger and cannot certify a bet.
Historical bootstrap and Monte Carlo convergence require actual supplied samples;
missing samples are reported as UNAVAILABLE, never fabricated.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Iterable

from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict


router = APIRouter(prefix="/validation/swarm", tags=["validation-swarm"])


@dataclass
class AgentMessage:
    run_id: str
    message_id: str
    sender: str
    recipient: str
    topic: str
    status: str
    payload: dict[str, Any]
    created_at: float


class AgentBus:
    """Small, deterministic pub/sub ledger for one validation run."""
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.messages: list[AgentMessage] = []

    def publish(self, sender: str, topic: str, status: str, payload: dict[str, Any]) -> AgentMessage:
        message = AgentMessage(self.run_id, str(uuid.uuid4()), sender, "*", topic, status, payload, time.time())
        self.messages.append(message)
        return message

    def send(self, sender: str, recipient: str, topic: str, status: str, payload: dict[str, Any]) -> AgentMessage:
        message = AgentMessage(self.run_id, str(uuid.uuid4()), sender, recipient, topic, status, payload, time.time())
        self.messages.append(message)
        return message

    def inbox(self, recipient: str, topic: str | None = None) -> list[AgentMessage]:
        return [m for m in self.messages if m.recipient in ("*", recipient) and (topic is None or m.topic == topic)]


def _clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, float(x)))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one observation")
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _poisson_pmf(k: int, lam: float) -> float:
    if k < 0 or lam < 0:
        return 0.0
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def poisson_market_probabilities(home_xg: float, away_xg: float, max_goals: int = 12) -> dict[str, float]:
    """Analytical independent-Poisson 1X2 and O/U 2.5 probabilities."""
    if not (0 <= home_xg <= 8 and 0 <= away_xg <= 8):
        raise ValueError("expected-goal rates must be between 0 and 8")
    h = [_poisson_pmf(i, home_xg) for i in range(max_goals + 1)]
    a = [_poisson_pmf(i, away_xg) for i in range(max_goals + 1)]
    home = draw = away = over25 = btts = 0.0
    for i, ph in enumerate(h):
        for j, pa in enumerate(a):
            p = ph * pa
            if i > j: home += p
            elif i == j: draw += p
            else: away += p
            if i + j >= 3: over25 += p
            if i > 0 and j > 0: btts += p
    mass = sum(h) * sum(a)
    # Normalize the truncated score grid to prevent tail truncation bias.
    vals = [home / mass, draw / mass, away / mass, over25 / mass, btts / mass]
    return {"home": vals[0], "draw": vals[1], "away": vals[2], "over_2_5": vals[3], "btts_yes": vals[4]}


class ValidationSwarmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_id: str = Field(min_length=1, max_length=128)
    expected_goals_home: float = Field(ge=0, le=8)
    expected_goals_away: float = Field(ge=0, le=8)
    market_odds_1x2: dict[str, float] | None = None
    historical_probability_samples: list[float] = Field(default_factory=list, max_length=20000)
    bayesian_evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    monte_carlo_outcomes: list[str] = Field(default_factory=list, max_length=2000000)
    monte_carlo_batch_size: int = Field(default=100000, ge=1000, le=1000000)


def bootstrap_bot(samples: Iterable[float], bus: AgentBus) -> dict[str, Any]:
    xs = [_clamp(x) for x in samples]
    if len(xs) < 30:
        result = {"status": "UNAVAILABLE", "n": len(xs), "reason": "At least 30 genuine observations are required; no synthetic observations are generated."}
        bus.publish("bootstrap_bot", "uncertainty_interval", "UNAVAILABLE", result)
        return result
    result = {"status": "PASS", "n": len(xs), "mean": sum(xs) / len(xs), "empirical_q05": _quantile(xs, .05), "empirical_q50": _quantile(xs, .50), "empirical_q95": _quantile(xs, .95), "method": "empirical quantiles; no parametric bootstrap resamples implied"}
    bus.publish("bootstrap_bot", "uncertainty_interval", "PASS", result)
    return result


def sensitivity_bot(home_xg: float, away_xg: float, bus: AgentBus) -> dict[str, Any]:
    base = poisson_market_probabilities(home_xg, away_xg)
    scenarios = {}
    for name, hm, am in [
        ("home_xg_minus_20pct", .8, 1.0), ("home_xg_plus_20pct", 1.2, 1.0),
        ("away_xg_minus_20pct", 1.0, .8), ("away_xg_plus_20pct", 1.0, 1.2),
        ("both_xg_minus_15pct", .85, .85), ("both_xg_plus_15pct", 1.15, 1.15),
    ]:
        scenarios[name] = poisson_market_probabilities(min(8, home_xg * hm), min(8, away_xg * am))
    max_shift = max(abs(v[k] - base[k]) for v in scenarios.values() for k in base)
    result = {"status": "PASS" if max_shift <= .10 else "WARN", "base": base, "scenarios": scenarios, "max_absolute_probability_shift": max_shift, "threshold": .10}
    bus.publish("sensitivity_bot", "parameter_sensitivity", result["status"], result)
    return result


def scenario_stress_bot(home_xg: float, away_xg: float, bus: AgentBus) -> dict[str, Any]:
    scenarios = {
        "base": (home_xg, away_xg),
        "home_attack_disrupted": (home_xg * .65, away_xg),
        "away_attack_disrupted": (home_xg, away_xg * .65),
        "home_defence_collapse": (home_xg, away_xg * 1.45),
        "away_defence_collapse": (home_xg * 1.45, away_xg),
        "low_event_match": (home_xg * .70, away_xg * .70),
        "high_event_match": (home_xg * 1.30, away_xg * 1.30),
    }
    rows = {name: poisson_market_probabilities(min(8, h), min(8, a)) for name, (h, a) in scenarios.items()}
    base = rows["base"]
    swing = max(abs(v[k] - base[k]) for name, v in rows.items() if name != "base" for k in base)
    result = {"status": "PASS" if swing <= .15 else "WARN", "scenarios": rows, "max_absolute_probability_shift": swing, "threshold": .15, "note": "Stress scenarios are deterministic perturbations, not estimates of scenario likelihood."}
    bus.publish("scenario_stress_bot", "stress_test", result["status"], result)
    return result


def market_benchmark_bot(odds: dict[str, float] | None, model: dict[str, float], bus: AgentBus) -> dict[str, Any]:
    if not odds or any(k not in odds for k in ("home", "draw", "away")):
        result = {"status": "UNAVAILABLE", "reason": "Decimal odds for home, draw and away are required."}
        bus.publish("market_benchmark_bot", "market_comparison", "UNAVAILABLE", result)
        return result
    if any(not isinstance(odds[k], (int, float)) or odds[k] <= 1 for k in ("home", "draw", "away")):
        result = {"status": "BLOCK", "reason": "All 1X2 decimal odds must be greater than 1."}
        bus.publish("market_benchmark_bot", "market_comparison", "BLOCK", result)
        return result
    raw = {k: 1.0 / float(odds[k]) for k in ("home", "draw", "away")}
    overround = sum(raw.values()) - 1.0
    fair = {k: raw[k] / sum(raw.values()) for k in raw}
    gaps = {k: model[k] - fair[k] for k in fair}
    result = {"status": "PASS", "raw_implied_probabilities": raw, "normalized_market_probabilities": fair, "overround": overround, "model_minus_market": gaps, "largest_absolute_gap": max(abs(v) for v in gaps.values())}
    bus.publish("market_benchmark_bot", "market_comparison", "PASS", result)
    bus.send("market_benchmark_bot", "bayesian_update_bot", "market_prior_signal", "INFO", {"normalized_market_probabilities": fair, "model_minus_market": gaps, "warning": "Market odds are a benchmark, not independent proof."})
    return result


def bayesian_update_bot(priors: dict[str, float], evidence: list[dict[str, Any]], bus: AgentBus) -> dict[str, Any]:
    """Bayesian binary update for explicitly supplied likelihood ratios by outcome."""
    outputs = {}
    audit = []
    for outcome in ("home", "draw", "away"):
        prior = _clamp(priors[outcome])
        odds = prior / max(1e-12, 1.0 - prior)
        applied = []
        for item in evidence:
            if item.get("outcome") != outcome:
                continue
            lr = item.get("likelihood_ratio")
            if not isinstance(lr, (int, float)) or not math.isfinite(lr) or lr <= 0 or lr > 100:
                continue
            odds *= float(lr)
            applied.append({"source": str(item.get("source", "unspecified"))[:100], "likelihood_ratio": float(lr)})
        outputs[outcome] = odds / (1.0 + odds)
        audit.append({"outcome": outcome, "prior": prior, "evidence_applied": applied, "posterior": outputs[outcome]})
    total = sum(outputs.values())
    normalized = {k: v / total for k, v in outputs.items()} if total else dict(priors)
    result = {"status": "PASS" if evidence else "WARN", "posterior_1x2": normalized, "audit": audit, "evidence_count": len(evidence), "warning": "Likelihood ratios must be empirically justified; supplied evidence is not independently authenticated by this bot."}
    bus.publish("bayesian_update_bot", "posterior_update", result["status"], result)
    return result


def convergence_bot(outcomes: list[str], batch_size: int, bus: AgentBus) -> dict[str, Any]:
    allowed = {"home", "draw", "away"}
    if len(outcomes) < 2 * batch_size:
        result = {"status": "UNAVAILABLE", "n": len(outcomes), "required_minimum": 2 * batch_size, "reason": "Provide at least two actual, ordered Monte Carlo batches."}
        bus.publish("convergence_bot", "monte_carlo_convergence", "UNAVAILABLE", result)
        return result
    if any(x not in allowed for x in outcomes):
        result = {"status": "BLOCK", "reason": "Outcomes must be ordered labels: home, draw, away."}
        bus.publish("convergence_bot", "monte_carlo_convergence", "BLOCK", result)
        return result
    cut = (len(outcomes) // batch_size) * batch_size
    prior = outcomes[:cut - batch_size]
    last = outcomes[cut - batch_size:cut]
    def freqs(xs: list[str]) -> dict[str, float]:
        return {k: xs.count(k) / len(xs) for k in sorted(allowed)}
    p0, p1 = freqs(prior), freqs(last)
    shift = max(abs(p1[k] - p0[k]) for k in allowed)
    result = {"status": "PASS" if shift <= .01 else "WARN", "n": cut, "batch_size": batch_size, "cumulative_before_last_batch": p0, "last_batch": p1, "max_absolute_frequency_shift": shift, "threshold": .01, "note": "Convergence is assessed by adjacent-batch frequency stability; it is not a proof of model correctness."}
    bus.publish("convergence_bot", "monte_carlo_convergence", result["status"], result)
    return result


def run_validation_swarm(request: ValidationSwarmRequest) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    bus = AgentBus(run_id)
    model = poisson_market_probabilities(request.expected_goals_home, request.expected_goals_away)
    bus.publish("orchestrator", "run_started", "INFO", {"fixture_id": request.fixture_id, "model_probabilities": model})
    boot = bootstrap_bot(request.historical_probability_samples, bus)
    sens = sensitivity_bot(request.expected_goals_home, request.expected_goals_away, bus)
    stress = scenario_stress_bot(request.expected_goals_home, request.expected_goals_away, bus)
    market = market_benchmark_bot(request.market_odds_1x2, model, bus)
    # The Bayesian bot starts from the analytical 1X2 distribution and receives
    # a real message from the market bot when odds are available.
    market_msgs = bus.inbox("bayesian_update_bot", "market_prior_signal")
    evidence = list(request.bayesian_evidence)
    for msg in market_msgs:
        # Do not convert model-market gaps into likelihood ratios: market data is
        # shared for comparison only unless the caller provides justified LRs.
        bus.send("orchestrator", "bayesian_update_bot", "market_context", "INFO", msg.payload)
    bayes = bayesian_update_bot({k: model[k] for k in ("home", "draw", "away")}, evidence, bus)
    convergence = convergence_bot(request.monte_carlo_outcomes, request.monte_carlo_batch_size, bus)
    statuses = [boot["status"], sens["status"], stress["status"], market["status"], bayes["status"], convergence["status"]]
    # Missing optional evidence is visible but does not masquerade as a failed calculation.
    blockers = []
    if "BLOCK" in statuses:
        blockers.append("A validation bot reported BLOCK.")
    if sens["status"] == "WARN": blockers.append("Forecast is parameter-sensitive.")
    if stress["status"] == "WARN": blockers.append("Forecast is sensitive to adverse scenarios.")
    if market["status"] == "PASS" and market.get("largest_absolute_gap", 0) >= .15:
        blockers.append("Model/market probability disagreement is at least 15 percentage points.")
    if convergence["status"] == "WARN": blockers.append("Monte Carlo estimates did not meet the adjacent-batch stability threshold.")
    final_status = "BLOCKED" if blockers else ("REVIEW_REQUIRED" if any(s in ("WARN", "UNAVAILABLE") for s in statuses) else "VALIDATION_DIAGNOSTICS_PASS")
    bus.publish("final_validation_arbiter", "validation_summary", final_status, {"bot_statuses": statuses, "blockers": blockers, "note": "This diagnostic arbiter never authorizes a bet; the production UMIOS Final Arbiter and all existing gates remain mandatory."})
    return {
        "run_id": run_id, "fixture_id": request.fixture_id, "status": final_status,
        "model_probabilities": model,
        "bots": {"bootstrap": boot, "sensitivity": sens, "scenario_stress": stress, "market_benchmark": market, "bayesian_update": bayes, "convergence": convergence},
        "blockers": blockers,
        "communication": {"message_count": len(bus.messages), "messages": [asdict(m) for m in bus.messages]},
        "production_bet_certification": "NOT_GRANTED",
    }


@router.get("/status")
async def validation_swarm_status():
    return {"service": "omega-validation-method-bots", "bots": ["bootstrap", "sensitivity", "scenario_stress", "bayesian_update", "market_benchmark", "convergence"], "communication": "per-run shared message ledger with broadcast and targeted messages", "bet_certification": "not granted by this diagnostic swarm"}


@router.post("/run")
async def validation_swarm_run(request: ValidationSwarmRequest):
    return run_validation_swarm(request)
