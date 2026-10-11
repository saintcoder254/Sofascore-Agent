import ast
import pathlib
import tempfile
import unittest

from basketball_omega.contracts import BasketballContext
from basketball_omega.data_schema import BasketballSnapshot, TeamSnapshot
from basketball_omega.router import BasketballRouter
from basketball_omega.snapshot_store import BasketballSnapshotStore

ROOT = pathlib.Path(__file__).resolve().parents[1]

class TestBasketballBoundaries(unittest.TestCase):
    def test_basketball_package_has_no_football_imports(self):
        package = ROOT / "basketball_omega"
        for path in package.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [x.name for x in node.names]
                    self.assertFalse(any(n.startswith(("umios", "football")) for n in names), path)
                elif isinstance(node, ast.ImportFrom):
                    name = node.module or ""
                    self.assertFalse(name.startswith(("umios", "football")), path)

    def test_router_rejects_non_basketball_context(self):
        with self.assertRaises(TypeError):
            BasketballRouter().analyze({"home":"H","away":"A"})

    def test_snapshot_store_is_point_in_time(self):
        snap = BasketballSnapshot(
            fixture_id="g1", captured_at=100.0,
            home_team_id="H", away_team_id="A",
            teams={
                "H": TeamSnapshot("H","Home",90.0,{"ortg":118}),
                "A": TeamSnapshot("A","Away",90.0,{"ortg":112}),
            },
        )
        fd, path = tempfile.mkstemp(suffix=".db")
        import os
        os.close(fd)
        try:
            store = BasketballSnapshotStore(path)
            store.put(snap)
            self.assertIsNotNone(store.latest_before("g1", 100.0))
            self.assertIsNone(store.latest_before("g1", 99.0))
            store.close()
        finally:
            pathlib.Path(path).unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
