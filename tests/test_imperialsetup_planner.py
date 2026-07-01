import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


models = load_module("imperialsetup.models", "imperialsetup/models.py")
planner = load_module("imperialsetup.planner", "imperialsetup/planner.py")
state = load_module("imperialsetup.state", "imperialsetup/state.py")


class PlannerTests(unittest.TestCase):
    def test_generates_create_and_edit_actions(self):
        blueprint = {
            "roles": [
                {"name": "Owner", "aliases": ["Boss"], "colour": 1, "assign_owner": True},
                {"name": "Member", "colour": 2},
            ],
            "categories": [
                {
                    "name": "BOT",
                    "aliases": ["Bots"],
                    "policy": "public_chat",
                    "channels": [
                        {
                            "type": "text",
                            "name": "bot-commands",
                            "topic": "Use bot here.",
                            "slowmode_delay": 1,
                            "seed": {"title": "Guide"},
                        }
                    ],
                }
            ],
        }
        discovered = planner.DiscoveredState(
            roles=(planner.ExistingRole(10, "Boss"),),
            categories=(planner.ExistingCategory(20, "Bots"),),
            channels=(
                planner.ExistingChannel(
                    30,
                    "bot-commands",
                    "text",
                    category_name="OLD",
                    topic=None,
                    empty=True,
                ),
            ),
        )

        actions = planner.plan_actions(blueprint, discovered)
        kinds = [item.kind for item in actions]
        self.assertIn(models.ActionKind.EDIT_ROLE, kinds)
        self.assertIn(models.ActionKind.CREATE_ROLE, kinds)
        self.assertIn(models.ActionKind.ASSIGN_OWNER_ROLE, kinds)
        self.assertIn(models.ActionKind.EDIT_CATEGORY, kinds)
        self.assertIn(models.ActionKind.MOVE_CHANNEL, kinds)
        self.assertIn(models.ActionKind.SET_TOPIC, kinds)
        self.assertIn(models.ActionKind.SET_SLOWMODE, kinds)
        self.assertIn(models.ActionKind.SEED_CHANNEL, kinds)
        self.assertEqual(actions[0].to_dict()["kind"], "edit_role")

    def test_state_migration_defaults_and_filters_bad_resources(self):
        migrated = state.migrate_state(
            {
                "active_profile": "base",
                "managed_resources": [
                    {"kind": "channel", "name": "bot", "resource_id": "123"},
                    {"bad": "data"},
                ],
            }
        )
        self.assertEqual(migrated.schema_version, state.SCHEMA_VERSION)
        self.assertEqual(migrated.active_profile, "base")
        self.assertEqual(len(migrated.managed_resources), 1)


if __name__ == "__main__":
    unittest.main()
