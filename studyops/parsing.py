from __future__ import annotations

import shlex
from typing import Any


def split_subject_goal(raw: str) -> tuple[str, str]:
    """Split `Subject | goal: ...` while keeping a forgiving fallback."""

    text = raw.strip()
    if "|" not in text:
        return text, ""
    subject, tail = text.split("|", 1)
    tail = tail.strip()
    lowered = tail.casefold()
    if lowered.startswith("goal:"):
        return subject.strip(), tail[5:].strip()
    if lowered.startswith("mục tiêu:"):
        return subject.strip(), tail[9:].strip()
    return subject.strip(), tail


def parse_key_value_tail(raw: str) -> dict[str, Any]:
    """Parse a compact command tail like `focus:8 learned:"..."`."""

    result: dict[str, Any] = {}
    if not raw.strip():
        return result

    try:
        tokens = shlex.split(raw)
    except ValueError:
        tokens = raw.split()

    current_key: str | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_parts
        if current_key:
            result[current_key] = " ".join(current_parts).strip()
        current_key = None
        current_parts = []

    for token in tokens:
        if ":" in token:
            before, after = token.split(":", 1)
            key = before.strip().casefold()
            if key:
                flush()
                current_key = key
                current_parts = [after.strip()] if after else []
                continue
        if current_key:
            current_parts.append(token)
    flush()
    return result


def parse_int_range(value: Any, *, minimum: int = 1, maximum: int = 10) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if minimum <= parsed <= maximum:
        return parsed
    return None
