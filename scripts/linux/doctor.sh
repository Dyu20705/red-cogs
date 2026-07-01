#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "doctor.sh failed at line $LINENO" >&2' ERR
python3 scripts/redctl.py doctor "$@"
