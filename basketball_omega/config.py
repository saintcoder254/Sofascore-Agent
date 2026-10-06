import os
from dataclasses import dataclass

@dataclass(frozen=True)
class BasketballOmegaConfig:
    simulations: int = int(os.getenv("BASKETBALL_MC_SIMS","20000"))
    min_history: int = int(os.getenv("BASKETBALL_MIN_HISTORY","12"))
    min_edge: float = float(os.getenv("BASKETBALL_MIN_EDGE","0.025"))
    max_agent_disagreement: float = float(os.getenv("BASKETBALL_MAX_DISAGREEMENT","0.12"))
    min_calibration_samples: int = int(os.getenv("BASKETBALL_MIN_CAL_SAMPLES","100"))
    max_injury_uncertainty: float = float(os.getenv("BASKETBALL_MAX_INJURY_UNCERTAINTY","0.20"))
