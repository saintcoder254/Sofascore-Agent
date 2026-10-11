import unittest
from basketball_omega.ci_swarm import StaticBot, BoundaryBot, ContractBot


class TestBasketballCISwarm(unittest.TestCase):
    def test_static_boundary_bot(self):
        result = StaticBot().run()
        self.assertTrue(result.passed, result.findings)

    def test_boundary_bot(self):
        result = BoundaryBot().run()
        self.assertTrue(result.passed, result.findings)

    def test_contract_bot(self):
        result = ContractBot().run()
        self.assertTrue(result.passed, result.findings)


if __name__ == "__main__":
    unittest.main()
