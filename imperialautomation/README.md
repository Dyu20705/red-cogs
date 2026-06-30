# ImperialAutomation — Feeds and Music Phase

This Red-DiscordBot cog is the first consolidated ImperialAutomation package.

Implemented services:
- Filtered RSS/Atom polling
- Keyword include/exclude filters
- URL deduplication
- 24-hour freshness limit
- Interestingness scoring
- Maximum three posts per polling cycle
- Daily topic threads and nightly digest
- Serious security-alert routing
- Music guide and persistent Now Playing panel
- #music-request command gate and cleanup
- Per-user queue quota
- Empty voice auto-disconnect
- Private Listening join-to-create rooms

Recommended migration:
1. Keep ImperialSetup for structure/reconcile/diagnose.
2. Load BotOps for audit/error routing.
3. Load ImperialAutomation.
4. Keep StudyOps and DevelopmentOps temporarily.
5. After stable operation, migrate their services into this same package and unload the old cogs.

Do not run multiple RSS or private-music-room cogs at the same time.
