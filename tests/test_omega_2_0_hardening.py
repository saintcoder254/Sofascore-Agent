import unittest
from prediction_ledger_guard import PredictionLedgerGuard
from calibration_engine import CalibrationEngine
from market_benchmark_engine import MarketBenchmarkEngine
from omega_weight_engine import OmegaWeightEngine
from calibration_pipeline import CalibrationPipeline

class TestOmegaHardening(unittest.TestCase):
    def test_ledger_freeze_and_verify(self):
        g=PredictionLedgerGuard(); r=g.freeze({"fixture_id":"x","market":"1X2","selection":"1","model":"OMEGA"})
        self.assertTrue(g.verify(r)["valid"])
    def test_market_clv(self):
        self.assertAlmostEqual(MarketBenchmarkEngine.clv(2.20,2.00),-0.090909,places=5)
    def test_calibration_metrics(self):
        c=CalibrationEngine().evaluate([{"p":.8,"y":1},{"p":.2,"y":0}]); self.assertIsNotNone(c["brier"]); self.assertIsNotNone(c["log_loss"])
    def test_weight_engine_shadows_thin_models(self):
        out=OmegaWeightEngine(min_samples=20).evaluate([{"model":"poisson","p":.6,"y":1},{"model":"market","p":.55,"y":0}])
        self.assertTrue(all(x["status"]=="SHADOW" for x in out["models"]))
    def test_pipeline_blocks_live_adjustment_without_data(self):
        out=CalibrationPipeline(min_train=20,min_test=10).run([{"predicted_at":1,"p":.6,"y":1}]*5); self.assertFalse(out["live_adjustment"])
