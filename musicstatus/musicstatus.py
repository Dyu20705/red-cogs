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


class MusicStatus(commands.Cog):
    """Tự động đăng trạng thái Music-Bot mỗi giờ."""

    __red_end_user_data_statement__ = (
        "This cog stores Discord guild, channel, and status message IDs."
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
        """Cấu hình bảng trạng thái Music-Bot."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @musicstatus.command(name="setchannel")
    async def set_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """Chọn channel đăng trạng thái."""

        permissions = channel.permissions_for(ctx.guild.me)

        missing = []

        if not permissions.view_channel:
            missing.append("View Channel")

        if not permissions.send_messages:
            missing.append("Send Messages")

        if not permissions.read_message_history:
            missing.append("Read Message History")

        if missing:
            await ctx.send(
                "❌ Bot đang thiếu quyền trong "
                f"{channel.mention}: **{', '.join(missing)}**"
            )
            return

        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await self.config.guild(ctx.guild).message_id.clear()

        await self.publish_status(ctx.guild)

        await ctx.send(
            f"✅ Đã đặt channel trạng thái thành {channel.mention}.\n"
            "Bảng trạng thái sẽ được cập nhật mỗi 1 giờ."
        )

    @musicstatus.command(name="now")
    async def update_now(self, ctx: commands.Context):
        """Cập nhật trạng thái ngay lập tức."""

        channel_id = await self.config.guild(ctx.guild).channel_id()

        if not channel_id:
            await ctx.send(
                f"❌ Chưa thiết lập channel.\n"
                f"Dùng `{ctx.clean_prefix}musicstatus setchannel #bot-status`."
            )
            return

        success = await self.publish_status(ctx.guild)

        if success:
            await ctx.tick()
        else:
            await ctx.send("❌ Không thể cập nhật bảng trạng thái.")

    @musicstatus.command(name="reset")
    async def reset_status(self, ctx: commands.Context):
        """Xóa cấu hình bảng trạng thái."""

        await self.config.guild(ctx.guild).clear()

        await ctx.send("✅ Đã xóa cấu hình Music-Bot Status.")

    # ---------------------------------------------------------
    # STATUS DATA
    # ---------------------------------------------------------

    def get_uptime(self) -> str:
        """Lấy uptime của toàn bộ Red instance."""

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
        """Trả về trạng thái audio node và số voice room hoạt động."""

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

        # Kiểm tra tất cả Lavalink nodes, kể cả khi chưa có người nghe nhạc.
        with contextlib.suppress(Exception):
            nodes = list(lavalink.all_nodes())
            node_ready = any(
                bool(getattr(node, "ready", False))
                for node in nodes
            )

        # Fallback nếu phiên bản Lavalink không có all_nodes().
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
    # MESSAGE UPDATE
    # ---------------------------------------------------------

    async def publish_status(self, guild: discord.Guild) -> bool:
        guild_config = self.config.guild(guild)

        channel_id = await guild_config.channel_id()
        message_id = await guild_config.message_id()

        if not channel_id:
            return False

        channel = guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            await guild_config.channel_id.clear()
            await guild_config.message_id.clear()
            return False

        me = guild.me

        if me is None:
            return False

        permissions = channel.permissions_for(me)

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.read_message_history
        ):
            return False

        content = self.build_status_message(guild)

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(content=content)
                return True

            except discord.NotFound:
                await guild_config.message_id.clear()

            except discord.Forbidden:
                return False

            except discord.HTTPException:
                return False

        try:
            message = await channel.send(content)
        except (discord.Forbidden, discord.HTTPException):
            return False

        await guild_config.message_id.set(message.id)
        return True

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
                await self.publish_status(guild)

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()