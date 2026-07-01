from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks
from redbot.core import Config, commands

try:
    import lavalink
except ImportError:
    lavalink = None


VIETNAM_TZ = ZoneInfo("Asia/Bangkok")
COMMAND_PAGE_LIMIT = 1850
COG_PRIORITY = (
    "Audio",
    "ImperialAutomation",
    "MusicStatus",
    "BotOps",
    "DevelopmentOps",
    "ImperialSetup",
    "StudyOps",
)


class MusicStatus(commands.Cog):
    """Maintain live Music-Bot health and command panels."""

    __red_end_user_data_statement__ = (
        "This cog stores Discord guild, channel, status-message, and "
        "command-index message IDs."
    )

    def __init__(self, bot):
        self.bot = bot
        self.loaded_at = datetime.now(timezone.utc)

        self.config = Config.get_conf(
            self,
            identifier=28092005,
            force_registration=True,
        )

        self.config.register_guild(
            channel_id=None,
            message_id=None,
            command_message_ids=[],
        )

        self.status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="musicstatus")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def musicstatus(self, ctx: commands.Context):
        """Configure the Music-Bot status and live command panels."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @musicstatus.command(name="setchannel")
    async def set_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """Choose the channel for both status and command panels."""

        missing = self._missing_channel_permissions(channel, ctx.guild.me)
        if missing:
            await ctx.send(
                "❌ Bot đang thiếu quyền trong "
                f"{channel.mention}: **{', '.join(missing)}**"
            )
            return

        guild_config = self.config.guild(ctx.guild)
        await guild_config.channel_id.set(channel.id)
        await guild_config.message_id.clear()
        await guild_config.command_message_ids.set([])

        status_ok, commands_ok = await self.publish_all(ctx.guild)

        if status_ok and commands_ok:
            await ctx.send(
                f"✅ Đã đặt channel dashboard thành {channel.mention}.\n"
                "Bảng trạng thái và danh mục command sẽ tự cập nhật mỗi 1 giờ."
            )
        else:
            await ctx.send(
                f"⚠️ Đã lưu {channel.mention}, nhưng chưa thể tạo đầy đủ dashboard. "
                "Hãy kiểm tra quyền rồi chạy "
                f"`{ctx.clean_prefix}musicstatus now`."
            )

    @musicstatus.command(name="now", aliases=["refresh"])
    async def update_now(self, ctx: commands.Context):
        """Refresh both status and command panels immediately."""

        channel_id = await self.config.guild(ctx.guild).channel_id()
        if not channel_id:
            await ctx.send(
                "❌ Chưa thiết lập channel.\n"
                f"Dùng `{ctx.clean_prefix}musicstatus setchannel #bot-status`."
            )
            return

        status_ok, commands_ok = await self.publish_all(ctx.guild)
        if status_ok and commands_ok:
            await ctx.tick()
        else:
            await ctx.send("❌ Không thể cập nhật đầy đủ dashboard Music-Bot.")

    @musicstatus.command(name="commands", aliases=["command", "cmds"])
    async def update_commands(self, ctx: commands.Context):
        """Refresh the live command index only."""

        if await self.publish_commands(ctx.guild):
            await ctx.tick()
        else:
            await ctx.send("❌ Không thể cập nhật bảng command.")

    @musicstatus.command(name="reset")
    async def reset_status(self, ctx: commands.Context):
        """Delete tracked dashboard messages and clear configuration."""

        guild_config = self.config.guild(ctx.guild)
        channel_id = await guild_config.channel_id()
        channel = ctx.guild.get_channel(channel_id) if channel_id else None

        if isinstance(channel, discord.TextChannel):
            message_ids = []
            status_message_id = await guild_config.message_id()
            if status_message_id:
                message_ids.append(status_message_id)
            message_ids.extend(await guild_config.command_message_ids())

            for message_id in message_ids:
                with contextlib.suppress(
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()

        await guild_config.clear()
        await ctx.send("✅ Đã xóa cấu hình và dashboard Music-Bot Status.")

    # ---------------------------------------------------------
    # STATUS DATA
    # ---------------------------------------------------------

    def get_uptime(self) -> str:
        """Return uptime for the whole Red instance."""

        started_at = getattr(self.bot, "uptime", None)
        if not isinstance(started_at, datetime):
            started_at = self.loaded_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        seconds = max(
            0,
            int((datetime.now(timezone.utc) - started_at).total_seconds()),
        )
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, _ = divmod(seconds, 60)

        if days:
            return f"{days}d {hours:02d}h {minutes:02d}m"
        return f"{hours:02d}h {minutes:02d}m"

    def get_audio_information(
        self,
        guild: discord.Guild,
    ) -> tuple[str, int]:
        """Return Audio-node status and active voice-room count."""

        audio_cog = self.bot.get_cog("Audio")
        if audio_cog is None:
            return "Not loaded", 0
        if lavalink is None:
            return "Unavailable", 0

        try:
            players = list(lavalink.all_players())
        except Exception:
            players = []

        active_players = []
        for player in players:
            player_guild = getattr(player, "guild", None)
            channel = getattr(player, "channel", None)
            if (
                player_guild is not None
                and player_guild.id == guild.id
                and channel is not None
            ):
                active_players.append(player)

        node_ready = False
        with contextlib.suppress(Exception):
            nodes = list(lavalink.all_nodes())
            node_ready = any(
                bool(getattr(node, "ready", False))
                for node in nodes
            )

        if not node_ready:
            node_ready = any(
                bool(getattr(getattr(player, "node", None), "ready", False))
                for player in players
            )

        return (
            "Connected" if node_ready else "Disconnected",
            len(active_players),
        )

    def build_status_message(self, guild: discord.Guild) -> str:
        latency_ms = round(self.bot.latency * 1000)
        audio_node, active_rooms = self.get_audio_information(guild)

        if not self.bot.is_ready():
            state = "🔴 Offline"
        elif latency_ms >= 500 or audio_node == "Disconnected":
            state = "🟡 Degraded"
        else:
            state = "🟢 Online"

        current_time = datetime.now(VIETNAM_TZ).strftime("%H:%M")

        return (
            "🤖 **MUSIC-BOT STATUS**\n\n"
            f"State: {state}\n"
            f"Uptime: `{self.get_uptime()}`\n"
            f"Latency: `{latency_ms} ms`\n"
            f"Audio node: `{audio_node}`\n"
            f"Loaded cogs: `{len(self.bot.cogs)}`\n"
            f"Active voice rooms: `{active_rooms}`\n"
            f"Last check: `{current_time}`"
        )

    # ---------------------------------------------------------
    # LIVE COMMAND INDEX
    # ---------------------------------------------------------

    async def _guild_prefix(self, guild: discord.Guild) -> str:
        with contextlib.suppress(Exception):
            prefixes = await self.bot.get_valid_prefixes(guild)
            for prefix in prefixes:
                if isinstance(prefix, str) and not prefix.startswith("<@"):
                    return prefix
        return "!"

    def _root_commands_by_cog(self) -> dict[str, list[str]]:
        grouped: dict[str, set[str]] = {}

        for command in self.bot.walk_commands():
            if command.parent is not None:
                continue
            if bool(getattr(command, "hidden", False)):
                continue
            if not bool(getattr(command, "enabled", True)):
                continue

            name = str(getattr(command, "qualified_name", "")).strip()
            if not name:
                continue

            cog_name = str(getattr(command, "cog_name", None) or "Core")
            grouped.setdefault(cog_name, set()).add(name)

        return {
            cog_name: sorted(names, key=str.casefold)
            for cog_name, names in grouped.items()
        }

    async def build_command_pages(self, guild: discord.Guild) -> list[str]:
        prefix = await self._guild_prefix(guild)
        grouped = self._root_commands_by_cog()

        priority = [name for name in COG_PRIORITY if name in grouped]
        remaining = sorted(
            (name for name in grouped if name not in COG_PRIORITY),
            key=str.casefold,
        )
        ordered_cogs = priority + remaining

        sync_time = datetime.now(VIETNAM_TZ).strftime("%H:%M")
        pages = [
            "📚 **BOT COMMANDS — LIVE INDEX**\n"
            f"Dùng `{prefix}help <command>` để xem cú pháp chi tiết.\n"
            "Danh sách này được tạo trực tiếp từ các cog đang load."
        ]

        for cog_name in ordered_cogs:
            command_tokens = [
                f"`{prefix}{name}`"
                for name in grouped[cog_name]
            ]
            section_lines = [f"\n**{cog_name}**"]

            current_line = ""
            for token in command_tokens:
                candidate = f"{current_line} {token}".strip()
                if len(candidate) > 180:
                    if current_line:
                        section_lines.append(current_line)
                    current_line = token
                else:
                    current_line = candidate
            if current_line:
                section_lines.append(current_line)

            for line in section_lines:
                if len(pages[-1]) + len(line) + 1 > COMMAND_PAGE_LIMIT:
                    pages.append("📚 **BOT COMMANDS — CONTINUED**")
                pages[-1] += "\n" + line

        pages[-1] += (
            f"\n\nCommands: `{sum(len(names) for names in grouped.values())}`"
            f" • Loaded cogs: `{len(self.bot.cogs)}`"
            f" • Last sync: `{sync_time}`"
        )
        return pages

    # ---------------------------------------------------------
    # MESSAGE UPDATE
    # ---------------------------------------------------------

    @staticmethod
    def _missing_channel_permissions(
        channel: discord.TextChannel,
        member: discord.Member | None,
    ) -> list[str]:
        if member is None:
            return ["Guild Member"]

        permissions = channel.permissions_for(member)
        checks = (
            ("View Channel", permissions.view_channel),
            ("Send Messages", permissions.send_messages),
            ("Read Message History", permissions.read_message_history),
        )
        return [name for name, allowed in checks if not allowed]

    async def _dashboard_channel(
        self,
        guild: discord.Guild,
    ) -> tuple[discord.TextChannel | None, object]:
        guild_config = self.config.guild(guild)
        channel_id = await guild_config.channel_id()
        if not channel_id:
            return None, guild_config

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await guild_config.channel_id.clear()
            await guild_config.message_id.clear()
            await guild_config.command_message_ids.set([])
            return None, guild_config

        if self._missing_channel_permissions(channel, guild.me):
            return None, guild_config

        return channel, guild_config

    async def publish_status(self, guild: discord.Guild) -> bool:
        channel, guild_config = await self._dashboard_channel(guild)
        if channel is None:
            return False

        message_id = await guild_config.message_id()
        content = self.build_status_message(guild)

        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(content=content)
                return True
            except discord.NotFound:
                await guild_config.message_id.clear()
            except (discord.Forbidden, discord.HTTPException):
                return False

        try:
            message = await channel.send(content)
        except (discord.Forbidden, discord.HTTPException):
            return False

        await guild_config.message_id.set(message.id)
        return True

    async def publish_commands(self, guild: discord.Guild) -> bool:
        channel, guild_config = await self._dashboard_channel(guild)
        if channel is None:
            return False

        pages = await self.build_command_pages(guild)
        existing_ids = [
            int(message_id)
            for message_id in await guild_config.command_message_ids()
        ]
        updated_ids: list[int] = []

        for index, content in enumerate(pages):
            message = None
            if index < len(existing_ids):
                with contextlib.suppress(
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    message = await channel.fetch_message(existing_ids[index])
                    await message.edit(content=content)

            if message is None:
                try:
                    message = await channel.send(content)
                except (discord.Forbidden, discord.HTTPException):
                    return False

            updated_ids.append(message.id)

        for message_id in existing_ids[len(pages):]:
            with contextlib.suppress(
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                message = await channel.fetch_message(message_id)
                await message.delete()

        await guild_config.command_message_ids.set(updated_ids)
        return True

    async def publish_all(self, guild: discord.Guild) -> tuple[bool, bool]:
        status_ok = await self.publish_status(guild)
        commands_ok = await self.publish_commands(guild)
        return status_ok, commands_ok

    # ---------------------------------------------------------
    # AUTOMATIC LOOP
    # ---------------------------------------------------------

    @tasks.loop(hours=1)
    async def status_loop(self):
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            if not data.get("channel_id"):
                continue

            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            with contextlib.suppress(Exception):
                await self.publish_all(guild)

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()
