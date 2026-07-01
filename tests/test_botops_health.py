import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "botops" / "health.py"
SPEC = importlib.util.spec_from_file_location("botops_health", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["botops_health"] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeBot:
    latency = 0.123
    uptime = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __init__(self):
        self._cogs = {"DevelopmentOps": object(), "BotOps": object()}

    def get_cog(self, name):
        return self._cogs.get(name)

    def is_ready(self):
        return True


class HealthSnapshotTests(unittest.TestCase):
    def test_snapshot_reports_presence_without_secret_values(self):
        snapshot = MODULE.build_health_snapshot(
            FakeBot(),
            environ={
                "DEVELOPMENTOPS_WEBHOOK_SECRET": "super-secret",
                "DEVELOPMENTOPS_GITHUB_TOKEN": "ghp_should_not_appear",
            },
        )
        text = "\n".join(snapshot.as_lines())
        self.assertIn("DevelopmentOps signing value present: `True`", text)
        self.assertNotIn("super-secret", text)
        self.assertNotIn("ghp_should_not_appear", text)


if __name__ == "__main__":
    unittest.main()
