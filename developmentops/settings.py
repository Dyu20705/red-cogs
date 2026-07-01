from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class DevelopmentOpsSettings:
    webhook_secret: str = ""
    github_token: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
    receiver_enabled: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "DevelopmentOpsSettings":
        env = os.environ if environ is None else environ
        warnings: list[str] = []

        webhook_secret = env.get("DEVELOPMENTOPS_WEBHOOK_SECRET", "")
        github_token = env.get("DEVELOPMENTOPS_GITHUB_TOKEN", "")
        host = (env.get("DEVELOPMENTOPS_HOST") or "127.0.0.1").strip()
        raw_port = (env.get("DEVELOPMENTOPS_PORT") or "8765").strip()
        receiver_enabled = True

        if not _valid_host(host):
            warnings.append(
                "DEVELOPMENTOPS_HOST is invalid; receiver disabled safely."
            )
            receiver_enabled = False
            host = "127.0.0.1"

        try:
            port = int(raw_port)
        except ValueError:
            warnings.append(
                "DEVELOPMENTOPS_PORT must be an integer from 1 to 65535; receiver disabled safely."
            )
            receiver_enabled = False
            port = 8765
        else:
            if not 1 <= port <= 65535:
                warnings.append(
                    "DEVELOPMENTOPS_PORT must be from 1 to 65535; receiver disabled safely."
                )
                receiver_enabled = False
                port = 8765

        return cls(
            webhook_secret=webhook_secret,
            github_token=github_token,
            host=host,
            port=port,
            receiver_enabled=receiver_enabled,
            warnings=tuple(warnings),
        )


def _valid_host(host: str) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return all(part and part.replace("-", "").isalnum() for part in host.split("."))
