#!/usr/bin/env python3
"""Cross-platform operations helper for this Red cog repository."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
COGS = (
    "imperialsetup",
    "developmentops",
    "botops",
    "imperialautomation",
    "studyops",
    "musicstatus",
)
WATCH_EXTENSIONS = {".py", ".json", ".md", ".yml", ".yaml", ".sh", ".ps1", ".bat"}
SENSITIVE_ENV_WORDS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "PRIVATE_KEY", "WEBHOOK")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def run(
    args: Sequence[str],
    *,
    check: bool = False,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        env=env,
    )


def print_result(result: CheckResult) -> None:
    marker = "OK" if result.ok else "FAIL"
    suffix = f" - {result.detail}" if result.detail else ""
    print(f"[{marker}] {result.name}{suffix}")


def check_command(name: str, args: Sequence[str], *, env: dict[str, str] | None = None) -> CheckResult:
    proc = run(args, capture=True, env=env)
    output = (proc.stdout or "").strip()
    return CheckResult(name, proc.returncode == 0, output.splitlines()[-1] if output else "")


def command_check(args: argparse.Namespace) -> int:
    del args
    def check_env(label: str) -> dict[str, str]:
        pycache = Path(tempfile.mkdtemp(prefix=f"redctl-pycache-{label}-"))
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = str(pycache)
        return env

    checks = [
        check_command("repository validator", [sys.executable, "scripts/validate_repo.py"], env=check_env("validator")),
        check_command("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], env=check_env("tests")),
        check_command(
            "compileall",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                *COGS,
                "scripts",
                "tests",
            ],
            env=check_env("compileall"),
        ),
        check_command("git diff --check", ["git", "diff", "--check"]),
    ]

    generator = check_command(
        "generate command reference",
        [sys.executable, "scripts/generate_command_reference.py"],
        env=check_env("docs"),
    )
    checks.append(generator)
    checks.append(check_command("generated docs freshness", ["git", "diff", "--exit-code", "--", "docs/COMMANDS.md"]))

    ruff = shutil.which("ruff")
    if ruff:
        checks.append(check_command("ruff check", [ruff, "check", "."], env=check_env("ruff")))

    for result in checks:
        print_result(result)
    return 0 if all(item.ok for item in checks) else 1


def redact_env_present(name: str) -> dict[str, bool]:
    if any(word in name.upper() for word in SENSITIVE_ENV_WORDS):
        return {"present": bool(os.getenv(name))}
    return {"present": bool(os.getenv(name))}


def port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def command_version(args: Sequence[str]) -> str:
    try:
        proc = run(args, capture=True)
    except OSError as exc:
        return f"missing: {exc}"
    return (proc.stdout or "").strip().splitlines()[0] if proc.stdout else "unknown"


def detect_repo_root() -> str:
    proc = run(["git", "rev-parse", "--show-toplevel"], capture=True)
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout.strip()
    return str(ROOT)


def command_doctor(args: argparse.Namespace) -> int:
    host = os.getenv("DEVELOPMENTOPS_HOST", "127.0.0.1")
    raw_port = os.getenv("DEVELOPMENTOPS_PORT", "8765")
    try:
        port = int(raw_port)
    except ValueError:
        port = 8765

    report = {
        "ok": True,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "virtualenv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        },
        "tools": {
            "git": command_version(["git", "--version"]),
            "java": command_version(["java", "-version"]),
            "redbot": shutil.which("redbot") or "not found on PATH",
        },
        "repository": {
            "root": detect_repo_root(),
            "expected_root": str(ROOT),
            "info_json": (ROOT / "info.json").is_file(),
            "cogs": {name: (ROOT / name / "info.json").is_file() for name in COGS},
        },
        "ports": {
            "developmentops": {
                "host": host,
                "port": port,
                "listening": port_listening(host, port) if 1 <= port <= 65535 else False,
            }
        },
        "environment": {
            "DEVELOPMENTOPS_WEBHOOK_SECRET": redact_env_present("DEVELOPMENTOPS_WEBHOOK_SECRET"),
            "DEVELOPMENTOPS_GITHUB_TOKEN": redact_env_present("DEVELOPMENTOPS_GITHUB_TOKEN"),
            "DEVELOPMENTOPS_HOST": {"present": bool(os.getenv("DEVELOPMENTOPS_HOST"))},
            "DEVELOPMENTOPS_PORT": {"present": bool(os.getenv("DEVELOPMENTOPS_PORT"))},
        },
        "writable": {
            "repo_tmp": os.access(ROOT, os.W_OK),
            "system_tmp": os.access(tempfile.gettempdir(), os.W_OK),
        },
    }
    validator = run([sys.executable, "scripts/validate_repo.py"], capture=True)
    report["validator"] = {
        "ok": validator.returncode == 0,
        "summary": (validator.stdout or "").strip().splitlines()[-1] if validator.stdout else "",
    }
    report["ok"] = bool(report["validator"]["ok"])

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Red Cogs doctor")
        print(f"OS: {report['os']['system']} {report['os']['release']} {report['os']['machine']}")
        print(f"Python: {report['os']['python']} virtualenv={report['os']['virtualenv']}")
        print(f"Git: {report['tools']['git']}")
        print(f"Java: {report['tools']['java']}")
        print(f"Red executable: {report['tools']['redbot']}")
        print(f"Repository: {report['repository']['root']}")
        print(f"DevelopmentOps receiver listening: {report['ports']['developmentops']['listening']}")
        print(f"Webhook secret present: {report['environment']['DEVELOPMENTOPS_WEBHOOK_SECRET']['present']}")
        print(f"GitHub token present: {report['environment']['DEVELOPMENTOPS_GITHUB_TOKEN']['present']}")
        print(f"Validator: {report['validator']['summary']}")
    return 0 if report["ok"] else 1


def ensure_confirmed(yes: bool, message: str) -> bool:
    if yes:
        return True
    answer = input(f"{message} Type YES to continue: ").strip()
    return answer == "YES"


def safe_archive_name(instance: str | None) -> str:
    suffix = f"-{instance}" if instance else ""
    return datetime.now(timezone.utc).strftime(f"red-data{suffix}-%Y%m%dT%H%M%SZ.zip")


def write_manifest(zipf: zipfile.ZipFile, source: Path, instance: str | None) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_name": source.name,
        "instance": instance,
        "warning": "Red data backups may contain sensitive administrative configuration.",
    }
    zipf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))


def iter_backup_files(source: Path) -> Iterable[Path]:
    for path in source.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            yield path


def command_backup(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        print(f"Source directory does not exist: {source}", file=sys.stderr)
        return 2
    archive = destination / safe_archive_name(args.instance)
    print("Warning: Red data backups may contain sensitive administrative data.")
    if args.dry_run:
        print(f"Would create archive: {archive}")
        return 0
    if not ensure_confirmed(args.yes, f"Create backup from {source} to {archive}?"):
        print("Backup cancelled.")
        return 1
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        write_manifest(zipf, source, args.instance)
        for file_path in iter_backup_files(source):
            zipf.write(file_path, file_path.relative_to(source))
    with zipfile.ZipFile(archive, "r") as zipf:
        bad = zipf.testzip()
        if bad:
            print(f"Archive verification failed at {bad}", file=sys.stderr)
            return 1
    if hasattr(os, "chmod"):
        os.chmod(archive, 0o600)
    prune_backups(destination, args.retention)
    print(f"Backup created: {archive}")
    return 0


def prune_backups(destination: Path, retention: int) -> None:
    if retention <= 0:
        return
    archives = sorted(destination.glob("red-data*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    for archive in archives[retention:]:
        archive.unlink(missing_ok=True)


def validate_zip_members(archive: Path) -> None:
    with zipfile.ZipFile(archive, "r") as zipf:
        for member in zipf.infolist():
            target = Path(member.filename)
            if target.is_absolute() or ".." in target.parts:
                raise ValueError(f"Unsafe archive path: {member.filename}")


def command_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    if not archive.is_file():
        print(f"Archive not found: {archive}", file=sys.stderr)
        return 2
    try:
        validate_zip_members(archive)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rollback = destination.with_name(destination.name + ".before-restore-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if args.dry_run:
        print(f"Would restore {archive} to {destination}")
        print(f"Existing destination would move to {rollback}")
        return 0
    if not ensure_confirmed(args.yes, f"Restore {archive} into {destination}?"):
        print("Restore cancelled.")
        return 1
    if destination.exists():
        destination.rename(rollback)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zipf:
        zipf.extractall(destination)
    print(f"Restore complete. Rollback path: {rollback}")
    print("Red was not started automatically.")
    return 0


def command_update(args: argparse.Namespace) -> int:
    status = run(["git", "status", "--porcelain"], capture=True)
    if status.stdout and status.stdout.strip():
        print("Working tree is dirty; refusing update.", file=sys.stderr)
        return 1
    target = f"{args.remote}/{args.branch}"
    run(["git", "fetch", args.remote], check=True)
    changed = changed_paths(f"HEAD..{target}")
    base = run(["git", "merge-base", "--is-ancestor", "HEAD", target], capture=True)
    if base.returncode != 0:
        print(f"{target} is not a fast-forward from HEAD.", file=sys.stderr)
        return 1
    print("Changed cogs:", ", ".join(changed_cogs(changed)) or "none")
    if args.dry_run:
        print(f"Would fast-forward to {target}")
        return 0
    run(["git", "merge", "--ff-only", target], check=True)
    check_code = command_check(argparse.Namespace())
    print_reload_commands(changed)
    return check_code


def changed_paths(spec: str | None = None) -> list[str]:
    cmd = ["git", "diff", "--name-only"]
    if spec:
        cmd.append(spec)
    proc = run(cmd, capture=True)
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def changed_cogs(paths: Iterable[str]) -> list[str]:
    result = []
    for cog in COGS:
        prefix = f"{cog}/"
        if any(path == cog or path.startswith(prefix) for path in paths):
            result.append(cog)
    return result


def print_reload_commands(paths: Iterable[str]) -> None:
    for cog in changed_cogs(paths):
        print(f"[p]reload {cog}")


def command_print_reload(args: argparse.Namespace) -> int:
    print_reload_commands(changed_paths(args.diff))
    return 0


def file_snapshot() -> dict[str, float]:
    snapshot: dict[str, float] = {}
    ignored = {".git", ".tmp", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in WATCH_EXTENSIONS:
            continue
        if any(part in ignored for part in path.parts):
            continue
        snapshot[str(path.relative_to(ROOT))] = path.stat().st_mtime
    return snapshot


def command_watch(args: argparse.Namespace) -> int:
    print("Watching repository; press Ctrl+C to stop.")
    previous = file_snapshot()
    try:
        while True:
            time.sleep(args.interval)
            current = file_snapshot()
            changed = [
                path
                for path, mtime in current.items()
                if previous.get(path) != mtime
            ]
            removed = [path for path in previous if path not in current]
            if changed or removed:
                time.sleep(args.debounce)
                paths = changed + removed
                print(f"Detected {len(paths)} changed file(s).")
                code = command_check(argparse.Namespace())
                if code == 0:
                    print_reload_commands(paths)
                previous = file_snapshot()
    except KeyboardInterrupt:
        print("Watch stopped.")
        return 0


def command_generate_docs(args: argparse.Namespace) -> int:
    del args
    proc = run([sys.executable, "scripts/generate_command_reference.py"])
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Run validator, tests, compile, diff checks").set_defaults(func=command_check)

    doctor = sub.add_parser("doctor", help="Inspect host and repository health")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    doctor.set_defaults(func=command_doctor)

    backup = sub.add_parser("backup", help="Create a zip backup of Red data")
    backup.add_argument("--source", required=True)
    backup.add_argument("--destination", required=True)
    backup.add_argument("--retention", type=int, default=7)
    backup.add_argument("--instance")
    backup.add_argument("--dry-run", action="store_true")
    backup.add_argument("--yes", action="store_true")
    backup.set_defaults(func=command_backup)

    restore = sub.add_parser("restore", help="Restore a backup archive")
    restore.add_argument("--archive", required=True)
    restore.add_argument("--destination", required=True)
    restore.add_argument("--dry-run", action="store_true")
    restore.add_argument("--yes", action="store_true")
    restore.set_defaults(func=command_restore)

    update = sub.add_parser("update", help="Fast-forward source and run checks")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--branch", default="main")
    update.add_argument("--remote", default="origin")
    update.set_defaults(func=command_update)

    watch = sub.add_parser("watch", help="Poll files and run checks after changes")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.add_argument("--debounce", type=float, default=0.8)
    watch.set_defaults(func=command_watch)

    sub.add_parser("generate-docs", help="Generate docs/COMMANDS.md").set_defaults(func=command_generate_docs)

    reload_parser = sub.add_parser("print-reload", help="Print reload commands for changed cogs")
    reload_parser.add_argument("--diff", help="Optional git diff range, e.g. main..HEAD")
    reload_parser.set_defaults(func=command_print_reload)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
