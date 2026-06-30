from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Dict, TypeVar

Target = TypeVar("Target")
Value = TypeVar("Value")


def merge_owned_entries(
    existing: Mapping[Target, Value],
    desired: Mapping[Target, Value],
    owned_targets: Iterable[Target],
) -> Dict[Target, Value]:
    owned = set(owned_targets)
    result = {
        target: value
        for target, value in existing.items()
        if target not in owned
    }
    result.update(desired)
    return result
