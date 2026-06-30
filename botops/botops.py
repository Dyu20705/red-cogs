\
from __future__ import annotations

import contextlib
import io
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.data_manager import cog_data_path


VN_TZ = timezone(timedelta(hours=7), name="UTC+7")

CHANNEL_KEYS = {
    "audit": "audit_channel_id",
    "errors": "errors_channel_id",
    "logs": "logs_channel_id",
}

EXPECTED_COMMAND_ERRORS = (
    commands.CommandNotFound,
    commands.UserInputError,
    commands.CheckFailure,
    commands.CommandOnCooldown,
    commands.DisabledCommand,
)

SECRET_PATTERNS = (
    (
        re.compile(
            r"https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/"
            r"\d+/[A-Za-z0-9._-]+",
            re.IGNORECASE,
        ),
        "[REDACTED_DISCORD_WEBHOOK]",
    ),
    (
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(
            r"\b(?:mfa\.[A-Za-z0-9_-]{20,}|"
            r"[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,})\b"
        ),
        "[REDACTED_DISCORD_TOKEN]",
    ),
    (
        re.compile(
            r"(?im)^(\s*[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|"
            r"PRIVATE_KEY|WEBHOOK)[A-Z0-9_]*\s*=\s*).+$"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)\b(authorization\s*:\s*(?:bearer|bot)\s+)[^\s,;]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b((?:token|secret|password|passwd|api[_-]?key)\s*[:=]\s*)"
            r"([\"']?)[^,\s\"']+\2"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)([?&](?:token|access_token|api_key|key|secret|password)=)[^&#\s]+"
        ),
        r"\1[REDACTED]",
    ),
)


class BotOps(commands.Cog):
    """Structured operational audit and error reporting."""

    __red_end_user_data_statement__ = (
        "This cog stores guild channel IDs, retention settings, and daily incident counters. "
        "Incident logs may contain Discord user, guild, channel, cog, and command identifiers."
    )

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=2809200502,
            force_registration=True,
        )
        self.config.register_guild(
            audit_channel_id=None,
            errors_channel_id=None,
            logs_channel_id=None,
            retention_days=14,
            counters={"date": "", "AUD": 0, "ERR": 0},
        )

        self.log_root = cog_data_path(self) / "incident_logs"
        self.log_root.mkdir(parents=True, exist_ok=True)
        self.cleanup_loop.start()

    def cog_unload(self):
        self.cleanup_loop.cancel()

    # ------------------------------------------------------------------
    # Configuration commands
    # ------------------------------------------------------------------

    @commands.group(name="botops")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def botops(self, ctx: commands.Context):
        """Configure operational audit and incident logging."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @botops.command(name="set")
    async def set_channel(
        self,
        ctx: commands.Context,
        kind: str,
        channel: discord.TextChannel,
    ):
        """Set a channel: audit, errors, or logs."""

        kind = kind.lower().strip()
        config_key = CHANNEL_KEYS.get(kind)

        if config_key is None:
            await ctx.send("❌ Loại channel phải là: `audit`, `errors`, hoặc `logs`.")
            return

        missing = self._missing_permissions(channel, require_attachment=(kind == "logs"))
        if missing:
            await ctx.send(
                f"❌ Bot thiếu quyền trong {channel.mention}: **{', '.join(missing)}**"
            )
            return

        guild_conf = self.config.guild(ctx.guild)
        old_id = await getattr(guild_conf, config_key)()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None

        await getattr(guild_conf, config_key).set(channel.id)

        before = old_channel.mention if old_channel else "none"
        await ctx.send(f"✅ Đã đặt `#{kind}` thành {channel.mention}.")

        # Do not recursively audit the first audit-channel assignment.
        if kind != "audit" or old_id:
            await self.audit(
                guild=ctx.guild,
                user=ctx.author,
                action=f"Changed BotOps {kind} channel",
                before=before,
                after=channel.mention,
                result="Success",
            )

    @botops.command(name="retention")
    async def set_retention(self, ctx: commands.Context, days: int):
        """Set #bot-logs retention between 7 and 30 days."""

        if not 7 <= days <= 30:
            await ctx.send("❌ Retention phải nằm trong khoảng **7–30 ngày**.")
            return

        old_days = await self.config.guild(ctx.guild).retention_days()
        await self.config.guild(ctx.guild).retention_days.set(days)

        await self.audit(
            guild=ctx.guild,
            user=ctx.author,
            action="Changed bot log retention",
            before=f"{old_days} days",
            after=f"{days} days",
            result="Success",
        )
        await ctx.send(f"✅ Log do bot gửi sẽ được xóa sau **{days} ngày**.")

    @botops.command(name="status")
    async def configuration_status(self, ctx: commands.Context):
        """Show current BotOps configuration."""

        data = await self.config.guild(ctx.guild).all()

        def channel_value(key: str) -> str:
            channel_id = data.get(key)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            return channel.mention if channel else "Not configured"

        await ctx.send(
            "**🧰 BOTOPS CONFIGURATION**\n\n"
            f"Audit: {channel_value('audit_channel_id')}\n"
            f"Errors: {channel_value('errors_channel_id')}\n"
            f"Logs: {channel_value('logs_channel_id')}\n"
            f"Log retention: `{data.get('retention_days', 14)} days`",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @botops.command(name="test")
    async def test_pipeline(self, ctx: commands.Context, kind: str = "all"):
        """Test audit/error/log delivery."""

        kind = kind.lower().strip()
        if kind not in {"audit", "error", "all"}:
            await ctx.send("❌ Chọn `audit`, `error`, hoặc `all`.")
            return

        if kind in {"audit", "all"}:
            await self.audit(
                guild=ctx.guild,
                user=ctx.author,
                action="Tested BotOps audit pipeline",
                before="idle",
                after="test event",
                result="Success",
            )

        if kind in {"error", "all"}:
            try:
                raise RuntimeError("Synthetic BotOps test error; no action is required.")
            except RuntimeError as exc:
                await self.report_error(
                    guild=ctx.guild,
                    operation="Test BotOps incident pipeline",
                    error=exc,
                    ctx=ctx,
                    reason="Synthetic test exception.",
                    suggested_fix="No fix required. This incident was generated by an administrator.",
                )

        await ctx.tick()

    @botops.command(name="cleanupnow")
    async def cleanup_now(self, ctx: commands.Context):
        """Run log retention cleanup immediately."""

        deleted_messages, deleted_files = await self._cleanup_guild(ctx.guild)
        await ctx.send(
            f"✅ Cleanup hoàn tất: `{deleted_messages}` Discord messages, "
            f"`{deleted_files}` local files."
        )

    # ------------------------------------------------------------------
    # Public API for other cogs
    # ------------------------------------------------------------------

    async def audit(
        self,
        *,
        guild: discord.Guild,
        user: Union[discord.Member, discord.User, str],
        action: str,
        before: Any,
        after: Any,
        result: str = "Success",
    ) -> str:
        """Send one structured configuration-change audit record."""

        incident = await self._next_incident(guild, "AUD")
        channel = await self._configured_channel(guild, "audit_channel_id")

        if channel is None:
            return incident

        user_name = (
            getattr(user, "display_name", None)
            or getattr(user, "name", None)
            or str(user)
        )
        content = (
            "🛠 **CONFIG CHANGE**\n"
            f"User: {self._short(user_name, 100)}\n"
            f"Action: {self._short(action, 300)}\n"
            f"From: {self._short(before, 300)}\n"
            f"To: {self._short(after, 300)}\n"
            f"Result: {self._short(result, 100)}\n"
            f"Incident: `{incident}`\n"
            f"Time: `{self._now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}`"
        )

        with contextlib.suppress(discord.HTTPException):
            await channel.send(
                self.sanitize(content),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return incident

    async def report_error(
        self,
        *,
        guild: discord.Guild,
        operation: str,
        error: BaseException,
        ctx: Optional[commands.Context] = None,
        reason: Optional[str] = None,
        suggested_fix: Optional[str] = None,
        cog_name: Optional[str] = None,
        command_name: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a concise incident and store/send its sanitized traceback."""

        incident = await self._next_incident(guild, "ERR")
        original = self._unwrap_error(error)
        status, code = self._discord_status(original)

        if reason is None:
            reason = self._friendly_reason(original)
        if suggested_fix is None:
            suggested_fix = self._suggested_fix(original, code)

        if ctx is not None:
            if cog_name is None and ctx.cog is not None:
                cog_name = ctx.cog.__class__.__name__
            if command_name is None and ctx.command is not None:
                command_name = ctx.command.qualified_name

        cog_name = cog_name or "Unknown"
        command_name = command_name or "Unknown"

        errors_channel = await self._configured_channel(guild, "errors_channel_id")
        logs_channel = await self._configured_channel(guild, "logs_channel_id")

        summary = (
            f"🔴 **BOT ERROR — {incident}**\n\n"
            f"Operation: {self._short(operation, 350)}\n"
            f"Discord status: `{status}`\n"
            f"Discord code: `{code}`\n"
            f"Reason: {self._short(reason, 500)}\n\n"
            "**Suggested fix:**\n"
            f"{self._short(suggested_fix, 600)}"
        )

        if logs_channel is not None:
            summary += f"\n\nFull traceback: {logs_channel.mention}"

        if errors_channel is not None:
            with contextlib.suppress(discord.HTTPException):
                await errors_channel.send(
                    self.sanitize(summary),
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        log_text = self._build_incident_log(
            incident=incident,
            guild=guild,
            operation=operation,
            error=original,
            ctx=ctx,
            status=status,
            code=code,
            reason=reason,
            suggested_fix=suggested_fix,
            cog_name=cog_name,
            command_name=command_name,
            extra=extra,
        )
        log_path = self._write_incident_file(guild.id, incident, log_text)

        if logs_channel is not None:
            await self._send_detailed_log(
                logs_channel,
                incident=incident,
                log_text=log_text,
                log_path=log_path,
            )

        return incident

    # ------------------------------------------------------------------
    # Automatic command-error capture
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: BaseException):
        """Capture unexpected command failures not handled by their own cog."""

        if ctx.guild is None or isinstance(error, EXPECTED_COMMAND_ERRORS):
            return

        command = ctx.command
        if command is not None:
            has_local_handler = getattr(command, "has_error_handler", None)
            if callable(has_local_handler) and has_local_handler():
                return

        cog = ctx.cog
        if cog is not None:
            has_cog_handler = getattr(cog, "has_error_handler", None)
            if callable(has_cog_handler) and has_cog_handler():
                return

        original = self._unwrap_error(error)
        await self.report_error(
            guild=ctx.guild,
            operation=f"Run command {ctx.command.qualified_name if ctx.command else 'unknown'}",
            error=original,
            ctx=ctx,
        )

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    @tasks.loop(hours=24)
    async def cleanup_loop(self):
        all_guilds = await self.config.all_guilds()

        for guild_id in all_guilds:
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue
            with contextlib.suppress(Exception):
                await self._cleanup_guild(guild)

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self):
        await self.bot.wait_until_ready()

    async def _cleanup_guild(self, guild: discord.Guild) -> Tuple[int, int]:
        retention_days = await self.config.guild(guild).retention_days()
        retention_days = max(7, min(30, int(retention_days)))
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        deleted_messages = 0
        log_channel = await self._configured_channel(guild, "logs_channel_id")

        if log_channel is not None:
            try:
                async for message in log_channel.history(
                    limit=None,
                    before=cutoff,
                    oldest_first=True,
                ):
                    if (
                        self.bot.user is not None
                        and message.author.id == self.bot.user.id
                        and not message.pinned
                    ):
                        with contextlib.suppress(discord.HTTPException):
                            await message.delete()
                            deleted_messages += 1
            except discord.HTTPException:
                pass

        deleted_files = 0
        guild_dir = self.log_root / str(guild.id)
        if guild_dir.exists():
            cutoff_timestamp = cutoff.timestamp()
            for file_path in guild_dir.glob("*.log"):
                with contextlib.suppress(OSError):
                    if file_path.stat().st_mtime < cutoff_timestamp:
                        file_path.unlink()
                        deleted_files += 1

        return deleted_messages, deleted_files

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(VN_TZ)

    @staticmethod
    def sanitize(value: Any) -> str:
        text = str(value)
        for pattern, replacement in SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _short(self, value: Any, limit: int) -> str:
        text = self.sanitize(value).replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"

    def _missing_permissions(
        self,
        channel: discord.TextChannel,
        *,
        require_attachment: bool = False,
    ):
        me = channel.guild.me
        if me is None:
            return ["Bot member unavailable"]

        permissions = channel.permissions_for(me)
        missing = []

        if not permissions.view_channel:
            missing.append("View Channel")
        if not permissions.send_messages:
            missing.append("Send Messages")
        if not permissions.read_message_history:
            missing.append("Read Message History")
        if require_attachment and not permissions.attach_files:
            missing.append("Attach Files")

        return missing

    async def _configured_channel(
        self,
        guild: discord.Guild,
        config_key: str,
    ) -> Optional[discord.TextChannel]:
        channel_id = await getattr(self.config.guild(guild), config_key)()
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    async def _next_incident(self, guild: discord.Guild, prefix: str) -> str:
        date_key = self._now().strftime("%Y%m%d")

        async with self.config.guild(guild).counters() as counters:
            if counters.get("date") != date_key:
                counters.clear()
                counters.update({"date": date_key, "AUD": 0, "ERR": 0})

            counters[prefix] = int(counters.get(prefix, 0)) + 1
            sequence = counters[prefix]

        return f"{prefix}-{date_key}-{sequence:03d}"

    @staticmethod
    def _unwrap_error(error: BaseException) -> BaseException:
        original = getattr(error, "original", None)
        return original if isinstance(original, BaseException) else error

    @staticmethod
    def _discord_status(error: BaseException) -> Tuple[str, str]:
        if isinstance(error, discord.HTTPException):
            return str(getattr(error, "status", "Unknown")), str(
                getattr(error, "code", "Unknown")
            )
        return "N/A", "N/A"

    @staticmethod
    def _friendly_reason(error: BaseException) -> str:
        if isinstance(error, discord.Forbidden):
            code = getattr(error, "code", None)
            if code == 50001:
                return "Bot cannot access the target Discord resource."
            if code == 50013:
                return "Bot is missing one or more required Discord permissions."
            return "Discord rejected the operation because access is forbidden."

        if isinstance(error, discord.NotFound):
            return "The target Discord resource no longer exists or is not visible to the bot."

        if isinstance(error, discord.HTTPException):
            text = getattr(error, "text", None)
            return text or str(error)

        return str(error) or error.__class__.__name__

    @staticmethod
    def _suggested_fix(error: BaseException, code: str) -> str:
        if code == "50001":
            return (
                "Grant View Channel and the operation-specific permission to the bot role "
                "in the target channel/category permission overrides."
            )
        if code == "50013":
            return (
                "Grant the exact missing permission to the bot role and ensure the bot's "
                "highest role is above any role it must manage."
            )
        if code in {"10003", "10008"}:
            return (
                "Verify that the configured channel/message still exists, then update the "
                "stored channel or message ID."
            )
        if isinstance(error, discord.NotFound):
            return "Reconfigure the deleted or inaccessible Discord resource."
        if isinstance(error, discord.HTTPException):
            return "Check Discord permissions, target IDs, and the operation parameters."
        return "Inspect the traceback in #bot-logs and fix the originating cog or command."

    def _build_incident_log(
        self,
        *,
        incident: str,
        guild: discord.Guild,
        operation: str,
        error: BaseException,
        ctx: Optional[commands.Context],
        status: str,
        code: str,
        reason: str,
        suggested_fix: str,
        cog_name: str,
        command_name: str,
        extra: Optional[Dict[str, Any]],
    ) -> str:
        channel_name = "Unknown"
        channel_id = "Unknown"
        user_name = "Unknown"
        user_id = "Unknown"

        if ctx is not None:
            channel_name = getattr(ctx.channel, "name", str(ctx.channel))
            channel_id = str(getattr(ctx.channel, "id", "Unknown"))
            user_name = getattr(ctx.author, "display_name", str(ctx.author))
            user_id = str(getattr(ctx.author, "id", "Unknown"))

        trace = "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__,
            )
        ).strip()

        if not trace:
            trace = f"{error.__class__.__name__}: {error}"

        lines = [
            f"Incident: {incident}",
            f"Time: {self._now().isoformat()}",
            f"Guild: {guild.name} ({guild.id})",
            f"Channel: {channel_name} ({channel_id})",
            f"User: {user_name} ({user_id})",
            f"Cog: {cog_name}",
            f"Command: {command_name}",
            f"Operation: {operation}",
            f"Discord status: {status}",
            f"Discord code: {code}",
            f"Exception: {error.__class__.__name__}",
            f"Reason: {reason}",
            f"Suggested fix: {suggested_fix}",
        ]

        if extra:
            lines.append("Extra context:")
            for key, value in extra.items():
                lines.append(f"  {key}: {value}")

        lines.extend(
            [
                "",
                "----- TRACEBACK -----",
                trace,
                "",
            ]
        )

        return self.sanitize("\n".join(lines))

    def _write_incident_file(
        self,
        guild_id: int,
        incident: str,
        log_text: str,
    ) -> Path:
        guild_dir = self.log_root / str(guild_id)
        guild_dir.mkdir(parents=True, exist_ok=True)

        log_path = guild_dir / f"{incident}.log"
        log_path.write_text(log_text, encoding="utf-8")
        return log_path

    async def _send_detailed_log(
        self,
        channel: discord.TextChannel,
        *,
        incident: str,
        log_text: str,
        log_path: Path,
    ):
        header = (
            f"📄 **INCIDENT LOG — {incident}**\n"
            f"Time: `{self._now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}`"
        )

        try:
            if len(log_text) <= 1600:
                safe_inline = log_text.replace("```", "[code-fence]")
                await channel.send(
                    f"{header}\n```py\n{safe_inline}\n```",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return

            payload = io.BytesIO(log_text.encode("utf-8"))
            await channel.send(
                header,
                file=discord.File(payload, filename=log_path.name),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            # Keep the sanitized local file even when Discord delivery fails.
            return
