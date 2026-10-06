# Basketball OMEGA — Historical Pipeline & Walk-Forward Evaluation v1

This stage adds the missing research-to-promotion loop without touching football/UMIOS code.

Pipeline:
1. Point-in-time historical examples are created from BasketballSnapshot.
2. Expanding-window training uses only examples with cutoff_at strictly before the OOS fixture.
3. Player impact observations are opponent/teammate adjusted with shrinkage.
4. Expected minutes are consumed at prediction time; unavailable players do not leak postgame information.
5. Player-adjusted strength is combined with team possession features.
6. OOS predictions are scored with Brier, log loss, ECE, margin MAE, total MAE, and CLV.
7. Promotion requires sufficient OOS samples, no regression in probability, calibration, margin, or total error, positive CLV, and chronological integrity.

Important limitation: this is now a real executable walk-forward framework, but it is not evidence that a model is already production-proven. Production readiness still requires a populated, independently validated historical snapshot corpus and a completed OOS run meeting the gate.

No football imports are used by this stage.
