\
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import discord
from discord.ext import tasks
from red_commons.logging import getLogger
from redbot.core import commands

from .message_renderer import idle_music_embed, now_playing_embed


log = getLogger("red.imperialautomation.music")
VN_TZ = timezone(timedelta(hours=7), name="UTC+7")

try:
    import lavalink
except ImportError:
    lavalink = None


AUDIO_ALLOWED_COMMANDS = {
    "play",
    "search",
    "queue",
    "skip",
    "pause",
    "resume",
    "volume",
    "disconnect",
    "stop",
    "now",
    "shuffle",
    "repeat",
    "remove",
    "bump",
    "seek",
}

ENQUEUE_COMMANDS = {
    "play",
    "search",
    "genre",
    "playlist start",
}


class MusicService:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.empty_since: Dict[int, datetime] = {}
        self.room_delete_tasks: Dict[int, asyncio.Task] = {}

    def start(self):
        self.panel_loop.start()
        self.disconnect_loop.start()
        self.room_sweeper.start()

    def stop(self):
        self.panel_loop.cancel()
        self.disconnect_loop.cancel()
        self.room_sweeper.cancel()
        for task in list(self.room_delete_tasks.values()):
            task.cancel()

    async def global_command_gate(self, ctx: commands.Context) -> bool:
        if ctx.guild is None or ctx.command is None:
            return True

        data = await self.cog.config.guild(ctx.guild).all()
        request_id = data.get("music_request_channel_id")
        enforce = bool(data.get("music_enforce_request_channel", True))
        command_name = ctx.command.qualified_name.casefold()
        root_name = command_name.split(" ", 1)[0]
        cog_name = (
            ctx.cog.qualified_name.casefold()
            if ctx.cog is not None
            else ""
        )

        in_request = bool(request_id and ctx.channel.id == request_id)
        is_audio = cog_name == "audio"

        if in_request and not is_audio:
            allowed_meta = (
                command_name.startswith("ia music")
                or command_name.startswith("listen ")
                or command_name == "help"
            )
            if not allowed_meta:
                await ctx.send(
                    "🎵 Kênh này chỉ nhận lệnh nhạc.",
                    delete_after=6,
                )
                return False

        if is_audio and enforce and not in_request:
            await ctx.send(
                "🎵 Hãy dùng lệnh Audio trong channel **#music-request**.",
                delete_after=8,
            )
            return False

        if is_audio and in_request:
            allowed = any(
                command_name == value
                or command_name.startswith(value + " ")
                for value in AUDIO_ALLOWED_COMMANDS
            )
            if not allowed:
                await ctx.send(
                    "⛔ Lệnh Audio này không được phép trong #music-request.",
                    delete_after=8,
                )
                return False

            if any(
                command_name == value
                or command_name.startswith(value + " ")
                for value in ENQUEUE_COMMANDS
            ):
                if not await self._can_enqueue(ctx, data):
                    return False

        return True

    async def _can_enqueue(
        self,
        ctx: commands.Context,
        data: Dict[str, Any],
    ) -> bool:
        max_per_user = max(
            1,
            min(50, int(data.get("music_max_queue_per_user", 5))),
        )
        current_count = self._requester_track_count(
            ctx.guild.id,
            ctx.author.id,
        )

        if current_count >= max_per_user:
            await ctx.send(
                f"📦 Bạn đã có `{current_count}/{max_per_user}` bài "
                "trong current track/queue.",
                delete_after=10,
            )
            return False

        allowed_voice_ids = {
            int(value)
            for value in data.get("music_allowed_voice_ids", [])
        }
        lounge_id = data.get("music_lounge_voice_id")
        if lounge_id:
            allowed_voice_ids.add(int(lounge_id))

        private_rooms = data.get("music_private_rooms", {})
        allowed_voice_ids.update(int(key) for key in private_rooms)

        voice_channel = (
            ctx.author.voice.channel
            if ctx.author.voice and ctx.author.voice.channel
            else None
        )

        if allowed_voice_ids and (
            voice_channel is None or voice_channel.id not in allowed_voice_ids
        ):
            await ctx.send(
                "🔊 Hãy vào **Music Lounge** hoặc một **Private Listening** room "
                "trước khi thêm nhạc.",
                delete_after=10,
            )
            return False

        return True

    def _requester_track_count(self, guild_id: int, user_id: int) -> int:
        if lavalink is None:
            return 0

        with contextlib.suppress(Exception):
            player = lavalink.get_player(guild_id)
            tracks = list(player.queue)
            if player.current is not None:
                tracks.insert(0, player.current)

            return sum(
                1
                for track in tracks
                if getattr(getattr(track, "requester", None), "id", None)
                == user_id
            )

        return 0

    async def trim_requester_queue(
        self,
        ctx: commands.Context,
    ):
        if ctx.guild is None or ctx.command is None or lavalink is None:
            return

        command_name = ctx.command.qualified_name.casefold()
        if not any(
            command_name == value or command_name.startswith(value + " ")
            for value in ENQUEUE_COMMANDS
        ):
            return

        data = await self.cog.config.guild(ctx.guild).all()
        request_id = data.get("music_request_channel_id")
        if not request_id or ctx.channel.id != request_id:
            return

        limit = max(
            1,
            min(50, int(data.get("music_max_queue_per_user", 5))),
        )

        try:
            player = lavalink.get_player(ctx.guild.id)
        except Exception:
            return

        current_owned = (
            1
            if getattr(
                getattr(player.current, "requester", None),
                "id",
                None,
            )
            == ctx.author.id
            else 0
        )
        allowed_queued = max(0, limit - current_owned)
        owned_seen = 0
        removed = 0
        new_queue = []

        for track in list(player.queue):
            requester_id = getattr(
                getattr(track, "requester", None),
                "id",
                None,
            )
            if requester_id == ctx.author.id:
                owned_seen += 1
                if owned_seen > allowed_queued:
                    removed += 1
                    continue
            new_queue.append(track)

        if removed:
            player.queue = new_queue
            await ctx.send(
                f"📦 Queue quota: removed `{removed}` surplus track(s). "
                f"Maximum: `{limit}` per user.",
                delete_after=12,
            )

    async def schedule_message_cleanup(self, message: discord.Message):
        if message.guild is None:
            return

        data = await self.cog.config.guild(message.guild).all()
        request_id = data.get("music_request_channel_id")
        if not request_id or message.channel.id != request_id:
            return

        delay = (
            int(data.get("music_bot_response_delete_seconds", 25))
            if message.author.bot
            else int(data.get("music_user_command_delete_seconds", 5))
        )

        if delay <= 0:
            return

        async def delete_later():
            await asyncio.sleep(delay)
            if message.pinned:
                return
            with contextlib.suppress(discord.HTTPException):
                await message.delete()

        asyncio.create_task(delete_later())

    @tasks.loop(seconds=15)
    async def panel_loop(self):
        all_guilds = await self.cog.config.all_guilds()
        for guild_id in all_guilds:
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue
            with contextlib.suppress(Exception):
                await self.update_panel(guild)

    @panel_loop.before_loop
    async def before_panel_loop(self):
        await self.bot.wait_until_ready()

    async def update_panel(self, guild: discord.Guild):
        guild_conf = self.cog.config.guild(guild)
        data = await guild_conf.all()
        channel_id = data.get("current_play_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        prefix = "!"
        with contextlib.suppress(Exception):
            prefixes = await self.bot.get_valid_prefixes(guild)
            prefix = next(
                (
                    value
                    for value in prefixes
                    if isinstance(value, str) and not value.startswith("<@")
                ),
                "!",
            )

        embed = idle_music_embed(prefix)
        if lavalink is not None:
            with contextlib.suppress(Exception):
                player = lavalink.get_player(guild.id)
                track = player.current
                if track is not None:
                    requester_obj = getattr(track, "requester", None)
                    requester = (
                        getattr(requester_obj, "display_name", None)
                        or getattr(requester_obj, "name", None)
                        or str(requester_obj or "Unknown")
                    )
                    embed = now_playing_embed(
                        title=getattr(track, "title", "Unknown track"),
                        artist=getattr(track, "author", "Unknown"),
                        position_ms=int(getattr(player, "position", 0) or 0),
                        length_ms=int(getattr(track, "length", 0) or 0),
                        requester=requester,
                        queue_size=len(getattr(player, "queue", []) or []),
                        volume=int(getattr(player, "volume", 0) or 0),
                        url=(
                            getattr(track, "uri", None)
                            or getattr(track, "url", None)
                        ),
                        thumbnail=getattr(track, "thumbnail", None),
                        is_stream=bool(getattr(track, "is_stream", False)),
                    )

        message_id = data.get("current_play_message_id")
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(
                    embed=embed,
                    content=None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            except discord.NotFound:
                await guild_conf.current_play_message_id.clear()
            except discord.HTTPException:
                return

        try:
            message = await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            await self.cog.report_error(
                guild,
                operation="Create current-play status message",
                error=exc,
            )
            return

        await guild_conf.current_play_message_id.set(message.id)

    async def publish_guide(self, guild: discord.Guild) -> bool:
        guild_conf = self.cog.config.guild(guild)
        data = await guild_conf.all()
        channel_id = data.get("music_guide_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return False

        prefix = "!"
        with contextlib.suppress(Exception):
            prefixes = await self.bot.get_valid_prefixes(guild)
            prefix = next(
                (
                    value
                    for value in prefixes
                    if isinstance(value, str) and not value.startswith("<@")
                ),
                "!",
            )

        embed = discord.Embed(
            title="🎼 NHẠC VIỆN — MUSIC GUIDE",
            description=(
                f"`{prefix}play <tên/link>` — phát hoặc thêm bài\n"
                f"`{prefix}search <tên>` — tìm bài\n"
                f"`{prefix}queue` — xem hàng đợi\n"
                f"`{prefix}skip` — bỏ qua\n"
                f"`{prefix}pause` / `{prefix}resume`\n"
                f"`{prefix}volume <0-150>`\n"
                f"`{prefix}disconnect` — rời voice\n\n"
                "Dùng lệnh trong **#music-request**. "
                "Vào **Music Lounge** hoặc **Private Listening** trước khi thêm nhạc."
            ),
            colour=discord.Colour.blurple(),
        )
        embed.set_footer(
            text="ImperialAutomation • Audio commands are channel-restricted"
        )

        message_id = data.get("music_guide_message_id")
        message = None
        if message_id:
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed, content=None)

        if message is None:
            message = await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await guild_conf.music_guide_message_id.set(message.id)

        if not message.pinned:
            with contextlib.suppress(discord.HTTPException):
                await message.pin(reason="ImperialAutomation music guide")

        return True

    @tasks.loop(seconds=30)
    async def disconnect_loop(self):
        if lavalink is None:
            return

        now = datetime.now(VN_TZ)
        all_guilds = await self.cog.config.all_guilds()

        for player in list(lavalink.all_players()):
            guild = getattr(player, "guild", None)
            channel = getattr(player, "channel", None)
            if guild is None or channel is None:
                continue

            data = all_guilds.get(str(guild.id)) or all_guilds.get(guild.id)
            if not data:
                continue

            timeout = max(
                180,
                min(
                    300,
                    int(data.get("music_empty_disconnect_seconds", 300)),
                ),
            )
            humans = [member for member in channel.members if not member.bot]

            if humans:
                self.empty_since.pop(guild.id, None)
                continue

            since = self.empty_since.setdefault(guild.id, now)
            if now - since < timedelta(seconds=timeout):
                continue

            try:
                await player.stop()
                await player.disconnect()
                self.empty_since.pop(guild.id, None)
                await self.update_panel(guild)
            except Exception as exc:
                await self.cog.report_error(
                    guild,
                    operation="Auto-disconnect empty music voice channel",
                    error=exc,
                )

    @disconnect_loop.before_loop
    async def before_disconnect_loop(self):
        await self.bot.wait_until_ready()

    async def voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        data = await self.cog.config.guild(member.guild).all()
        trigger_id = data.get("music_private_trigger_id")

        if after.channel is not None and after.channel.id == trigger_id:
            await self._create_private_room(member, after.channel)
            return

        if before.channel is not None and before.channel != after.channel:
            await self._maybe_schedule_room_delete(before.channel)

        if after.channel is not None and before.channel != after.channel:
            task = self.room_delete_tasks.pop(after.channel.id, None)
            if task is not None:
                task.cancel()

    async def _create_private_room(
        self,
        member: discord.Member,
        trigger: discord.VoiceChannel,
    ):
        guild = member.guild
        guild_conf = self.cog.config.guild(guild)
        category_id = await guild_conf.music_private_category_id()
        category = guild.get_channel(category_id) if category_id else trigger.category

        try:
            room = await guild.create_voice_channel(
                f"Listening • {member.display_name}"[:100],
                category=(
                    category
                    if isinstance(category, discord.CategoryChannel)
                    else None
                ),
                bitrate=trigger.bitrate,
                user_limit=4,
                overwrites=trigger.overwrites,
                reason=f"Private listening room for {member}",
            )
            await room.set_permissions(
                member,
                view_channel=True,
                connect=True,
                move_members=True,
                manage_channels=True,
                reason="Private Listening owner permissions",
            )
            async with guild_conf.music_private_rooms() as rooms:
                rooms[str(room.id)] = {
                    "owner_id": member.id,
                    "created_at": datetime.now(VN_TZ).isoformat(),
                }

            await member.move_to(
                room,
                reason="Move member into Private Listening room",
            )
        except discord.HTTPException as exc:
            await self.cog.report_error(
                guild,
                operation=(
                    f"Create Private Listening room for "
                    f"{member.display_name}"
                ),
                error=exc,
            )

    async def _maybe_schedule_room_delete(
        self,
        channel: discord.abc.GuildChannel,
    ):
        if not isinstance(channel, discord.VoiceChannel):
            return

        rooms = await self.cog.config.guild(channel.guild).music_private_rooms()
        if str(channel.id) not in rooms:
            return

        if any(not member.bot for member in channel.members):
            return

        old_task = self.room_delete_tasks.pop(channel.id, None)
        if old_task is not None:
            old_task.cancel()

        delay = await self.cog.config.guild(
            channel.guild
        ).music_private_empty_seconds()
        self.room_delete_tasks[channel.id] = asyncio.create_task(
            self._delete_room_after(channel.guild.id, channel.id, int(delay))
        )

    async def _delete_room_after(
        self,
        guild_id: int,
        channel_id: int,
        delay: int,
    ):
        try:
            await asyncio.sleep(max(30, min(60, delay)))
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return

            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                await self._remove_room(guild, channel_id)
                return

            if any(not member.bot for member in channel.members):
                return

            await channel.delete(reason="Private Listening room became empty")
            await self._remove_room(guild, channel_id)
        except asyncio.CancelledError:
            raise
        except discord.HTTPException as exc:
            guild = self.bot.get_guild(guild_id)
            if guild is not None:
                await self.cog.report_error(
                    guild,
                    operation=(
                        f"Delete empty Private Listening room {channel_id}"
                    ),
                    error=exc,
                )
        finally:
            self.room_delete_tasks.pop(channel_id, None)

    async def _remove_room(
        self,
        guild: discord.Guild,
        channel_id: int,
    ):
        async with self.cog.config.guild(guild).music_private_rooms() as rooms:
            rooms.pop(str(channel_id), None)

    @tasks.loop(minutes=5)
    async def room_sweeper(self):
        all_guilds = await self.cog.config.all_guilds()

        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            for channel_id_text in list(
                data.get("music_private_rooms", {})
            ):
                channel = guild.get_channel(int(channel_id_text))
                if not isinstance(channel, discord.VoiceChannel):
                    await self._remove_room(guild, int(channel_id_text))
                    continue

                if not any(not member.bot for member in channel.members):
                    await self._maybe_schedule_room_delete(channel)

    @room_sweeper.before_loop
    async def before_room_sweeper(self):
        await self.bot.wait_until_ready()

    async def owned_room(
        self,
        ctx: commands.Context,
    ) -> Optional[discord.VoiceChannel]:
        voice = ctx.author.voice
        if voice is None or not isinstance(
            voice.channel,
            discord.VoiceChannel,
        ):
            await ctx.send("❌ Bạn phải ở trong Private Listening room.")
            return None

        rooms = await self.cog.config.guild(ctx.guild).music_private_rooms()
        room = rooms.get(str(voice.channel.id))
        if not room:
            await ctx.send("❌ Đây không phải Private Listening room.")
            return None

        owner_id = int(room.get("owner_id") or 0)
        if (
            owner_id != ctx.author.id
            and not ctx.author.guild_permissions.manage_channels
        ):
            await ctx.send("❌ Bạn không phải chủ phòng.")
            return None

        return voice.channel
