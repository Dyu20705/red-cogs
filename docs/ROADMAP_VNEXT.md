# vNext Roadmap

## P0 - Safety, Scripts, Tests, Docs

- Add dependency-free `scripts/redctl.py` for check, doctor, backup, restore,
  update, watch, generated docs, and reload hints.
- Add Windows and Linux wrappers with help/dry-run or confirmation behavior.
- Generate command reference from AST without importing Red.
- Add concise cheatsheet, upgrade, data handling, and runtime smoke-test docs.
- Expand unit tests for pure helper logic.
- Keep credential values out of diagnostics and docs.

## P1 - Incremental Refactor

- Extract DevelopmentOps settings parsing, HMAC verification, delivery dedupe,
  bounded webhook queue, and task tracking.
- Add per-guild DevelopmentOps timezone with `Asia/Bangkok` default.
- Add BotOps deep health diagnostic without exposing environment values.
- Add ImperialSetup typed action models, pure planner skeleton, profile split,
  and state migration helpers.

## P2 - Optional Platform Improvements

- Persist DevelopmentOps delivery dedupe with TTL and max size.
- Wire ImperialSetup planner/executor fully into public commands.
- Add richer BotOps permission hierarchy checks in embeds.
- Add optional Red-supported hot-reload adapter if an official mechanism is
  available for the installed Red version.

## Deferred

- Runtime smoke tests on a real development Discord server.
- Full ImperialSetup executor facade migration.
- Durable external queue for GitHub webhooks.
- Lavalink integration tests across connected/disconnected node states.
- Any production restart, auto-deploy, or auto-reload workflow.
