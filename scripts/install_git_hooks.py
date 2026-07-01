#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".git" / "hooks" / "pre-commit"

HOOK_BODY = """#!/usr/bin/env sh
python scripts/redctl.py check
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a local pre-commit hook that runs redctl check."
    )
    parser.add_argument("--yes", action="store_true", help="Overwrite after creating a backup")
    args = parser.parse_args()

    if not (ROOT / ".git").exists():
        print("This does not look like a Git checkout.", file=sys.stderr)
        return 2

    if HOOK.exists():
        existing = HOOK.read_text(encoding="utf-8", errors="replace")
        if existing == HOOK_BODY:
            print("pre-commit hook is already installed.")
            return 0
        if not args.yes:
            print("pre-commit hook already exists. Rerun with --yes to back it up and replace it.")
            return 1
        backup = HOOK.with_suffix(".pre-commit-backup")
        counter = 1
        while backup.exists():
            backup = HOOK.with_suffix(f".pre-commit-backup-{counter}")
            counter += 1
        shutil.copy2(HOOK, backup)
        print(f"Backed up existing hook to {backup}")

    HOOK.write_text(HOOK_BODY, encoding="utf-8")
    mode = HOOK.stat().st_mode
    HOOK.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed {HOOK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
