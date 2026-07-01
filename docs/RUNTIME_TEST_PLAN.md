# Runtime Smoke Test Plan

Run on a development Discord server, not production. Record expected result and
cleanup for each item.

## Cog Lifecycle

```text
[p]load <cog>
[p]reload <cog>
[p]unload <cog>
```

Expected: each cog loads independently and unloads without background task
errors.

## ImperialSetup

- Run audit, plan, reconcile on a fixture server. Expected: no unmanaged
  resource deletion.
- Add custom overwrites before optimize. Expected: custom overwrites remain.
- Create duplicate channel aliases. Expected: mutating command stops with a
  clear ambiguity warning.
- Test profile change and state reset once command integration is complete.

## DevelopmentOps

- Start without signing value. Expected: receiver disabled with clear warning.
- Start with invalid port. Expected: cog loads and receiver is disabled.
- Send signed ping delivery. Expected: 202 and Discord route works.
- Send invalid signature. Expected: 403 and no dispatch.
- Send webhook burst above queue size. Expected: bounded 503 responses.
- Test PR review thread, Forum to Issue, closed/reopened Issue, stale mapping
  diagnostics, and timezone schedule.

## BotOps

- Trigger synthetic test error. Expected: public summary redacted, detailed log
  sanitized.
- Run `[p]botops health`. Expected: no raw environment value, no mentions.

## StudyOps

- Run Pomodoro start/pause/resume/stop. Expected: metrics update.
- Create and empty temporary voice room. Expected: owned room cleanup.
- Restart bot during session. Expected: no stale task traceback.

## ImperialAutomation And MusicStatus

- Run with Audio unavailable. Expected: degraded status, no traceback.
- Connect/disconnect Lavalink. Expected: panels update.
- Delete configured status message. Expected: fallback creates a new message.
- Post duplicate feed entry. Expected: dedupe suppresses repeat.
