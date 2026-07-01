#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "update-red.sh failed at line $LINENO" >&2' ERR

VENV=".venv-red"
BACKUP_SOURCE=""
BACKUP_DESTINATION=""
SKIP_BACKUP=0
YES=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="${2:?Missing value for --venv}"; shift ;;
    --backup-source) BACKUP_SOURCE="${2:?Missing value for --backup-source}"; shift ;;
    --backup-destination) BACKUP_DESTINATION="${2:?Missing value for --backup-destination}"; shift ;;
    --skip-backup) SKIP_BACKUP=1 ;;
    --yes) YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --help)
      cat <<'EOF'
Usage: update-red.sh [options]

Options:
  --venv PATH                  Red virtual environment (default: .venv-red)
  --backup-source PATH         Red data directory to back up
  --backup-destination PATH    Directory for verified backup archives
  --skip-backup                Explicitly skip backup; requires --yes
  --yes                        Non-interactive confirmation
  --dry-run                    Print actions without changing the environment
  --help                       Show this help
EOF
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

PYTHON="$VENV/bin/python"
[[ -x "$PYTHON" ]] || { echo "Python not found in venv: $PYTHON" >&2; exit 2; }
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
REDCTL="$REPO_ROOT/scripts/redctl.py"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if [[ "$SKIP_BACKUP" -eq 1 ]]; then
  if [[ "$YES" -ne 1 ]]; then
    echo "Skipping backup requires both --skip-backup and --yes." >&2
    exit 1
  fi
  echo "Warning: backup explicitly skipped." >&2
else
  if [[ -z "$BACKUP_SOURCE" || -z "$BACKUP_DESTINATION" ]]; then
    echo "Provide --backup-source and --backup-destination, or use --skip-backup --yes." >&2
    exit 2
  fi
  backup_args=("$PYTHON" "$REDCTL" backup --source "$BACKUP_SOURCE" --destination "$BACKUP_DESTINATION")
  [[ "$YES" -eq 1 ]] && backup_args+=(--yes)
  [[ "$DRY_RUN" -eq 1 ]] && backup_args+=(--dry-run)
  "${backup_args[@]}"
fi

run "$PYTHON" -m pip install --upgrade Red-DiscordBot
run "$PYTHON" "$REDCTL" check

echo "Run manually in Discord after review:"
echo "  [p]cog update"
