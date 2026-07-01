from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ManagedResource:
    kind: str
    name: str
    resource_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "resource_id": self.resource_id,
        }


@dataclass(frozen=True)
class ImperialSetupState:
    schema_version: int = SCHEMA_VERSION
    active_profile: str = "personal"
    managed_resources: tuple[ManagedResource, ...] = field(default_factory=tuple)
    last_plan_summary: dict[str, int] = field(default_factory=dict)
    last_reconcile_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_profile": self.active_profile,
            "managed_resources": [
                item.to_dict() for item in self.managed_resources
            ],
            "last_plan_summary": dict(self.last_plan_summary),
            "last_reconcile_at": self.last_reconcile_at,
        }


def migrate_state(raw: dict[str, Any] | None) -> ImperialSetupState:
    if not raw:
        return ImperialSetupState()
    resources = []
    for item in raw.get("managed_resources", []):
        try:
            resources.append(
                ManagedResource(
                    kind=str(item["kind"]),
                    name=str(item["name"]),
                    resource_id=int(item["resource_id"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return ImperialSetupState(
        schema_version=SCHEMA_VERSION,
        active_profile=str(raw.get("active_profile") or "personal"),
        managed_resources=tuple(resources),
        last_plan_summary=dict(raw.get("last_plan_summary") or {}),
        last_reconcile_at=str(raw.get("last_reconcile_at") or ""),
    )
