import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BoundaryQualityContractTests(unittest.TestCase):
    def test_maintained_boundaries_distinguish_bounded_adapters_from_absent_live_paths(self) -> None:
        limitations = (ROOT / "docs" / "LOCAL_LIMITATIONS.md").read_text(encoding="utf-8")
        readiness = (ROOT / "docs" / "READINESS_GATES.md").read_text(encoding="utf-8")

        self.assertIn("bounded public instrument, manual session, and research-only historical-candle adapters", limitations.lower())
        self.assertIn("no broker account/profile/funds/holdings/positions state, live quotes, websocket feed, order endpoint, external scheduler, cloud service", limitations.lower())
        self.assertNotIn("no credentials or network code in the repository", readiness.lower())
        self.assertIn("bounded public-master, manual session, and research-candle adapters", readiness.lower())
        self.assertIn("no adapter presence is evidence of provider permission", readiness.lower())

    def test_make_lint_runs_declared_ruff_rules_after_compilation(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("python3.12 -m compileall -q src tests", makefile)
        self.assertIn("ruff check src tests", makefile)
        self.assertIn("lint:\n\tpython3.12 -m compileall -q src tests\n\truff check src tests\n", makefile)


if __name__ == "__main__":
    unittest.main()
