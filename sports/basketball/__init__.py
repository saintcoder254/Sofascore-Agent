"""Basketball TITAN modules."""
from .engine import BasketballEngine, GameContext, Projection, TeamProfile
from .simulation import SimulationResult, simulate
from .decision import Decision, decide
from .lineup import PlayerImpact, availability_quality, lineup_adjustment
from .regime import RegimeSignal, classify_regime
from .shot_model import ShotOutcomeModel, ShotProfile, PossessionOutcome
from .rotation import RotationPlayer, RotationSummary, summarize_rotation
from .features import TeamFeatures, DataFreshness, normalize_rate
from .adversarial import StressCase, StressResult, stress_test

__all__ = [
    "BasketballEngine", "GameContext", "Projection", "TeamProfile",
    "SimulationResult", "simulate", "Decision", "decide",
    "PlayerImpact", "availability_quality", "lineup_adjustment",
    "RegimeSignal", "classify_regime",
    "ShotOutcomeModel", "ShotProfile", "PossessionOutcome",
    "RotationPlayer", "RotationSummary", "summarize_rotation",
    "TeamFeatures", "DataFreshness", "normalize_rate",
    "StressCase", "StressResult", "stress_test",
]
