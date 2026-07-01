#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "start-red.sh failed at line $LINENO" >&2' ERR

VENV=".venv-red"
INSTANCE="YOUR_INSTANCE"
RESTART=0
MAX_RESTARTS=5
BACKOFF_SECONDS=10
RESTART_CODES=",26,"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="${2:?Missing value for --venv}"; shift ;;
    --instance) INSTANCE="${2:?Missing value for --instance}"; shift ;;
    --restart) RESTART=1 ;;
    --max-restarts) MAX_RESTARTS="${2:?Missing value for --max-restarts}"; shift ;;
    --backoff) BACKOFF_SECONDS="${2:?Missing value for --backoff}"; shift ;;
    --restart-exit-code)
      RESTART_CODES+="${2:?Missing value for --restart-exit-code},"
      shift
      ;;
    --help)
      cat <<'EOF'
Usage: start-red.sh --instance NAME [options]

Options:
  --venv PATH                 Red virtual environment (default: .venv-red)
  --restart                   Restart only for configured exit codes
  --restart-exit-code CODE    Add a restart exit code (default: 26)
  --max-restarts COUNT        Maximum restarts before stopping (default: 5)
  --backoff SECONDS           Delay between restarts (default: 10)
  --help                      Show this help
EOF
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -z "$INSTANCE" || "$INSTANCE" == "YOUR_INSTANCE" ]]; then
  echo "Set --instance to the Red instance name." >&2
  exit 2
fi
if ! [[ "$MAX_RESTARTS" =~ ^[0-9]+$ && "$BACKOFF_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--max-restarts and --backoff must be non-negative integers." >&2
  exit 2
fi

REDBOT="$VENV/bin/redbot"
[[ -x "$REDBOT" ]] || { echo "redbot not found: $REDBOT" >&2; exit 2; }

restart_count=0
while true; do
  set +e
  "$REDBOT" "$INSTANCE"
  code=$?
  set -e

  if [[ "$RESTART" -ne 1 || "$code" -eq 0 || "$RESTART_CODES" != *",$code,"* ]]; then
    exit "$code"
  fi

  restart_count=$((restart_count + 1))
  if (( restart_count > MAX_RESTARTS )); then
    echo "Red requested restart more than $MAX_RESTARTS time(s); stopping with exit code $code." >&2
    exit "$code"
  fi

  echo "Red exited with restart code $code; restarting in $BACKOFF_SECONDS second(s)..."
  sleep "$BACKOFF_SECONDS"
done
