import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ServerAutomationExtensionTests(unittest.TestCase):
    def test_imperial_blueprint_extensions(self):
        source = (ROOT / "imperialsetup/automation.py").read_text(encoding="utf-8")
        self.assertIn('"name": "leet-code"', source)
        self.assertIn('"study-log"', source)
        self.assertIn("AUDIT & MOD LOG — NGỰ SỬ ĐÀI", source)
        self.assertIn("📢 Bảng cáo thị", source)
        ast.parse(source)

    def test_studyops_has_leetcode_controls_and_scheduler(self):
        source = (ROOT / "studyops/automation.py").read_text(encoding="utf-8")
        self.assertIn('@commands.group(name="leetcode")', source)
        self.assertIn('@leetcode.command(name="schedule")', source)
        self.assertIn('@leetcode.command(name="now"', source)
        self.assertIn("leetcode_loop.start()", source)
        self.assertIn("post_leetcode_daily", source)
        ast.parse(source)

    def test_botops_has_expected_audit_listeners(self):
        source = (ROOT / "botops/automation.py").read_text(encoding="utf-8")
        listeners = (
            "on_message_delete",
            "on_message_edit",
            "on_member_join",
            "on_member_remove",
            "on_member_ban",
            "on_guild_channel_update",
            "on_guild_role_update",
        )
        for listener in listeners:
            self.assertIn(f"async def {listener}", source)
        ast.parse(source)

    def test_package_entries_load_extended_classes(self):
        expected = {
            "studyops/__init__.py": "from .automation import StudyOps",
            "botops/__init__.py": "from .automation import BotOps",
            "imperialsetup/__init__.py": "from .automation import ImperialSetup",
        }
        for relative_path, import_line in expected.items():
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(import_line, source)


if __name__ == "__main__":
    unittest.main()
