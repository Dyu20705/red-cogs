import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "musicstatus/musicstatus.py"


class MusicStatusDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_tracks_command_panel_message_ids(self):
        self.assertIn("command_message_ids", self.source)

    def test_live_index_uses_loaded_bot_commands(self):
        calls = [node for node in ast.walk(self.tree) if isinstance(node, ast.Call)]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "walk_commands"
                for call in calls
            )
        )

    def test_commands_refresh_subcommand_exists(self):
        self.assertIn('name="commands"', self.source)
        self.assertIn('aliases=["command", "cmds"]', self.source)

    def test_status_and_commands_refresh_together(self):
        self.assertIn("await self.publish_all(ctx.guild)", self.source)
        self.assertIn("await self.publish_all(guild)", self.source)


if __name__ == "__main__":
    unittest.main()
