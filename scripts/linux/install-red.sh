#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "install-red.sh failed at line $LINENO" >&2' ERR

DRY_RUN=0
VENV=".venv-red"
INSTANCE="YOUR_INSTANCE"
SKIP_JAVA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --venv) VENV="${2:?}"; shift ;;
    --instance) INSTANCE="${2:?}"; shift ;;
    --skip-java) SKIP_JAVA=1 ;;
    --help) echo "Usage: $0 [--dry-run] [--venv PATH] [--instance NAME] [--skip-java]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not run this whole script as root. It uses sudo only where needed." >&2
  exit 2
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" ]]; then
  echo "Warning: this script is tested for Ubuntu 24.04; detected ${PRETTY_NAME:-unknown}." >&2
fi

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

run sudo apt-get update
run sudo apt-get install -y python3 python3-venv python3-pip git build-essential
if [[ "$SKIP_JAVA" -eq 0 ]]; then
  run sudo apt-get install -y openjdk-17-jre-headless
fi
run python3 -m venv "$VENV"
run "$VENV/bin/python" -m pip install --upgrade pip wheel Red-DiscordBot

echo "Next steps:"
echo "  $VENV/bin/redbot-setup"
echo "  scripts/linux/start-red.sh --venv '$VENV' --instance '$INSTANCE'"
