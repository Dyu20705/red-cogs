import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def configured_audio_commands():
    commands = set()

    music_source = (ROOT / "imperialautomation/services/music_service.py").read_text(
        encoding="utf-8"
    )
    music_tree = ast.parse(music_source)
    for node in music_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "AUDIO_ALLOWED_COMMANDS"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            for item in node.value.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    commands.add(item.value)

    init_source = (ROOT / "imperialautomation/services/__init__.py").read_text(
        encoding="utf-8"
    )
    init_tree = ast.parse(init_source)
    for node in ast.walk(init_tree):
        if not isinstance(node, ast.Call) or len(node.args) != 1:
            continue
        func = node.func
        arg = node.args[0]
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "add"
            and isinstance(func.value, ast.Name)
            and func.value.id == "AUDIO_ALLOWED_COMMANDS"
            and isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
        ):
            commands.add(arg.value)

    return commands


class MusicRequestGateTests(unittest.TestCase):
    def test_summon_is_allowed_in_music_request_channel(self):
        self.assertIn("summon", configured_audio_commands())


if __name__ == "__main__":
    unittest.main()
