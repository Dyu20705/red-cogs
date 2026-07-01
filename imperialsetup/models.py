from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    CREATE_ROLE = "create_role"
    EDIT_ROLE = "edit_role"
    ASSIGN_OWNER_ROLE = "assign_owner_role"
    CREATE_CATEGORY = "create_category"
    EDIT_CATEGORY = "edit_category"
    CREATE_CHANNEL = "create_channel"
    MOVE_CHANNEL = "move_channel"
    PATCH_OVERWRITE = "patch_overwrite"
    SET_TOPIC = "set_topic"
    SET_SLOWMODE = "set_slowmode"
    SET_USER_LIMIT = "set_user_limit"
    SEED_CHANNEL = "seed_channel"
    SET_AFK_CHANNEL = "set_afk_channel"
    WARNING = "warning"


@dataclass(frozen=True)
class BaseAction:
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


@dataclass(frozen=True)
class CreateRole(BaseAction):
    name: str
    colour: int
    hoist: bool = False
    kind: ActionKind = ActionKind.CREATE_ROLE


@dataclass(frozen=True)
class EditRole(BaseAction):
    role_id: int | None
    before_name: str
    after_name: str
    kind: ActionKind = ActionKind.EDIT_ROLE


@dataclass(frozen=True)
class AssignOwnerRole(BaseAction):
    role_name: str
    kind: ActionKind = ActionKind.ASSIGN_OWNER_ROLE


@dataclass(frozen=True)
class CreateCategory(BaseAction):
    name: str
    position: int
    policy: str
    kind: ActionKind = ActionKind.CREATE_CATEGORY


@dataclass(frozen=True)
class EditCategory(BaseAction):
    category_id: int | None
    before_name: str
    after_name: str
    kind: ActionKind = ActionKind.EDIT_CATEGORY


@dataclass(frozen=True)
class CreateChannel(BaseAction):
    name: str
    channel_type: str
    category_name: str
    policy: str
    kind: ActionKind = ActionKind.CREATE_CHANNEL


@dataclass(frozen=True)
class MoveChannel(BaseAction):
    channel_id: int | None
    name: str
    target_category: str
    kind: ActionKind = ActionKind.MOVE_CHANNEL


@dataclass(frozen=True)
class PatchOverwrite(BaseAction):
    target_name: str
    resource_name: str
    policy: str
    kind: ActionKind = ActionKind.PATCH_OVERWRITE


@dataclass(frozen=True)
class SetTopic(BaseAction):
    channel_id: int | None
    name: str
    topic: str
    kind: ActionKind = ActionKind.SET_TOPIC


@dataclass(frozen=True)
class SetSlowmode(BaseAction):
    channel_id: int | None
    name: str
    seconds: int
    kind: ActionKind = ActionKind.SET_SLOWMODE


@dataclass(frozen=True)
class SetUserLimit(BaseAction):
    channel_id: int | None
    name: str
    limit: int
    kind: ActionKind = ActionKind.SET_USER_LIMIT


@dataclass(frozen=True)
class SeedChannel(BaseAction):
    channel_id: int | None
    name: str
    seed_title: str
    kind: ActionKind = ActionKind.SEED_CHANNEL


@dataclass(frozen=True)
class SetAfkChannel(BaseAction):
    name: str
    timeout_seconds: int = 300
    kind: ActionKind = ActionKind.SET_AFK_CHANNEL


@dataclass(frozen=True)
class WarningAction(BaseAction):
    message: str
    kind: ActionKind = ActionKind.WARNING
