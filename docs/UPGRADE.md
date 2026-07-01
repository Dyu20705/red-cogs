# Upgrade Guide

Always backup Red data before updating source, Red, or cogs.

## Update Source

```bash
python scripts/redctl.py update --dry-run
python scripts/redctl.py update
```

`redctl update` refuses dirty working trees, fetches the remote, requires a
fast-forward, runs checks, and prints reload commands. It does not restart Red
or reload production cogs automatically.

## Update Red

Windows:

```powershell
.\scripts\windows\update-red.ps1 -VenvPath .venv-red -Yes
```

Ubuntu:

```bash
scripts/linux/update-red.sh --venv .venv-red --yes
```

## Update Cogs

Run in Discord after reviewing source and checks:

```text
[p]cog update
[p]reload <cog>
```

Use reload for code-only cog changes. Restart the Red process when changing
Python packages, environment variables, process service files, or receiver bind
configuration.

## Rollback

Use the previous Git commit or branch and reload affected cogs. Restore Red data
only when configuration or state was changed and the archive has been verified:

```bash
python scripts/redctl.py restore --archive backup.zip --destination /path/to/data --dry-run
python scripts/redctl.py restore --archive backup.zip --destination /path/to/data --yes
```

Restore does not start the bot automatically.
