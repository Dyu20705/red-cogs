# DevelopmentOps for Red-DiscordBot

Features:
- GitHub push/PR/issue/workflow/tag feed
- Release and production deployment channel
- review-needed PR threads
- Discord Forum -> GitHub Issue sync
- GitHub issue closed -> Discord resolved tag
- Morning DEVELOPMENT GOALS

Secrets are never stored in Red Config. Set these in the Red process environment:
- DEVELOPMENTOPS_WEBHOOK_SECRET
- DEVELOPMENTOPS_GITHUB_TOKEN (optional for public read-only use; required for private repos and Forum issue creation)
- DEVELOPMENTOPS_HOST (default 127.0.0.1)
- DEVELOPMENTOPS_PORT (default 8765)

GitHub webhook endpoint:
POST /github

Health endpoint:
GET /healthz
