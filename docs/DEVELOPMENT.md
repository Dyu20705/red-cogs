# Development

```bash
git clone https://github.com/Dyu20705/red-cogs.git
cd red-cogs
python -m venv .venv
. .venv/Scripts/activate
python scripts/redctl.py check
```

For Red development, use a separate test instance and development Discord
server. Do not use production credentials or production webhook secrets.

Useful commands:

```bash
python scripts/redctl.py generate-docs
python scripts/redctl.py watch
python scripts/redctl.py print-reload --diff main..HEAD
python scripts/install_git_hooks.py --yes
```

In Discord:

```text
[p]addpath /path/to/red-cogs
[p]load <cog>
[p]reload <cog>
```

Commit messages should use a clear scope such as `chore:`, `docs:`, `test:`,
`refactor:`, `feat:`, or `ci:`. Debug logs and incident reports must be
redacted before sharing.
