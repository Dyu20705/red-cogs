#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "install-systemd.sh failed at line $LINENO" >&2' ERR

SERVICE_NAME="red@.service"
TEMPLATE="examples/systemd/red@.service"
DRY_RUN=0
YES=0
RED_USER="$(id -un)"
WORKING_DIRECTORY="$(pwd -P)"
VENV=".venv-red"
ENVIRONMENT_FILE="/etc/red/%i.env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --user) RED_USER="${2:?Missing value for --user}"; shift ;;
    --working-directory) WORKING_DIRECTORY="${2:?Missing value for --working-directory}"; shift ;;
    --venv) VENV="${2:?Missing value for --venv}"; shift ;;
    --environment-file) ENVIRONMENT_FILE="${2:?Missing value for --environment-file}"; shift ;;
    --help)
      cat <<'EOF'
Usage: install-systemd.sh [options]

Options:
  --user USER                 Service account (default: current user)
  --working-directory PATH   Operations directory (default: current directory)
  --venv PATH                Red virtual environment (default: .venv-red)
  --environment-file PATH    Optional EnvironmentFile (default: /etc/red/%i.env)
  --dry-run                   Print rendered service without installing it
  --yes                       Confirm installation
  --help                      Show this help
EOF
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

[[ -f "$TEMPLATE" ]] || { echo "Missing template: $TEMPLATE" >&2; exit 2; }
id "$RED_USER" >/dev/null 2>&1 || { echo "Unknown service user: $RED_USER" >&2; exit 2; }
WORKING_DIRECTORY="$(realpath "$WORKING_DIRECTORY")"
if [[ "$VENV" = /* ]]; then
  VENV_PATH="$VENV"
else
  VENV_PATH="$WORKING_DIRECTORY/$VENV"
fi
REDBOT_EXECUTABLE="$(realpath -m "$VENV_PATH/bin/redbot")"
[[ -x "$REDBOT_EXECUTABLE" || "$DRY_RUN" -eq 1 ]] || {
  echo "redbot executable not found: $REDBOT_EXECUTABLE" >&2
  exit 2
}

rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT
python3 - "$TEMPLATE" "$rendered" "$RED_USER" "$WORKING_DIRECTORY" "$ENVIRONMENT_FILE" "$REDBOT_EXECUTABLE" <<'PY'
from pathlib import Path
import sys

source, target, user, workdir, env_file, executable = sys.argv[1:]
for value in (user, workdir, env_file, executable):
    if "\n" in value or "\r" in value:
        raise SystemExit("Unsafe newline in systemd configuration value")
text = Path(source).read_text(encoding="utf-8")
text = text.replace("User=YOUR_USER", f"User={user}")
text = text.replace("WorkingDirectory=/opt/red/YOUR_INSTANCE", f"WorkingDirectory={workdir}")
text = text.replace("EnvironmentFile=-/etc/red/%i.env", f"EnvironmentFile=-{env_file}")
text = text.replace("ExecStart=/opt/red/YOUR_INSTANCE/.venv-red/bin/redbot %i", f"ExecStart={executable} %i --no-prompt")
if "YOUR_USER" in text or "/opt/red/YOUR_INSTANCE" in text:
    raise SystemExit("Unresolved systemd template placeholder")
Path(target).write_text(text, encoding="utf-8")
PY

if [[ "$DRY_RUN" -eq 1 ]]; then
  cat "$rendered"
  exit 0
fi
if [[ "$YES" -ne 1 ]]; then
  echo "Review the rendered service with --dry-run, then rerun with --yes." >&2
  exit 1
fi

sudo install -m 0644 "$rendered" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
echo "Installed /etc/systemd/system/$SERVICE_NAME"
echo "Enable manually after review:"
echo "  sudo systemctl enable --now red@YOUR_INSTANCE.service"
echo "Rollback:"
echo "  sudo rm /etc/systemd/system/$SERVICE_NAME && sudo systemctl daemon-reload"
