from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

from .models import (
    AssignOwnerRole,
    BaseAction,
    CreateCategory,
    CreateChannel,
    CreateRole,
    EditCategory,
    EditRole,
    MoveChannel,
    SeedChannel,
    SetSlowmode,
    SetTopic,
    SetUserLimit,
    WarningAction,
)


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


@dataclass(frozen=True)
class ExistingRole:
    id: int
    name: str


@dataclass(frozen=True)
class ExistingCategory:
    id: int
    name: str
    position: int = 0


@dataclass(frozen=True)
class ExistingChannel:
    id: int
    name: str
    channel_type: str
    category_name: str | None = None
    topic: str | None = None
    slowmode_delay: int = 0
    user_limit: int = 0
    empty: bool = False


@dataclass(frozen=True)
class DiscoveredState:
    roles: tuple[ExistingRole, ...] = field(default_factory=tuple)
    categories: tuple[ExistingCategory, ...] = field(default_factory=tuple)
    channels: tuple[ExistingChannel, ...] = field(default_factory=tuple)


def plan_actions(blueprint: dict[str, Any], state: DiscoveredState) -> list[BaseAction]:
    actions: list[BaseAction] = []
    role_index = _index_by_names(state.roles)
    category_index = _index_by_names(state.categories)

    for role_spec in blueprint.get("roles", []):
        role = _find(role_index, role_spec["name"], role_spec.get("aliases", []))
        if role is None:
            actions.append(
                CreateRole(
                    name=role_spec["name"],
                    colour=int(role_spec.get("colour", 0)),
                    hoist=bool(role_spec.get("hoist", False)),
                )
            )
        elif role.name != role_spec["name"]:
            actions.append(
                EditRole(
                    role_id=role.id,
                    before_name=role.name,
                    after_name=role_spec["name"],
                )
            )
        if role_spec.get("assign_owner"):
            actions.append(AssignOwnerRole(role_name=role_spec["name"]))

    channel_index = _channel_index(state.channels)
    for position, category_spec in enumerate(blueprint.get("categories", [])):
        category = _find(
            category_index,
            category_spec["name"],
            category_spec.get("aliases", []),
        )
        if category is None:
            actions.append(
                CreateCategory(
                    name=category_spec["name"],
                    position=position,
                    policy=category_spec.get("policy", "public_chat"),
                )
            )
        elif category.name != category_spec["name"]:
            actions.append(
                EditCategory(
                    category_id=category.id,
                    before_name=category.name,
                    after_name=category_spec["name"],
                )
            )

        for channel_spec in category_spec.get("channels", []):
            channel = _find_channel(
                channel_index,
                channel_spec["type"],
                channel_spec["name"],
                channel_spec.get("aliases", []),
            )
            if channel is None:
                actions.append(
                    CreateChannel(
                        name=channel_spec["name"],
                        channel_type=channel_spec["type"],
                        category_name=category_spec["name"],
                        policy=channel_spec.get("policy", "inherit"),
                    )
                )
                if channel_spec.get("seed"):
                    actions.append(
                        SeedChannel(
                            channel_id=None,
                            name=channel_spec["name"],
                            seed_title=channel_spec["seed"].get("title", ""),
                        )
                    )
                continue

            if channel.category_name != category_spec["name"]:
                actions.append(
                    MoveChannel(
                        channel_id=channel.id,
                        name=channel.name,
                        target_category=category_spec["name"],
                    )
                )
            if channel_spec["type"] == "text":
                topic = channel_spec.get("topic")
                if topic and channel.topic != topic:
                    actions.append(SetTopic(channel_id=channel.id, name=channel.name, topic=topic))
                slowmode = int(channel_spec.get("slowmode_delay", 0))
                if channel.slowmode_delay != slowmode:
                    actions.append(SetSlowmode(channel_id=channel.id, name=channel.name, seconds=slowmode))
                if channel.empty and channel_spec.get("seed"):
                    actions.append(
                        SeedChannel(
                            channel_id=channel.id,
                            name=channel.name,
                            seed_title=channel_spec["seed"].get("title", ""),
                        )
                    )
            if channel_spec["type"] == "voice":
                limit = int(channel_spec.get("user_limit", 0))
                if channel.user_limit != limit:
                    actions.append(SetUserLimit(channel_id=channel.id, name=channel.name, limit=limit))

    duplicate_channels = _duplicates(
        f"{item.channel_type}:{normalise(item.name)}" for item in state.channels
    )
    for duplicate in duplicate_channels:
        actions.append(WarningAction(message=f"Duplicate channel namespace: {duplicate}"))
    return actions


def _index_by_names(items: Iterable[ExistingRole | ExistingCategory]):
    index: dict[str, list[Any]] = {}
    for item in items:
        index.setdefault(normalise(item.name), []).append(item)
    return index


def _channel_index(items: Iterable[ExistingChannel]):
    index: dict[tuple[str, str], list[ExistingChannel]] = {}
    for item in items:
        index.setdefault((item.channel_type, normalise(item.name)), []).append(item)
    return index


def _find(index: dict[str, list[Any]], name: str, aliases: Iterable[str]):
    candidates = []
    for candidate in (name, *aliases):
        candidates.extend(index.get(normalise(candidate), []))
    unique = {item.id: item for item in candidates}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _find_channel(
    index: dict[tuple[str, str], list[ExistingChannel]],
    channel_type: str,
    name: str,
    aliases: Iterable[str],
) -> ExistingChannel | None:
    candidates: list[ExistingChannel] = []
    for candidate in (name, *aliases):
        candidates.extend(index.get((channel_type, normalise(candidate)), []))
    unique = {item.id: item for item in candidates}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)
