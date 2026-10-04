import tempfile
import unittest
from case_database import CaseDatabaseManager


class TestCaseDatabase(unittest.TestCase):
    def test_case_isolated_and_chain_valid(self):
        with tempfile.TemporaryDirectory() as root:
            manager=CaseDatabaseManager(root)
            case=manager.open("fixture-123")
            case.record_observation("ACQUISITION","sofascore","sofascore",{"home":"A","away":"B"})
            case.record_trust({"state":"TRUSTED","envelope_hash":"abc","hard_blocks":[]})
            case.record_model_run("UMIOS-TITAN","UNDER_2_5",{"probability":0.62},1000,{"fixture":"fixture-123"})
            case.record_prediction({"prediction_id":"p1","market":"UNDER_2_5","selection":"UNDER","model_probability":0.62,"odds":1.80,"model":"UMIOS"})
            case.record_arbiter({"state":"NO_BET","reason":"value"})
            summary=case.summary()
            self.assertEqual(summary["case_id"],"fixture-123")
            self.assertEqual(summary["counts"]["audit_chain"],5)
            self.assertTrue(summary["chain"]["valid"])
            case.close()
            self.assertEqual(len(manager.list_cases()),1)
            manager.close()

    def test_case_databases_are_separate(self):
        with tempfile.TemporaryDirectory() as root:
            manager=CaseDatabaseManager(root)
            a=manager.open("A"); b=manager.open("B")
            a.record_observation("X","agent","source",{"x":1})
            b.record_observation("X","agent","source",{"x":2})
            self.assertNotEqual(a.path,b.path)
            self.assertEqual(a.summary()["counts"]["observations"],1)
            self.assertEqual(b.summary()["counts"]["observations"],1)
            a.close(); b.close(); manager.close()
