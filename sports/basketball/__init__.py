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
from .data_adapter import BasketballDataAdapter
from .collector import BasketballCollector
from .store import BasketballStore
from .feature_builder import RollingTeamFeatures, build_rolling_features
from .arbiter import BasketballArbiter, ModelSignal, ArbiterResult
from .training import TrainingRow, TrainingMetrics, evaluate, chronological_split

__all__ = [
    "BasketballEngine", "GameContext", "Projection", "TeamProfile",
    "SimulationResult", "simulate", "Decision", "decide",
    "PlayerImpact", "availability_quality", "lineup_adjustment",
    "RegimeSignal", "classify_regime",
    "ShotOutcomeModel", "ShotProfile", "PossessionOutcome",
    "RotationPlayer", "RotationSummary", "summarize_rotation",
    "TeamFeatures", "DataFreshness", "normalize_rate",
    "StressCase", "StressResult", "stress_test",
    "BasketballDataAdapter", "BasketballCollector", "BasketballStore",
    "RollingTeamFeatures", "build_rolling_features",
    "BasketballArbiter", "ModelSignal", "ArbiterResult",
    "TrainingRow", "TrainingMetrics", "evaluate", "chronological_split",
]
