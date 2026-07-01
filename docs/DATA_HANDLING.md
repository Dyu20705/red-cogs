# Data Handling

No cog stores Discord bot tokens, GitHub tokens, webhook secrets, or private keys
in repository files. DevelopmentOps reads GitHub runtime values from process
environment only.

## ImperialSetup

Reads guild roles, categories, channels, permissions, and selected message
history to decide whether starter content is needed. Current runtime state is
mostly Discord state; vNext state helpers define schema version, active profile,
managed resources, last plan summary, and last reconcile time. Backup impact is
low unless Red Config state is later enabled. Privacy risk: channel names,
role names, and setup reports can reveal server structure.

## DevelopmentOps

Stores repository names, channel IDs, Forum and PR thread mappings, schedule
settings, and timezone in Red Config. GitHub token and webhook signing value are
read from environment and only reported as present/absent. Sends selected
GitHub event content to Discord and, when Forum sync is enabled, can send Forum
post content and attachment URLs to GitHub Issues. Backup impact is medium
because mappings reveal repository and Discord thread IDs.

## BotOps

Stores audit/error/log channel IDs, retention settings, counters, and sanitized
incident log files under the cog data path. Tracebacks are redacted before
Discord delivery and local write. Privacy risk is medium because stack traces
can include user, guild, channel, command, and path context.

## ImperialAutomation

Stores feed source URLs, hashed seen URLs, digest items, channel/message IDs,
music queue controls, and temporary voice-room ownership. It fetches configured
RSS/Atom URLs and sends matching entries to Discord. Backup impact is medium
because feed configuration and room ownership IDs are preserved.

## StudyOps

Stores member goals, progress, study metrics, schedule configuration, temporary
room ownership, and message IDs. It does not send data to external services.
Backup impact is high for personal productivity history.

## MusicStatus

Stores guild channel and status message IDs. It reads Red latency, uptime, cog
state, and Lavalink status when available. Backup impact is low.
