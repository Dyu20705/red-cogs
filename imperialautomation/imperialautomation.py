\
from __future__ import annotations

import contextlib
import io
from typing import Any, Dict, List, Optional

import discord
from redbot.core import Config, commands

from .services import FeedService, MusicService


CHANNEL_KEYS = {
    "feeds": "all_feeds_channel_id",
    "feed-alert": "feed_alert_channel_id",
    "music-guide": "music_guide_channel_id",
    "music-request": "music_request_channel_id",
    "current-play": "current_play_channel_id",
}


class ImperialAutomation(commands.Cog):
    """Unified automation layer for feeds and Red Audio."""

    __red_end_user_data_statement__ = (
        "This cog stores RSS source configuration, hashed seen URLs, digest items, "
        "Discord channel/message/thread IDs, music queue controls, and temporary "
        "voice-room ownership. It does not store bot tokens, webhook URLs, or API secrets."
    )

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=2809200505,
            force_registration=True,
        )
        self.config.register_guild(
            # FEEDS
            all_feeds_channel_id=None,
            feed_alert_channel_id=None,
            feed_sources=[],
            feed_seen_urls={},
            feed_digest_items=[],
            feed_topic_threads={},
            feed_interval_minutes=25,
            feed_max_items_per_cycle=3,
            feed_max_age_hours=24,
            feed_digest_hour=21,
            feed_digest_minute=30,
            feed_thread_mode=True,
            feed_last_cycle=None,
            feed_last_digest="",
            # MUSIC
            music_guide_channel_id=None,
            music_request_channel_id=None,
            current_play_channel_id=None,
            music_lounge_voice_id=None,
            music_allowed_voice_ids=[],
            music_private_trigger_id=None,
            music_private_category_id=None,
            music_private_rooms={},
            music_private_empty_seconds=45,
            music_guide_message_id=None,
            current_play_message_id=None,
            music_max_queue_per_user=5,
            music_user_command_delete_seconds=5,
            music_bot_response_delete_seconds=25,
            music_empty_disconnect_seconds=300,
            music_enforce_request_channel=True,
        )

        self.feed = FeedService(self)
        self.music = MusicService(self)
        self.feed.start()
        self.music.start()
        self.bot.add_check(self.music.global_command_gate)

    def cog_unload(self):
        self.feed.stop()
        self.music.stop()
        self.bot.remove_check(self.music.global_command_gate)

    # ------------------------------------------------------------------
    # Main configuration
    # ------------------------------------------------------------------

    @commands.group(name="ia", aliases=["imperialautomation"])
    @commands.guild_only()
    async def ia(self, ctx: commands.Context):
        """ImperialAutomation controls."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @ia.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def ia_set_channel(
        self,
        ctx: commands.Context,
        kind: str,
        channel: discord.TextChannel,
    ):
        """Set feeds/feed-alert/music-guide/music-request/current-play."""

        key = CHANNEL_KEYS.get(kind.casefold().strip())
        if key is None:
            await ctx.send(
                "❌ Chọn `feeds`, `feed-alert`, `music-guide`, "
                "`music-request`, hoặc `current-play`."
            )
            return

        missing = self._missing_text_permissions(
            channel,
            needs_threads=(kind == "feeds"),
            needs_pin=(kind == "music-guide"),
        )
        if missing:
            await ctx.send(
                f"❌ Bot thiếu quyền trong {channel.mention}: "
                f"**{', '.join(missing)}**"
            )
            return

        guild_conf = self.config.guild(ctx.guild)
        old_id = await getattr(guild_conf, key)()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None
        await getattr(guild_conf, key).set(channel.id)

        await self.audit(
            ctx,
            action=f"Changed ImperialAutomation {kind} channel",
            before=old_channel.mention if old_channel else "none",
            after=channel.mention,
        )
        await ctx.send(f"✅ `{kind}` channel: {channel.mention}")

    @ia.command(name="status")
    @commands.admin_or_permissions(manage_guild=True)
    async def ia_status(self, ctx: commands.Context):
        """Show the current feed and music automation configuration."""

        data = await self.config.guild(ctx.guild).all()

        def channel_text(key: str) -> str:
            channel_id = data.get(key)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            return channel.mention if isinstance(
                channel,
                discord.TextChannel,
            ) else "Not configured"

        def voice_text(key: str) -> str:
            channel_id = data.get(key)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            return (
                f"**{channel.name}**"
                if isinstance(channel, discord.VoiceChannel)
                else "Not configured"
            )

        await ctx.send(
            "**👑 IMPERIAL AUTOMATION STATUS**\n\n"
            "**Feeds**\n"
            f"All feeds: {channel_text('all_feeds_channel_id')}\n"
            f"Security alerts: {channel_text('feed_alert_channel_id')}\n"
            f"Sources: `{len(data['feed_sources'])}`\n"
            f"Interval: `{data['feed_interval_minutes']}m`\n"
            f"Max per cycle: `{data['feed_max_items_per_cycle']}`\n"
            f"Max age: `{data['feed_max_age_hours']}h`\n"
            f"Thread mode: `{data['feed_thread_mode']}`\n"
            f"Digest: `{data['feed_digest_hour']:02d}:"
            f"{data['feed_digest_minute']:02d} UTC+7`\n\n"
            "**Music**\n"
            f"Guide: {channel_text('music_guide_channel_id')}\n"
            f"Request: {channel_text('music_request_channel_id')}\n"
            f"Current play: {channel_text('current_play_channel_id')}\n"
            f"Music Lounge: {voice_text('music_lounge_voice_id')}\n"
            f"Queue quota: `{data['music_max_queue_per_user']}`/user\n"
            f"Command cleanup: `{data['music_user_command_delete_seconds']}s`\n"
            f"Response cleanup: `{data['music_bot_response_delete_seconds']}s`\n"
            f"Empty disconnect: `{data['music_empty_disconnect_seconds']}s`\n"
            f"Request-channel gate: `{data['music_enforce_request_channel']}`",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # ------------------------------------------------------------------
    # Feed configuration
    # ------------------------------------------------------------------

    @ia.group(name="feed")
    @commands.admin_or_permissions(manage_guild=True)
    async def ia_feed(self, ctx: commands.Context):
        """Manage filtered RSS/Atom feeds."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @ia_feed.command(name="add")
    async def feed_add(
        self,
        ctx: commands.Context,
        topic: str,
        url: str,
        *,
        name: str = "",
    ):
        """Add a feed: `!ia feed add dev URL Source name`."""

        if not url.startswith(("http://", "https://")):
            await ctx.send("❌ URL phải bắt đầu bằng `http://` hoặc `https://`.")
            return

        source = {
            "name": name.strip()[:100] or url,
            "url": url.strip(),
            "topic": topic.strip().lower()[:30] or "general",
            "include_keywords": [],
            "exclude_keywords": [],
            "priority": 50,
            "minimum_score": 25,
            "security": False,
            "enabled": True,
        }

        async with self.config.guild(ctx.guild).feed_sources() as sources:
            if any(
                str(item.get("url") or "").casefold() == url.casefold()
                for item in sources
            ):
                await ctx.send("❌ Feed URL đã tồn tại.")
                return
            sources.append(source)
            index = len(sources)

        await self.audit(
            ctx,
            action="Added RSS source",
            before="not configured",
            after=f"{source['name']} ({source['topic']})",
        )
        await ctx.send(f"✅ Added feed **#{index}**: {source['name']}")

    @ia_feed.command(name="list")
    async def feed_list(self, ctx: commands.Context):
        """List feed sources."""

        sources = await self.config.guild(ctx.guild).feed_sources()
        if not sources:
            await ctx.send("ℹ️ Chưa có RSS source.")
            return

        lines = ["**🗞 FEED SOURCES**", ""]
        for index, source in enumerate(sources, start=1):
            flags = []
            if source.get("security"):
                flags.append("security")
            if not source.get("enabled", True):
                flags.append("disabled")
            flag_text = f" • `{', '.join(flags)}`" if flags else ""
            lines.append(
                f"**{index}. {source.get('name')}** "
                f"— `{source.get('topic')}`"
                f" • priority `{source.get('priority', 50)}`{flag_text}\n"
                f"<{source.get('url')}>"
            )

        await ctx.send(
            "\n".join(lines)[:1900],
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @ia_feed.command(name="remove")
    async def feed_remove(self, ctx: commands.Context, number: int):
        """Remove one feed source."""

        async with self.config.guild(ctx.guild).feed_sources() as sources:
            if number < 1 or number > len(sources):
                await ctx.send("❌ Feed number không tồn tại.")
                return
            removed = sources.pop(number - 1)

        await self.audit(
            ctx,
            action="Removed RSS source",
            before=removed.get("name"),
            after="removed",
        )
        await ctx.send(f"🗑 Removed **{removed.get('name')}**.")

    @ia_feed.command(name="include")
    async def feed_include(
        self,
        ctx: commands.Context,
        number: int,
        *,
        keywords: str,
    ):
        """Set comma-separated required keywords; use `none` to clear."""

        values = self._keyword_values(keywords)
        await self._update_feed_source(
            ctx,
            number,
            "include_keywords",
            values,
            "Updated feed include keywords",
        )

    @ia_feed.command(name="exclude")
    async def feed_exclude(
        self,
        ctx: commands.Context,
        number: int,
        *,
        keywords: str,
    ):
        """Set comma-separated blocked keywords; use `none` to clear."""

        values = self._keyword_values(keywords)
        await self._update_feed_source(
            ctx,
            number,
            "exclude_keywords",
            values,
            "Updated feed exclude keywords",
        )

    @ia_feed.command(name="security")
    async def feed_security(
        self,
        ctx: commands.Context,
        number: int,
        enabled: bool,
    ):
        """Route a source as serious security alerts."""

        await self._update_feed_source(
            ctx,
            number,
            "security",
            enabled,
            "Changed feed security routing",
        )

    @ia_feed.command(name="priority")
    async def feed_priority(
        self,
        ctx: commands.Context,
        number: int,
        priority: int,
    ):
        """Set source priority from 0 to 100."""

        if not 0 <= priority <= 100:
            await ctx.send("❌ Priority phải từ 0 đến 100.")
            return

        await self._update_feed_source(
            ctx,
            number,
            "priority",
            priority,
            "Changed feed priority",
        )

    @ia_feed.command(name="enable")
    async def feed_enable(
        self,
        ctx: commands.Context,
        number: int,
        enabled: bool,
    ):
        """Enable or disable one source."""

        await self._update_feed_source(
            ctx,
            number,
            "enabled",
            enabled,
            "Changed feed enabled state",
        )

    @ia_feed.command(name="interval")
    async def feed_interval(self, ctx: commands.Context, minutes: int):
        """Set polling interval from 20 to 30 minutes."""

        if not 20 <= minutes <= 30:
            await ctx.send("❌ Interval phải từ 20 đến 30 phút.")
            return

        old = await self.config.guild(ctx.guild).feed_interval_minutes()
        await self.config.guild(ctx.guild).feed_interval_minutes.set(minutes)
        await self.audit(
            ctx,
            action="Changed feed interval",
            before=f"{old} minutes",
            after=f"{minutes} minutes",
        )
        await ctx.send(f"✅ Feed interval: **{minutes} minutes**.")

    @ia_feed.command(name="maxitems")
    async def feed_max_items(self, ctx: commands.Context, count: int):
        """Set maximum posts per cycle from 1 to 3."""

        if not 1 <= count <= 3:
            await ctx.send("❌ Max items phải từ 1 đến 3.")
            return

        old = await self.config.guild(ctx.guild).feed_max_items_per_cycle()
        await self.config.guild(ctx.guild).feed_max_items_per_cycle.set(count)
        await self.audit(
            ctx,
            action="Changed feed max items per cycle",
            before=str(old),
            after=str(count),
        )
        await ctx.send(f"✅ Maximum feed posts per cycle: **{count}**.")

    @ia_feed.command(name="threadmode")
    async def feed_thread_mode(
        self,
        ctx: commands.Context,
        enabled: bool,
    ):
        """Send normal articles into daily topic threads."""

        old = await self.config.guild(ctx.guild).feed_thread_mode()
        await self.config.guild(ctx.guild).feed_thread_mode.set(enabled)
        await self.audit(
            ctx,
            action="Changed feed topic thread mode",
            before=str(old),
            after=str(enabled),
        )
        await ctx.send(
            "✅ Feed thread mode: "
            + ("**enabled**" if enabled else "**disabled**")
        )

    @ia_feed.command(name="digesttime")
    async def feed_digest_time(
        self,
        ctx: commands.Context,
        hour: int,
        minute: int = 30,
    ):
        """Set daily digest time in UTC+7."""

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            await ctx.send("❌ Giờ/phút không hợp lệ.")
            return

        guild_conf = self.config.guild(ctx.guild)
        old_hour = await guild_conf.feed_digest_hour()
        old_minute = await guild_conf.feed_digest_minute()
        await guild_conf.feed_digest_hour.set(hour)
        await guild_conf.feed_digest_minute.set(minute)

        await self.audit(
            ctx,
            action="Changed feed digest time",
            before=f"{old_hour:02d}:{old_minute:02d}",
            after=f"{hour:02d}:{minute:02d}",
        )
        await ctx.send(f"✅ Daily digest: **{hour:02d}:{minute:02d} UTC+7**.")

    @ia_feed.command(name="checknow")
    async def feed_check_now(self, ctx: commands.Context):
        """Run one feed cycle now."""

        count = await self.feed.run_cycle(ctx.guild, force=True)
        await ctx.send(f"✅ Feed cycle complete: `{count}` item(s) posted.")

    @ia_feed.command(name="digestnow")
    async def feed_digest_now(self, ctx: commands.Context):
        """Post today's digest immediately."""

        posted = await self.feed.post_digest(ctx.guild, force=True)
        if posted:
            await ctx.tick()
        else:
            await ctx.send("❌ Chưa cấu hình #all-feeds.")

    # ------------------------------------------------------------------
    # Music configuration
    # ------------------------------------------------------------------

    @ia.group(name="music")
    @commands.admin_or_permissions(manage_guild=True)
    async def ia_music(self, ctx: commands.Context):
        """Configure the Red Audio automation layer."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @ia_music.command(name="guide")
    async def music_guide(self, ctx: commands.Context):
        """Publish/update and pin the music guide."""

        if await self.music.publish_guide(ctx.guild):
            await ctx.tick()
        else:
            await ctx.send("❌ Chưa cấu hình #music-guide.")

    @ia_music.command(name="panel")
    async def music_panel(self, ctx: commands.Context):
        """Create or refresh the current-play panel."""

        await self.music.update_panel(ctx.guild)
        await ctx.tick()

    @ia_music.command(name="lounge")
    async def music_lounge(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
    ):
        """Set the shared Music Lounge."""

        guild_conf = self.config.guild(ctx.guild)
        old_id = await guild_conf.music_lounge_voice_id()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None
        await guild_conf.music_lounge_voice_id.set(channel.id)

        await self.audit(
            ctx,
            action="Changed Music Lounge",
            before=old_channel.name if old_channel else "none",
            after=channel.name,
        )
        await ctx.send(f"✅ Music Lounge: **{channel.name}**")

    @ia_music.command(name="allowvoice")
    async def music_allow_voice(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
    ):
        """Allow an additional music voice channel."""

        async with self.config.guild(
            ctx.guild
        ).music_allowed_voice_ids() as channel_ids:
            if channel.id not in channel_ids:
                channel_ids.append(channel.id)

        await ctx.send(f"✅ Allowed music voice: **{channel.name}**")

    @ia_music.command(name="denyvoice")
    async def music_deny_voice(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
    ):
        """Remove an additional allowed music voice channel."""

        async with self.config.guild(
            ctx.guild
        ).music_allowed_voice_ids() as channel_ids:
            with contextlib.suppress(ValueError):
                channel_ids.remove(channel.id)

        await ctx.send(f"✅ Removed allowed voice: **{channel.name}**")

    @ia_music.command(name="private")
    async def music_private(
        self,
        ctx: commands.Context,
        trigger: discord.VoiceChannel,
        category: Optional[discord.CategoryChannel] = None,
    ):
        """Set Private Listening join-to-create trigger."""

        category = category or trigger.category
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.music_private_trigger_id.set(trigger.id)
        await guild_conf.music_private_category_id.set(
            category.id if category else None
        )

        await self.audit(
            ctx,
            action="Changed Private Listening trigger",
            before="previous trigger",
            after=trigger.name,
        )
        await ctx.send(
            f"✅ Private Listening trigger: **{trigger.name}**\n"
            f"Category: **{category.name if category else 'none'}**"
        )

    @ia_music.command(name="maxqueue")
    async def music_max_queue(self, ctx: commands.Context, count: int):
        """Set maximum current+queued tracks per user."""

        if not 1 <= count <= 50:
            await ctx.send("❌ Queue quota phải từ 1 đến 50.")
            return

        old = await self.config.guild(ctx.guild).music_max_queue_per_user()
        await self.config.guild(ctx.guild).music_max_queue_per_user.set(count)
        await self.audit(
            ctx,
            action="Changed music queue quota",
            before=str(old),
            after=str(count),
        )
        await ctx.send(f"✅ Queue quota: **{count} tracks/user**.")

    @ia_music.command(name="cleanup")
    async def music_cleanup(
        self,
        ctx: commands.Context,
        user_seconds: int,
        bot_seconds: int,
    ):
        """Set deletion delay for user commands and bot responses."""

        if not 0 <= user_seconds <= 60 or not 0 <= bot_seconds <= 300:
            await ctx.send(
                "❌ User delay: 0–60s; bot response delay: 0–300s."
            )
            return

        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.music_user_command_delete_seconds.set(user_seconds)
        await guild_conf.music_bot_response_delete_seconds.set(bot_seconds)
        await ctx.send(
            f"✅ Cleanup: user `{user_seconds}s`, bot `{bot_seconds}s`."
        )

    @ia_music.command(name="autodisconnect")
    async def music_auto_disconnect(
        self,
        ctx: commands.Context,
        seconds: int,
    ):
        """Set empty-channel disconnect to 180–300 seconds."""

        if not 180 <= seconds <= 300:
            await ctx.send("❌ Auto-disconnect phải từ 180 đến 300 giây.")
            return

        old = await self.config.guild(
            ctx.guild
        ).music_empty_disconnect_seconds()
        await self.config.guild(
            ctx.guild
        ).music_empty_disconnect_seconds.set(seconds)

        await self.audit(
            ctx,
            action="Changed music empty disconnect timeout",
            before=f"{old}s",
            after=f"{seconds}s",
        )
        await ctx.send(f"✅ Empty disconnect: **{seconds}s**.")

    @ia_music.command(name="gate")
    async def music_gate(
        self,
        ctx: commands.Context,
        enabled: bool,
    ):
        """Require all Audio commands to be issued in #music-request."""

        old = await self.config.guild(
            ctx.guild
        ).music_enforce_request_channel()
        await self.config.guild(
            ctx.guild
        ).music_enforce_request_channel.set(enabled)

        await self.audit(
            ctx,
            action="Changed music request-channel gate",
            before=str(old),
            after=str(enabled),
        )
        await ctx.send(
            "✅ Request-channel gate: "
            + ("**enabled**" if enabled else "**disabled**")
        )

    @ia_music.command(name="permissions")
    async def music_permissions_yaml(self, ctx: commands.Context):
        """Generate a Red Permissions ACL YAML template."""

        data = await self.config.guild(ctx.guild).all()
        request_id = data.get("music_request_channel_id")
        lounge_id = data.get("music_lounge_voice_id")
        private_category_id = data.get("music_private_category_id")

        if not request_id:
            await ctx.send("❌ Hãy cấu hình #music-request trước.")
            return

        audio_rules = {
            str(request_id): True,
            "default": False,
        }
        if lounge_id:
            audio_rules[str(lounge_id)] = True
        if private_category_id:
            audio_rules[str(private_category_id)] = True

        lines = ["COG:", "  Audio:"]
        for model, value in audio_rules.items():
            lines.append(f"    {model}: {str(value).lower()}")

        lines.extend(
            [
                "COMMAND:",
                "  audioset:",
                "    default: false",
                "  llset:",
                "    default: false",
            ]
        )
        payload = "\n".join(lines) + "\n"

        await ctx.send(
            "Dùng file này với `!permissions acl updateserver` hoặc "
            "`!permissions acl setserver` sau khi đã kiểm tra nội dung.",
            file=discord.File(
                io.BytesIO(payload.encode("utf-8")),
                filename="imperialautomation-audio-permissions.yaml",
            ),
        )

    # ------------------------------------------------------------------
    # Private Listening owner commands
    # ------------------------------------------------------------------

    @commands.group(name="listen")
    @commands.guild_only()
    async def listen(self, ctx: commands.Context):
        """Manage your Private Listening room."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @listen.command(name="lock")
    async def listen_lock(self, ctx: commands.Context):
        channel = await self.music.owned_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                connect=False,
                reason=f"Private Listening locked by {ctx.author}",
            )
            await channel.set_permissions(
                ctx.author,
                view_channel=True,
                connect=True,
                move_members=True,
                manage_channels=True,
                reason="Preserve room owner access",
            )
        except discord.HTTPException as exc:
            await self.report_error(
                ctx.guild,
                operation=f"Lock Private Listening room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.send("🔒 Private Listening room locked.")

    @listen.command(name="unlock")
    async def listen_unlock(self, ctx: commands.Context):
        channel = await self.music.owned_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                connect=None,
                reason=f"Private Listening unlocked by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self.report_error(
                ctx.guild,
                operation=f"Unlock Private Listening room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.send("🔓 Private Listening room unlocked.")

    @listen.command(name="limit")
    async def listen_limit(self, ctx: commands.Context, limit: int):
        channel = await self.music.owned_room(ctx)
        if channel is None:
            return
        if not 0 <= limit <= 99:
            await ctx.send("❌ Limit phải từ 0 đến 99.")
            return

        try:
            await channel.edit(
                user_limit=limit,
                reason=f"Private Listening limit set by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self.report_error(
                ctx.guild,
                operation=f"Set Private Listening limit {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.send(f"👥 Room limit: **{limit or 'unlimited'}**")

    @listen.command(name="rename")
    async def listen_rename(self, ctx: commands.Context, *, name: str):
        channel = await self.music.owned_room(ctx)
        if channel is None:
            return

        name = name.strip()
        if not 1 <= len(name) <= 100:
            await ctx.send("❌ Tên phòng phải từ 1 đến 100 ký tự.")
            return

        try:
            await channel.edit(
                name=name,
                reason=f"Private Listening renamed by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self.report_error(
                ctx.guild,
                operation=f"Rename Private Listening room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.send(f"✏️ Room renamed to **{name}**.")

    @listen.command(name="permit")
    async def listen_permit(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        channel = await self.music.owned_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                connect=True,
                reason=f"Private Listening permit by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self.report_error(
                ctx.guild,
                operation=f"Permit member in {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.send(f"✅ Permitted **{member.display_name}**.")

    # ------------------------------------------------------------------
    # Event listeners
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.music.schedule_message_cleanup(message)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        await self.music.trim_requester_queue(ctx)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        await self.music.voice_state_update(member, before, after)

    @commands.Cog.listener()
    async def on_red_audio_track_start(self, guild, track, requester):
        if isinstance(guild, discord.Guild):
            await self.music.update_panel(guild)

    @commands.Cog.listener()
    async def on_red_audio_track_end(self, guild, track, requester):
        if isinstance(guild, discord.Guild):
            await self.music.update_panel(guild)

    @commands.Cog.listener()
    async def on_red_audio_queue_end(self, guild, track, requester):
        if isinstance(guild, discord.Guild):
            await self.music.update_panel(guild)

    @commands.Cog.listener()
    async def on_red_audio_audio_disconnect(self, guild):
        if isinstance(guild, discord.Guild):
            await self.music.update_panel(guild)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _update_feed_source(
        self,
        ctx: commands.Context,
        number: int,
        key: str,
        value: Any,
        action: str,
    ):
        old_value = None
        source_name = None

        async with self.config.guild(ctx.guild).feed_sources() as sources:
            if number < 1 or number > len(sources):
                await ctx.send("❌ Feed number không tồn tại.")
                return

            source = sources[number - 1]
            old_value = source.get(key)
            source[key] = value
            source_name = source.get("name")

        await self.audit(
            ctx,
            action=f"{action}: {source_name}",
            before=old_value,
            after=value,
        )
        await ctx.send(f"✅ Updated **{source_name}**: `{key}` = `{value}`")

    @staticmethod
    def _keyword_values(text: str) -> List[str]:
        if text.strip().casefold() in {"none", "clear", "off"}:
            return []

        values = []
        for value in text.split(","):
            value = value.strip()
            if value and value.casefold() not in {
                item.casefold() for item in values
            }:
                values.append(value[:80])

        return values[:30]

    @staticmethod
    def _missing_text_permissions(
        channel: discord.TextChannel,
        *,
        needs_threads: bool,
        needs_pin: bool,
    ) -> List[str]:
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
        if not permissions.embed_links:
            missing.append("Embed Links")
        if needs_threads and not permissions.create_public_threads:
            missing.append("Create Public Threads")
        if needs_threads and not permissions.send_messages_in_threads:
            missing.append("Send Messages in Threads")
        if needs_pin and not permissions.manage_messages:
            missing.append("Manage Messages")
        return missing

    async def audit(
        self,
        ctx: commands.Context,
        *,
        action: str,
        before: Any,
        after: Any,
    ):
        botops = self.bot.get_cog("BotOps")
        if botops is None or not hasattr(botops, "audit"):
            return

        with contextlib.suppress(Exception):
            await botops.audit(
                guild=ctx.guild,
                user=ctx.author,
                action=action,
                before=before,
                after=after,
                result="Success",
            )

    async def report_error(
        self,
        guild: discord.Guild,
        *,
        operation: str,
        error: BaseException,
        ctx: Optional[commands.Context] = None,
    ):
        botops = self.bot.get_cog("BotOps")
        if botops is not None and hasattr(botops, "report_error"):
            with contextlib.suppress(Exception):
                await botops.report_error(
                    guild=guild,
                    operation=operation,
                    error=error,
                    ctx=ctx,
                    cog_name=self.__class__.__name__,
                    command_name=(
                        ctx.command.qualified_name
                        if ctx is not None and ctx.command is not None
                        else "automatic task"
                    ),
                )
                return
