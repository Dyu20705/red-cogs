from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

COG_NAMES = (
    "ImperialSetup",
    "DevelopmentOps",
    "BotOps",
    "ImperialAutomation",
    "StudyOps",
    "MusicStatus",
)
SENSITIVE_ENV = (
    "DEVELOPMENTOPS_WEBHOOK_SECRET",
    "DEVELOPMENTOPS_GITHUB_TOKEN",
)


@dataclass(frozen=True)
class HealthSnapshot:
    ready: bool
    latency_ms: int
    uptime_seconds: int
    cogs: Mapping[str, bool]
    audio_loaded: bool
    developmentops_receiver: str
    developmentops_secret_present: bool
    github_token_present: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_lines(self) -> list[str]:
        lines = [
            "**BOTOPS HEALTH**",
            "",
            f"Ready: `{self.ready}`",
            f"Latency: `{self.latency_ms} ms`",
            f"Uptime: `{_format_uptime(self.uptime_seconds)}`",
            f"Audio loaded: `{self.audio_loaded}`",
            f"DevelopmentOps receiver: `{self.developmentops_receiver}`",
            f"DevelopmentOps signing value present: `{self.developmentops_secret_present}`",
            f"GitHub credential present: `{self.github_token_present}`",
            "",
            "**Cog state**",
        ]
        for name, loaded in self.cogs.items():
            lines.append(f"- {name}: `{'loaded' if loaded else 'not loaded'}`")
        if self.warnings:
            lines.extend(["", "**Warnings**"])
            lines.extend(f"- {warning}" for warning in self.warnings)
        return lines


def build_health_snapshot(bot, *, environ: Mapping[str, str] | None = None) -> HealthSnapshot:
    env = os.environ if environ is None else environ
    started = getattr(bot, "uptime", None)
    if not isinstance(started, datetime):
        started = datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    cogs = {name: bot.get_cog(name) is not None for name in COG_NAMES}
    devops = bot.get_cog("DevelopmentOps")
    receiver = "not loaded"
    if devops is not None:
        web_site = getattr(devops, "web_site", None)
        error = getattr(devops, "web_start_error", None)
        queue = getattr(devops, "webhook_queue", None)
        queue_size = queue.qsize() if queue is not None else 0
        receiver = "listening" if web_site is not None else f"not listening: {error or 'starting'}"
        receiver = f"{receiver}; queue={queue_size}"

    warnings: list[str] = []
    if not cogs.get("DevelopmentOps"):
        warnings.append("DevelopmentOps is not loaded.")
    if cogs.get("DevelopmentOps") and not bool(env.get("DEVELOPMENTOPS_WEBHOOK_SECRET")):
        warnings.append("DevelopmentOps receiver cannot verify GitHub webhooks without a signing value.")

    return HealthSnapshot(
        ready=bool(bot.is_ready()),
        latency_ms=round(float(getattr(bot, "latency", 0.0)) * 1000),
        uptime_seconds=max(0, int((datetime.now(timezone.utc) - started).total_seconds())),
        cogs=cogs,
        audio_loaded=bot.get_cog("Audio") is not None,
        developmentops_receiver=receiver,
        developmentops_secret_present=bool(env.get("DEVELOPMENTOPS_WEBHOOK_SECRET")),
        github_token_present=bool(env.get("DEVELOPMENTOPS_GITHUB_TOKEN")),
        warnings=tuple(warnings),
    )


def _format_uptime(seconds: int) -> str:
    days, seconds = divmod(max(0, int(seconds)), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"
