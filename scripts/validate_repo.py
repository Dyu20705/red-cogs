#!/usr/bin/env python3
"""Dependency-free structural checks for this Red cog repository."""

from __future__ import annotations

import ast
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []
VALID_POLICIES = {
    "inherit",
    "public_chat",
    "public_read_only",
    "private_staff",
    "private_staff_bot",
    "bot_post_only",
    "staff_post_only",
}


def error(message: str) -> None:
    ERRORS.append(message)


def warning(message: str) -> None:
    WARNINGS.append(message)


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        error(f"Missing JSON file: {path.relative_to(ROOT)}")
        return {}
    except json.JSONDecodeError as exc:
        error(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(data, dict):
        error(f"Expected JSON object in {path.relative_to(ROOT)}")
        return {}
    return data


def discover_cogs() -> list[Path]:
    ignored = {
        ".git",
        ".github",
        "assets",
        "docs",
        "scripts",
        "tests",
    }
    cogs: list[Path] = []
    for path in sorted(ROOT.iterdir()):
        if (
            not path.is_dir()
            or path.name in ignored
            or path.name.startswith(".")
        ):
            continue
        has_info = (path / "info.json").is_file()
        has_entrypoint = (path / "__init__.py").is_file()
        if has_info or has_entrypoint:
            if not (has_info and has_entrypoint):
                error(
                    f"Possible cog {path.name!r} needs info.json "
                    "and __init__.py"
                )
            else:
                cogs.append(path)
    if not cogs:
        error("No cog packages discovered")
    return cogs


def validate_metadata(cogs: Iterable[Path]) -> None:
    files = [(ROOT / "info.json", load_json(ROOT / "info.json"))]
    files.extend((cog / "info.json", load_json(cog / "info.json")) for cog in cogs)

    for path, data in files:
        relative = path.relative_to(ROOT)
        for key in ("author", "description", "short", "install_msg"):
            if not data.get(key):
                error(f"{relative}: missing or empty {key!r}")
        authors = data.get("author")
        if authors and (
            not isinstance(authors, list)
            or not all(
                isinstance(author, str) and author.strip()
                for author in authors
            )
        ):
            error(f"{relative}: author must be a string list")

        if path.parent == ROOT:
            continue
        if data.get("type") != "COG":
            error(f"{relative}: type must be COG")
        version = data.get("min_python_version")
        if not (
            isinstance(version, list)
            and len(version) == 3
            and all(isinstance(part, int) for part in version)
        ):
            error(f"{relative}: invalid min_python_version")
        if not data.get("min_bot_version"):
            error(f"{relative}: missing min_bot_version")
        if not data.get("end_user_data_statement"):
            error(f"{relative}: missing end_user_data_statement")


def literal_assignment(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"Assignment {name} not found")


def validate_blueprint() -> None:
    path = ROOT / "imperialsetup" / "blueprint.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        roles = literal_assignment(tree, "ROLE_SPECS")
        categories = literal_assignment(tree, "CATEGORIES")
    except (OSError, SyntaxError, ValueError) as exc:
        error(f"Cannot parse blueprint.py: {exc}")
        return

    def check_namespace(kind: str, specs: list[dict[str, Any]]) -> None:
        seen: dict[str, str] = {}
        for spec in specs:
            name = spec.get("name")
            if not isinstance(name, str) or not name.strip():
                error(f"{kind}: missing name")
                continue
            aliases = spec.get("aliases", [])
            if not isinstance(aliases, list):
                error(f"{kind} {name!r}: aliases must be a list")
                aliases = []
            for candidate in [name, *aliases]:
                if not isinstance(candidate, str):
                    error(f"{kind} {name!r}: alias must be a string")
                    continue
                key = normalise(candidate)
                previous = seen.get(key)
                if previous and previous != name:
                    error(
                        f"{kind} collision: {previous!r} and {name!r}"
                    )
                else:
                    seen[key] = name

    if not isinstance(roles, list) or not isinstance(categories, list):
        error("ROLE_SPECS and CATEGORIES must be lists")
        return
    check_namespace("role", roles)
    check_namespace("category", categories)

    seen_channels: dict[tuple[str, str], str] = {}
    for category in categories:
        if category.get("policy") not in VALID_POLICIES:
            error(f"Invalid category policy: {category.get('name')!r}")
        channels = category.get("channels", [])
        if not isinstance(channels, list):
            error(f"Category {category.get('name')!r}: channels must be a list")
            continue
        for channel in channels:
            name = channel.get("name")
            kind = channel.get("type")
            if kind not in {"text", "voice"}:
                error(f"Channel {name!r}: invalid type")
                continue
            if channel.get("policy", "inherit") not in VALID_POLICIES:
                error(f"Channel {name!r}: invalid policy")
            for candidate in [name, *channel.get("aliases", [])]:
                if not isinstance(candidate, str):
                    error(f"Channel {name!r}: invalid name/alias")
                    continue
                key = (kind, normalise(candidate))
                previous = seen_channels.get(key)
                if previous and previous != name:
                    error(
                        f"Channel collision: {previous!r} and {name!r}"
                    )
                else:
                    seen_channels[key] = name


def validate_python(cogs: Iterable[Path]) -> None:
    roots = [*cogs, ROOT / "scripts", ROOT / "tests"]
    for source_root in roots:
        if not source_root.exists():
            continue
        for path in sorted(source_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                ast.parse(
                    path.read_text(encoding="utf-8"),
                    filename=str(path),
                )
            except (OSError, UnicodeDecodeError, SyntaxError) as exc:
                error(f"Python parse error in {path.relative_to(ROOT)}: {exc}")


def validate_links(cogs: Iterable[Path]) -> None:
    files = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        *ROOT.glob("docs/*.md"),
        *(cog / "README.md" for cog in cogs),
    ]
    pattern = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")
    for path in files:
        if not path.exists():
            continue
        for raw_target in pattern.findall(path.read_text(encoding="utf-8")):
            target = raw_target.split("#", 1)[0]
            if target and not (path.parent / target).resolve().exists():
                error(f"{path.relative_to(ROOT)}: broken link {raw_target}")


def scan_sensitive_patterns() -> None:
    patterns = {
        "Discord credential": re.compile(
            r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{24,}\."
            r"[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}"
        ),
        "Discord webhook": re.compile(
            r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+",
            re.I,
        ),
        "GitHub credential": re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|"
            r"github_pat_[A-Za-z0-9_]{50,})\b"
        ),
        "private key": re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    }
    excluded = {".git", "__pycache__", ".venv", "venv", "redenv"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in patterns.items():
            if pattern.search(text):
                error(f"Possible {label} in {path.relative_to(ROOT)}")


def main() -> int:
    cogs = discover_cogs()
    validate_metadata(cogs)
    if any(cog.name == "imperialsetup" for cog in cogs):
        validate_blueprint()
    validate_python(cogs)
    validate_links(cogs)
    scan_sensitive_patterns()

    for message in WARNINGS:
        print(f"WARNING: {message}")
    for message in ERRORS:
        print(f"ERROR: {message}")
    if ERRORS:
        print(f"Validation failed with {len(ERRORS)} error(s).")
        return 1
    print(f"Validation passed for {len(cogs)} cog(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
