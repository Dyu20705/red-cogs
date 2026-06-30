import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "imperialsetup"
    / "safety.py"
)
SPEC = importlib.util.spec_from_file_location(
    "imperialsetup_safety",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
merge_owned_entries = MODULE.merge_owned_entries


class MergeOwnedEntriesTests(unittest.TestCase):
    def test_preserves_unmanaged_targets(self):
        existing = {
            "everyone": "old-public",
            "cabinet": "old-staff",
            "custom-role": "custom",
            "member-42": "member-specific",
        }
        desired = {
            "everyone": "new-public",
            "cabinet": "new-staff",
        }

        result = merge_owned_entries(
            existing,
            desired,
            {"everyone", "cabinet", "guard", "bot"},
        )

        self.assertEqual(result["everyone"], "new-public")
        self.assertEqual(result["cabinet"], "new-staff")
        self.assertEqual(result["custom-role"], "custom")
        self.assertEqual(result["member-42"], "member-specific")

    def test_removes_owned_target_when_not_desired(self):
        existing = {
            "everyone": "old",
            "guard": "old",
            "custom": "keep",
        }
        desired = {"everyone": "new"}

        result = merge_owned_entries(
            existing,
            desired,
            {"everyone", "guard"},
        )

        self.assertEqual(
            result,
            {"everyone": "new", "custom": "keep"},
        )

    def test_does_not_mutate_inputs(self):
        existing = {"everyone": "old", "custom": "keep"}
        desired = {"everyone": "new"}
        existing_copy = existing.copy()
        desired_copy = desired.copy()

        merge_owned_entries(existing, desired, {"everyone"})

        self.assertEqual(existing, existing_copy)
        self.assertEqual(desired, desired_copy)


if __name__ == "__main__":
    unittest.main()
