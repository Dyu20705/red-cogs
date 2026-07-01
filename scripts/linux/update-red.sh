#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "update-red.sh failed at line $LINENO" >&2' ERR

VENV=".venv-red"
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="${2:?}"; shift ;;
    --yes) YES=1 ;;
    --help) echo "Usage: $0 [--venv PATH] [--yes]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ "$YES" -ne 1 ]]; then
  echo "Create/verify a backup first, then rerun with --yes." >&2
  exit 1
fi

"$VENV/bin/python" -m pip install --upgrade Red-DiscordBot
python3 scripts/redctl.py check
echo "Run manually in Discord after review:"
echo "  [p]cog update"
