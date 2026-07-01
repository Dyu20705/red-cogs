#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "start-red.sh failed at line $LINENO" >&2' ERR

VENV=".venv-red"
INSTANCE="YOUR_INSTANCE"
RESTART=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="${2:?}"; shift ;;
    --instance) INSTANCE="${2:?}"; shift ;;
    --restart) RESTART=1 ;;
    --help) echo "Usage: $0 --instance NAME [--venv PATH] [--restart]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -z "$INSTANCE" || "$INSTANCE" == "YOUR_INSTANCE" ]]; then
  echo "Set --instance to the Red instance name." >&2
  exit 2
fi

REDBOT="$VENV/bin/redbot"
[[ -x "$REDBOT" ]] || { echo "redbot not found: $REDBOT" >&2; exit 2; }

while true; do
  "$REDBOT" "$INSTANCE"
  CODE=$?
  [[ "$RESTART" -eq 1 && "$CODE" -ne 0 ]] || exit "$CODE"
  sleep 10
done
