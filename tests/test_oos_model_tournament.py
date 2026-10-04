import unittest
from oos_model_tournament import OOSModelTournament

class TestOOSTournament(unittest.TestCase):
    def rows(self, model, bias=0.0):
        return [{"predicted_at":i,"fixture_id":f"f{i}","market":"1X2","p":min(.99,max(.01,.55+bias+(i%2)*.1)),"y":1.0 if i%3 else 0.0,"model":model} for i in range(80)]

    def test_insufficient_test_data_shadows(self):
        out=OOSModelTournament(min_train=50,min_test=20).run({"a":self.rows("a")[:60]})
        self.assertEqual(out["models"]["a"]["state"],"SHADOW")

    def test_evaluates_chronological_holdout(self):
        out=OOSModelTournament(min_train=50,min_test=20).run({"a":self.rows("a")})
        self.assertEqual(out["models"]["a"]["state"],"EVALUATED")
        self.assertEqual(out["models"]["a"]["train_samples"],56)
        self.assertEqual(out["models"]["a"]["test_samples"],24)

if __name__=="__main__":
    unittest.main()
