import unittest
import tempfile
import os
from store import Store
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
        self.assertAlmostEqual(MarketBenchmarkEngine.clv(2.20,2.00),0.10,places=5)
    def test_calibration_metrics(self):
        c=CalibrationEngine().evaluate([{"p":.8,"y":1},{"p":.2,"y":0}]); self.assertIsNotNone(c["brier"]); self.assertIsNotNone(c["log_loss"])
    def test_weight_engine_shadows_thin_models(self):
        out=OmegaWeightEngine(min_samples=20).evaluate([{"model":"poisson","p":.6,"y":1},{"model":"market","p":.55,"y":0}])
        self.assertTrue(all(x["status"]=="SHADOW" for x in out["models"]))
    def test_store_freezes_prediction_and_exposes_calibration_ledger(self):
        fd,path=tempfile.mkstemp(); os.close(fd)
        try:
            s=Store(path)
            s.add_prediction("p1","fx1","1X2",.62,selection="1",odds=2.0,model_version="poisson",features={"competition":"Test League"})
            checks=s.verify_prediction_ledger("p1")
            self.assertTrue(checks[0]["valid"])
            s.record_outcome("p1",1)
            ledger=s.calibration_ledger()
            self.assertEqual(ledger[0]["p"],.62)
            self.assertEqual(ledger[0]["y"],1.0)
            self.assertEqual(ledger[0]["competition"],"Test League")
        finally:
            os.unlink(path)

    def test_pipeline_blocks_live_adjustment_without_data(self):
        out=CalibrationPipeline(min_train=20,min_test=10).run([{"predicted_at":1,"p":.6,"y":1}]*5); self.assertFalse(out["live_adjustment"])
