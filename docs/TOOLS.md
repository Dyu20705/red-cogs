# Tools and server automation strategy

The goal is not to install as many bots as possible. A small Red instance with clear workflows, least privilege, reliable backup, and filtered notifications is usually better.

## Recommended Red core cogs

| Cog | Purpose | Notes |
|---|---|---|
| Downloader | Install/update community cogs | Bot owner only |
| General | Basic utility commands | Lightweight |
| Audio | Music and local tracks | Requires compatible Java/Lavalink |
| Permissions | Restrict commands by role/channel | Prefer over Administrator |
| Mod + ModLog | Moderation and audit | Enable only when needed |
| Cleanup | Controlled message cleanup | Requires deliberate permissions |
| CustomCommands | Simple personal commands | Not a replacement for complex cogs |

Repository cogs:

- **ImperialSetup**: structure, permission audit, and controlled reconciliation.
- **DevelopmentOps**: filtered GitHub activity, review threads, forum/issue workflows, and daily goals.

## Host tools

### Common

- Git for versioning and rollback.
- Python 3.11 virtual environment for Red.
- Java 17 LTS for a simple Audio setup.
- Password manager for service credentials.
- Separate development bot/server for permission changes.
- Versioned backups with retention.

### Windows

- PowerShell and Windows Terminal.
- Task Scheduler or a controlled restart script.
- Disable sleep/hibernate on a machine expected to host continuously.

### Ubuntu

- systemd for lifecycle/restart.
- journalctl for logs.
- UFW for minimal firewall rules.
- Nginx/Caddy or a secure tunnel for DevelopmentOps HTTPS ingress.
- `ss`, `curl`, `df`, and `du` for health checks.

## Category workflows

### BOT

- `#bot-commands`: interactive commands.
- `#music-request`: music requests.
- `#now-playing`: bot-post-only status.
- `#bot-errors`, `#bot-logs`: staff and bot only.

Never post unredacted process logs in public channels.

### STUDY

- `#goals-and-progress`: weekly/monthly goals.
- `#study-log`: concise daily updates.
- `#resources`: curated, staff-post-only resources.
- Pomodoro/Study Room voice channels.

Prefer threads for subjects and projects rather than many empty channels.

### DEVELOPMENT

- `#dev-chat`: general discussion.
- Forum `bugs-and-ideas`: one post per issue candidate.
- `#code-review`: one thread per PR.
- `#github-feed`: filtered events.
- `#goals-and-progress`: DevelopmentOps daily goals.

A basic Discord webhook is sufficient for a read-only feed. DevelopmentOps is useful when routing, filtering, review threads, and forum/issue mapping are required.

### FEEDS

- Keep one `#all-feeds` while volume is low.
- Split into tech/fun/video only when volume justifies it.
- Prefer PR, issue, release, security, and failed-workflow events over every commit.
- Deduplicate and filter before posting to reduce notification fatigue.

## Reviewing a community cog

Before installation:

1. Check recent maintenance history.
2. Read `info.json`, requirements, and the end-user data statement.
3. Review network, filesystem, subprocess, and dynamic-code paths.
4. Identify required credentials and data transfers.
5. Test on a secondary bot/server.
6. Grant only required Discord permissions.
7. Document uninstall and restore steps.

A listing service is a discovery aid, not a security guarantee; source code and maintenance history remain the main evidence.

## Local music

- Store music outside this repository.
- Ensure the Red process user can read the folder.
- Keep managed Lavalink private.
- Do not commit MP3/FLAC files.
- Use `[p]help Audio` for commands matching the installed Red version.

## Automation levels

### Safe to automate

- Process start/restart.
- Repository validate/test/compile checks.
- Local health checks.
- Scheduled backup with retention.
- Filtered release and failed-workflow feeds.

### Require confirmation

- Role or channel permission changes.
- Creating, renaming, or moving channels.
- Updating Red/community cogs.
- Posting starter content.
- Enabling Forum-to-GitHub synchronization.

### Do not automate

- Deleting roles/channels/messages.
- Granting Administrator.
- Installing unreviewed cogs.
- Publishing raw Lavalink/webhook ports.
- Copying private logs or private forum content to public systems.

## Roadmap

### Phase 1 — stability

- Red + Audio + ImperialSetup.
- systemd/Windows restart.
- Backup, logs, and least privilege.
- Repository CI.

### Phase 2 — personal workspace

- DevelopmentOps for active repositories.
- Filtered events, forum tags, and daily goals.
- Reviewed reminder/pomodoro cog.
- Local music library.

### Phase 3 — platform quality

- ImperialSetup profiles and resource-ID migrations.
- Modular DevelopmentOps receiver/client/queue.
- Durable delivery deduplication.
- Configurable timezone.
- Health metrics and documented restore drills.
