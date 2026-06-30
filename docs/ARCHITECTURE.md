# Architecture review and vNext design

## Repository boundaries

The repository contains two separate systems:

```text
ImperialSetup: desired Discord structure -> audit/plan -> controlled mutation
DevelopmentOps: GitHub events/API -> normalize/route -> Discord workflows
```

Keeping them as separate cogs is correct. They share a server, but their failure modes, permissions, data handling, and test strategies are different.

## ImperialSetup audit

### Current design

- `blueprint.py`: desired roles, categories, channels, aliases, policies, and starter content.
- `imperialsetup.py`: commands, discovery, planning, mutation, permission policy, and reports.
- `hardening.py`: compatibility layer that narrows ownership and blocks ambiguous mutations.
- `safety.py`: dependency-free merge logic with unit tests.

### Important ownership rule

The blueprint may manage matching resources and the overwrites for:

- `@everyone`
- `👑 Quân Vương`
- `🏛️ Nội Các`
- `🛡️ Cận Vệ`
- the bot member

Other role/member overwrites belong to administrators or integrations and are preserved.

### Problems fixed

1. Replacing a complete channel/category overwrite mapping could remove custom entries.
2. Duplicate name/alias matches could cause an arbitrary channel to be selected.
3. Starter-message operation tracking used the wrong label.
4. Cog metadata did not reflect repository ownership.

The hardening layer now merges only blueprint-owned entries and stops mutating commands when multiple channels match.

### Remaining limits

- Names and aliases remain the primary identity.
- Discord does not provide a transaction for a multi-step server migration.
- The main engine mixes too many responsibilities.
- Personal project channels such as `arcaea-viewer` are in the base blueprint.

### Better vNext layout

```text
imperialsetup/
├─ commands.py
├─ models.py
├─ discovery.py
├─ planner.py
├─ executor.py
├─ permissions.py
├─ reporting.py
├─ profiles/
│  ├─ base.py
│  └─ personal.py
└─ state.py
```

After the first reconciliation, store resource IDs and a schema version in Red Config. A pure planner should return typed actions such as `CreateRole`, `MoveChannel`, and `PatchOverwrite`; only the executor should call Discord APIs.

## DevelopmentOps audit

### Strengths

- Signing validation before event dispatch.
- Loopback bind by default.
- Request-size cap.
- In-memory delivery deduplication.
- External content posted with mentions disabled in key paths.
- GitHub runtime values are not stored in Red Config.
- Managed forum labels preserve labels outside the managed set.

### Risks and limits

1. One file contains HTTP ingress, API clients, routing, rendering, forum sync, review threads, scheduling, and commands.
2. The listener runs in the Red process, so webhook bursts can affect bot responsiveness.
3. Active tasks and delivery deduplication are lost on restart.
4. Daily goals use a fixed UTC+7 timezone.
5. Forum content, attachment URLs, and creator IDs can cross from Discord to GitHub.
6. Changing repository/thread mappings needs a migration and cleanup strategy.
7. Invalid numeric environment configuration can fail early during cog initialization.

### Better vNext layout

```text
developmentops/
├─ commands.py
├─ config.py
├─ receiver.py
├─ security.py
├─ dispatcher.py
├─ github_client.py
├─ renderers/
├─ forum_sync.py
├─ review_threads.py
├─ scheduler.py
└─ models.py
```

For a personal server, an in-process listener is acceptable when kept on loopback behind HTTPS. At larger scale, use:

```text
GitHub -> HTTPS ingress -> durable queue -> Red consumer
```

## Shared design principles

- Least privilege; no default Administrator permission.
- Read-only audit and planning before mutation.
- Explicit ownership boundaries.
- Idempotent operations where possible.
- Runtime configuration outside the repository.
- External content treated as untrusted.
- Dependency-free core logic for fast unit tests.
- Observable failures with operation context.

## Do not automate

- Deleting roles/channels/messages from name matching alone.
- Granting Administrator automatically.
- Publishing raw Lavalink or webhook listener ports.
- Installing unreviewed community cogs.
- Sending complete private logs into Discord.
- Running permission optimization periodically without a new audit.

## Production-readiness checklist

- Validator, unit tests, and compile checks pass.
- Development server runtime test completed.
- Backup and restore steps documented and rehearsed.
- Custom overwrites remain after optimization.
- DevelopmentOps listens on loopback and public ingress uses HTTPS.
- GitHub access is limited to required repositories and operations.
- Forum members are informed when content can be copied to GitHub.
