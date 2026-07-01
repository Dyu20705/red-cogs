#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "install-systemd.sh failed at line $LINENO" >&2' ERR

SERVICE_NAME="red@.service"
TEMPLATE="examples/systemd/red@.service"
DRY_RUN=0
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --help) echo "Usage: $0 [--dry-run] [--yes]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

[[ -f "$TEMPLATE" ]] || { echo "Missing template: $TEMPLATE" >&2; exit 2; }
if [[ "$YES" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
  echo "Review $TEMPLATE, then rerun with --yes." >&2
  exit 1
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Would install $TEMPLATE to /etc/systemd/system/$SERVICE_NAME"
  exit 0
fi
sudo install -m 0644 "$TEMPLATE" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
echo "Installed. Enable manually after review:"
echo "  sudo systemctl enable --now red@YOUR_INSTANCE.service"
echo "Rollback:"
echo "  sudo rm /etc/systemd/system/$SERVICE_NAME && sudo systemctl daemon-reload"
