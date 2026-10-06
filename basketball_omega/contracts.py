from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class AgentOpinion:
    agent: str
    verdict: str
    confidence: float
    fair_margin: float | None = None
    fair_total: float | None = None
    win_prob_home: float | None = None
    rationale: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BasketballContext:
    home: str
    away: str
    players: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    injuries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    team_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    lineups: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    market: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float | None = None
    regime: str = "normal"

@dataclass
class FusionVerdict:
    state: str
    confidence: float
    fair_margin: float | None
    fair_total: float | None
    win_prob_home: float | None
    recommended_markets: List[Dict[str, Any]]
    dissent: List[Dict[str, Any]]
    blocked_reasons: List[str]
    agent_opinions: List[AgentOpinion]
    audit: Dict[str, Any] = field(default_factory=dict)
