\
from __future__ import annotations

import asyncio
import contextlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import tasks
from red_commons.logging import getLogger
from redbot.core import Config, commands


log = getLogger("red.studyops")
VN_TZ = timezone(timedelta(hours=7), name="UTC+7")

DAY_FMT = "%Y-%m-%d"
DISPLAY_DAY_FMT = "%d/%m/%Y"


@dataclass
class PomoState:
    guild_id: int
    user_id: int
    text_channel_id: int
    voice_channel_id: Optional[int]
    topic: str
    focus_minutes: int
    break_minutes: int
    total_cycles: int
    cycle: int = 1
    phase: str = "focus"
    phase_started: datetime = field(default_factory=lambda: datetime.now(VN_TZ))
    phase_end: datetime = field(default_factory=lambda: datetime.now(VN_TZ))
    paused: bool = False
    pause_started: Optional[datetime] = None
    warned_five_minutes: bool = False
    completed_cycles: int = 0
    task: Optional[asyncio.Task] = None


class StudyOps(commands.Cog):
    """Goals, Pomodoro, study history, and temporary study rooms."""

    __red_end_user_data_statement__ = (
        "This cog stores user goals, study metrics, progress tracks, "
        "temporary room ownership, and Discord user/channel IDs."
    )

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(
            self,
            identifier=2809200503,
            force_registration=True,
        )

        self.config.register_guild(
            owner_id=None,
            daily_goals_channel_id=None,
            progress_channel_id=None,
            study_log_channel_id=None,
            pomodoro_voice_id=None,
            join_to_create_id=None,
            temp_room_category_id=None,
            focus_target_minutes=180,
            morning_hour=7,
            morning_minute=0,
            review_hour=22,
            review_minute=0,
            weekly_hour=20,
            weekly_minute=0,
            empty_room_delay=45,
            track_room_time=True,
            last_daily_post="",
            last_review_post="",
            last_weekly_post="",
            daily_message_ids={},
            temp_rooms={},
        )

        self.config.register_member(
            goals={},
            metrics={},
            progress={},
        )

        self.pomodoros: Dict[Tuple[int, int], PomoState] = {}
        self.room_delete_tasks: Dict[int, asyncio.Task] = {}
        self.voice_join_times: Dict[Tuple[int, int, int], datetime] = {}

        self.scheduler_loop.start()
        self.temp_room_sweeper.start()

    def cog_unload(self):
        self.scheduler_loop.cancel()
        self.temp_room_sweeper.cancel()

        for state in list(self.pomodoros.values()):
            if state.task is not None:
                state.task.cancel()

        for task in list(self.room_delete_tasks.values()):
            task.cancel()

    # ------------------------------------------------------------------
    # Setup commands
    # ------------------------------------------------------------------

    @commands.group(name="studyset")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def studyset(self, ctx: commands.Context):
        """Configure StudyOps."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @studyset.command(name="owner")
    async def studyset_owner(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        """Set the primary user for automatic daily and weekly posts."""

        old_id = await self.config.guild(ctx.guild).owner_id()
        old_member = ctx.guild.get_member(old_id) if old_id else None

        await self.config.guild(ctx.guild).owner_id.set(member.id)
        await self._audit(
            ctx,
            "Changed StudyOps primary user",
            old_member.display_name if old_member else "none",
            member.display_name,
        )
        await ctx.send(f"✅ Primary study user: **{member.display_name}**")

    @studyset.command(name="channel")
    async def studyset_channel(
        self,
        ctx: commands.Context,
        kind: str,
        channel: discord.TextChannel,
    ):
        """Set `daily`, `progress`, or `log` text channel."""

        mapping = {
            "daily": "daily_goals_channel_id",
            "progress": "progress_channel_id",
            "log": "study_log_channel_id",
        }
        key = mapping.get(kind.lower().strip())

        if key is None:
            await ctx.send("❌ Chọn `daily`, `progress`, hoặc `log`.")
            return

        missing = self._missing_text_permissions(channel)
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
        await self._audit(
            ctx,
            f"Changed StudyOps {kind} channel",
            old_channel.mention if old_channel else "none",
            channel.mention,
        )
        await ctx.send(f"✅ `{kind}` channel: {channel.mention}")

    @studyset.command(name="pomovoice")
    async def studyset_pomovoice(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
    ):
        """Set the recommended Pomodoro voice channel."""

        old_id = await self.config.guild(ctx.guild).pomodoro_voice_id()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None

        await self.config.guild(ctx.guild).pomodoro_voice_id.set(channel.id)
        await self._audit(
            ctx,
            "Changed Pomodoro voice channel",
            old_channel.name if old_channel else "none",
            channel.name,
        )
        await ctx.send(f"✅ Pomodoro voice channel: **{channel.name}**")

    @studyset.command(name="jointocreate")
    async def studyset_join_to_create(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
        category: Optional[discord.CategoryChannel] = None,
    ):
        """Set the join-to-create trigger and optional target category."""

        category = category or channel.category

        old_id = await self.config.guild(ctx.guild).join_to_create_id()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None

        await self.config.guild(ctx.guild).join_to_create_id.set(channel.id)
        await self.config.guild(ctx.guild).temp_room_category_id.set(
            category.id if category else None
        )

        await self._audit(
            ctx,
            "Changed join-to-create voice channel",
            old_channel.name if old_channel else "none",
            channel.name,
        )

        category_text = category.name if category else "no category"
        await ctx.send(
            f"✅ Trigger: **{channel.name}**\n"
            f"Temporary-room category: **{category_text}**"
        )

    @studyset.command(name="focus")
    async def studyset_focus_target(
        self,
        ctx: commands.Context,
        minutes: int,
    ):
        """Set the daily focus target in minutes."""

        if not 15 <= minutes <= 1440:
            await ctx.send("❌ Focus target phải từ 15 đến 1440 phút.")
            return

        old_value = await self.config.guild(ctx.guild).focus_target_minutes()
        await self.config.guild(ctx.guild).focus_target_minutes.set(minutes)

        await self._audit(
            ctx,
            "Changed daily focus target",
            f"{old_value} minutes",
            f"{minutes} minutes",
        )
        await ctx.send(f"✅ Daily focus target: **{self._format_minutes(minutes)}**")

    @studyset.command(name="schedule")
    async def studyset_schedule(
        self,
        ctx: commands.Context,
        kind: str,
        hour: int,
        minute: int = 0,
    ):
        """Set `morning`, `review`, or `weekly` schedule in UTC+7."""

        if kind not in {"morning", "review", "weekly"}:
            await ctx.send("❌ Chọn `morning`, `review`, hoặc `weekly`.")
            return

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            await ctx.send("❌ Giờ/phút không hợp lệ.")
            return

        guild_conf = self.config.guild(ctx.guild)
        hour_key = f"{kind}_hour"
        minute_key = f"{kind}_minute"

        old_hour = await getattr(guild_conf, hour_key)()
        old_minute = await getattr(guild_conf, minute_key)()

        await getattr(guild_conf, hour_key).set(hour)
        await getattr(guild_conf, minute_key).set(minute)

        await self._audit(
            ctx,
            f"Changed StudyOps {kind} schedule",
            f"{old_hour:02d}:{old_minute:02d}",
            f"{hour:02d}:{minute:02d}",
        )
        await ctx.send(f"✅ `{kind}` schedule: **{hour:02d}:{minute:02d} UTC+7**")

    @studyset.command(name="emptydelay")
    async def studyset_empty_delay(
        self,
        ctx: commands.Context,
        seconds: int,
    ):
        """Set empty temporary-room deletion delay."""

        if not 30 <= seconds <= 60:
            await ctx.send("❌ Delay phải từ **30 đến 60 giây**.")
            return

        old_value = await self.config.guild(ctx.guild).empty_room_delay()
        await self.config.guild(ctx.guild).empty_room_delay.set(seconds)

        await self._audit(
            ctx,
            "Changed empty-room deletion delay",
            f"{old_value} seconds",
            f"{seconds} seconds",
        )
        await ctx.send(f"✅ Empty rooms will be deleted after **{seconds}s**.")

    @studyset.command(name="roomtracking")
    async def studyset_room_tracking(
        self,
        ctx: commands.Context,
        enabled: bool,
    ):
        """Enable or disable voice-room time logging."""

        old_value = await self.config.guild(ctx.guild).track_room_time()
        await self.config.guild(ctx.guild).track_room_time.set(enabled)

        await self._audit(
            ctx,
            "Changed study-room time tracking",
            str(old_value),
            str(enabled),
        )
        await ctx.send(
            "✅ Study-room time tracking: "
            + ("**enabled**" if enabled else "**disabled**")
        )

    @studyset.command(name="status")
    async def studyset_status(self, ctx: commands.Context):
        """Show StudyOps configuration."""

        data = await self.config.guild(ctx.guild).all()

        def channel_text(key: str) -> str:
            channel_id = data.get(key)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            return channel.mention if isinstance(channel, discord.TextChannel) else (
                channel.name if channel else "Not configured"
            )

        owner = ctx.guild.get_member(data.get("owner_id"))
        await ctx.send(
            "**🎓 STUDYOPS CONFIGURATION**\n\n"
            f"Primary user: **{owner.display_name if owner else 'Not configured'}**\n"
            f"Daily goals: {channel_text('daily_goals_channel_id')}\n"
            f"Weekly progress: {channel_text('progress_channel_id')}\n"
            f"Study log: {channel_text('study_log_channel_id')}\n"
            f"Pomodoro voice: {channel_text('pomodoro_voice_id')}\n"
            f"Join-to-create: {channel_text('join_to_create_id')}\n"
            f"Focus target: `{self._format_minutes(data['focus_target_minutes'])}`\n"
            f"Morning: `{data['morning_hour']:02d}:{data['morning_minute']:02d}`\n"
            f"Review: `{data['review_hour']:02d}:{data['review_minute']:02d}`\n"
            f"Weekly: Sunday `{data['weekly_hour']:02d}:{data['weekly_minute']:02d}`\n"
            f"Empty-room delay: `{data['empty_room_delay']}s`\n"
            f"Room tracking: `{data['track_room_time']}`",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @studyset.command(name="postnow")
    async def studyset_post_now(
        self,
        ctx: commands.Context,
        kind: str,
    ):
        """Post `daily`, `review`, or `weekly` immediately."""

        member = await self._primary_member(ctx.guild)
        if member is None:
            await ctx.send("❌ Chưa cấu hình primary user.")
            return

        kind = kind.lower().strip()
        if kind == "daily":
            await self._post_daily_goals(ctx.guild, member, force=True)
        elif kind == "review":
            await self._post_daily_review(ctx.guild, member, force=True)
        elif kind == "weekly":
            await self._post_weekly_summary(ctx.guild, member, force=True)
        else:
            await ctx.send("❌ Chọn `daily`, `review`, hoặc `weekly`.")
            return

        await ctx.tick()

    # ------------------------------------------------------------------
    # Goal commands
    # ------------------------------------------------------------------

    @commands.group(name="goal")
    @commands.guild_only()
    async def goal(self, ctx: commands.Context):
        """Manage today's goals."""

        if ctx.invoked_subcommand is None:
            await self._send_goal_list(ctx)

    @goal.command(name="add")
    async def goal_add(self, ctx: commands.Context, *, content: str):
        """Add one goal for today."""

        content = content.strip()
        if not content:
            await ctx.send("❌ Goal không được để trống.")
            return

        if len(content) > 300:
            await ctx.send("❌ Goal tối đa 300 ký tự.")
            return

        day_key = self._today_key()

        async with self.config.member(ctx.author).goals() as goals:
            day_goals = goals.setdefault(day_key, [])
            if len(day_goals) >= 25:
                await ctx.send("❌ Tối đa 25 goals mỗi ngày.")
                return

            day_goals.append(
                {
                    "text": content,
                    "done": False,
                    "created_at": self._now().isoformat(),
                    "completed_at": None,
                }
            )
            index = len(day_goals)

        await ctx.send(f"✅ Added goal **#{index}**: {content}")
        await self._refresh_daily_message(ctx.guild, ctx.author)

    @goal.command(name="list")
    async def goal_list(self, ctx: commands.Context):
        """List today's goals."""

        await self._send_goal_list(ctx)

    @goal.command(name="done")
    async def goal_done(self, ctx: commands.Context, number: int):
        """Mark one goal as completed."""

        day_key = self._today_key()

        async with self.config.member(ctx.author).goals() as goals:
            day_goals = goals.get(day_key, [])

            if number < 1 or number > len(day_goals):
                await ctx.send("❌ Goal number không tồn tại.")
                return

            goal_item = day_goals[number - 1]
            goal_item["done"] = True
            goal_item["completed_at"] = self._now().isoformat()
            content = goal_item["text"]

        await ctx.send(f"✅ Completed goal **#{number}**: {content}")
        await self._refresh_daily_message(ctx.guild, ctx.author)

    @goal.command(name="remove")
    async def goal_remove(self, ctx: commands.Context, number: int):
        """Remove one goal."""

        day_key = self._today_key()

        async with self.config.member(ctx.author).goals() as goals:
            day_goals = goals.get(day_key, [])

            if number < 1 or number > len(day_goals):
                await ctx.send("❌ Goal number không tồn tại.")
                return

            removed = day_goals.pop(number - 1)

        await ctx.send(f"🗑 Removed: {removed['text']}")
        await self._refresh_daily_message(ctx.guild, ctx.author)

    @goal.command(name="carry")
    async def goal_carry(self, ctx: commands.Context):
        """Carry unfinished goals from yesterday into today."""

        today = self._now().date()
        today_key = today.strftime(DAY_FMT)
        yesterday_key = (today - timedelta(days=1)).strftime(DAY_FMT)

        carried = []

        async with self.config.member(ctx.author).goals() as goals:
            yesterday_goals = goals.get(yesterday_key, [])
            today_goals = goals.setdefault(today_key, [])
            existing = {item["text"].casefold() for item in today_goals}

            for item in yesterday_goals:
                text = item.get("text", "").strip()
                if not item.get("done") and text and text.casefold() not in existing:
                    today_goals.append(
                        {
                            "text": text,
                            "done": False,
                            "created_at": self._now().isoformat(),
                            "completed_at": None,
                            "carried_from": yesterday_key,
                        }
                    )
                    existing.add(text.casefold())
                    carried.append(text)

        if not carried:
            await ctx.send("ℹ️ Không có goal chưa hoàn thành để carry.")
            return

        await ctx.send(f"✅ Carried **{len(carried)}** goal(s) into today.")
        await self._refresh_daily_message(ctx.guild, ctx.author)

    @goal.command(name="stats")
    async def goal_stats(self, ctx: commands.Context):
        """Show seven-day goal and focus statistics."""

        stats = await self._calculate_stats(ctx.author, days=7)

        await ctx.send(
            "**📊 7-DAY STUDY STATS**\n\n"
            f"Goals: `{stats['completed_goals']}/{stats['total_goals']}` completed\n"
            f"Completion rate: `{stats['completion_rate']:.0f}%`\n"
            f"Focused time: `{self._format_minutes(stats['focus_minutes'])}`\n"
            f"Pomodoro sessions: `{stats['pomodoro_sessions']}`\n"
            f"Study-room time: `{self._format_minutes(stats['voice_minutes'])}`\n"
            f"Current streak: `{stats['streak']} day(s)`"
        )

    async def _send_goal_list(self, ctx: commands.Context):
        goals = await self._get_goals(ctx.author, self._today_key())
        target = await self.config.guild(ctx.guild).focus_target_minutes()

        await ctx.send(
            self._build_daily_goal_text(goals, target),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # ------------------------------------------------------------------
    # Progress commands
    # ------------------------------------------------------------------

    @commands.group(name="progress")
    @commands.guild_only()
    async def progress(self, ctx: commands.Context):
        """Track long-term IELTS, MLOps, System, and project progress."""

        if ctx.invoked_subcommand is None:
            await self._send_progress(ctx)

    @progress.command(name="set")
    async def progress_set(
        self,
        ctx: commands.Context,
        track: str,
        percent: int,
        *,
        note: str = "",
    ):
        """Set a progress track, e.g. `!progress set IELTS 45 Listening B1`."""

        if not 0 <= percent <= 100:
            await ctx.send("❌ Percent phải từ 0 đến 100.")
            return

        track = track.strip()
        if not track or len(track) > 50:
            await ctx.send("❌ Track name phải từ 1 đến 50 ký tự.")
            return

        async with self.config.member(ctx.author).progress() as progress:
            progress[track] = {
                "percent": percent,
                "note": note[:300],
                "updated_at": self._now().isoformat(),
            }

        await ctx.send(f"✅ **{track}** progress: **{percent}%**")
        await self._audit(
            ctx,
            f"Updated study progress: {track}",
            "previous value",
            f"{percent}% — {note or 'no note'}",
        )

    @progress.command(name="remove")
    async def progress_remove(self, ctx: commands.Context, *, track: str):
        """Remove a progress track."""

        removed = None

        async with self.config.member(ctx.author).progress() as progress:
            matching_key = next(
                (key for key in progress if key.casefold() == track.casefold()),
                None,
            )
            if matching_key is not None:
                removed = progress.pop(matching_key)

        if removed is None:
            await ctx.send("❌ Track không tồn tại.")
            return

        await ctx.send(f"🗑 Removed progress track: **{track}**")

    @progress.command(name="list")
    async def progress_list(self, ctx: commands.Context):
        """List long-term progress tracks."""

        await self._send_progress(ctx)

    async def _send_progress(self, ctx: commands.Context):
        progress = await self.config.member(ctx.author).progress()

        if not progress:
            await ctx.send(
                "ℹ️ Chưa có progress track.\n"
                f"Dùng `{ctx.clean_prefix}progress set IELTS 20 Foundation`."
            )
            return

        lines = ["**🏛 LONG-TERM PROGRESS**", ""]

        for track, item in sorted(progress.items()):
            percent = int(item.get("percent", 0))
            note = item.get("note") or "No note"
            bar = self._progress_bar(percent)
            lines.append(f"**{track}** — `{percent}%` {bar}")
            lines.append(f"└ {note}")

        await ctx.send("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

    # ------------------------------------------------------------------
    # Pomodoro commands
    # ------------------------------------------------------------------

    @commands.group(name="pomo")
    @commands.guild_only()
    async def pomo(self, ctx: commands.Context):
        """Run Pomodoro focus sessions."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @pomo.command(name="start")
    async def pomo_start(
        self,
        ctx: commands.Context,
        focus_minutes: int = 25,
        break_minutes: int = 5,
        cycles: int = 4,
        *,
        topic: str = "Focus",
    ):
        """Start: `!pomo start 50 10 4 Kubernetes`."""

        key = (ctx.guild.id, ctx.author.id)
        if key in self.pomodoros:
            await ctx.send("❌ Bạn đã có một Pomodoro đang chạy.")
            return

        if not 1 <= focus_minutes <= 180:
            await ctx.send("❌ Focus phải từ 1 đến 180 phút.")
            return

        if not 1 <= break_minutes <= 60:
            await ctx.send("❌ Break phải từ 1 đến 60 phút.")
            return

        if not 1 <= cycles <= 12:
            await ctx.send("❌ Cycles phải từ 1 đến 12.")
            return

        voice_channel = (
            ctx.author.voice.channel
            if ctx.author.voice and ctx.author.voice.channel
            else None
        )

        configured_voice_id = await self.config.guild(ctx.guild).pomodoro_voice_id()
        if configured_voice_id and (
            voice_channel is None or voice_channel.id != configured_voice_id
        ):
            configured_voice = ctx.guild.get_channel(configured_voice_id)
            warning = (
                f"\nℹ️ Recommended voice room: **{configured_voice.name}**"
                if configured_voice
                else ""
            )
        else:
            warning = ""

        now = self._now()
        state = PomoState(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            text_channel_id=ctx.channel.id,
            voice_channel_id=voice_channel.id if voice_channel else None,
            topic=topic.strip()[:100] or "Focus",
            focus_minutes=focus_minutes,
            break_minutes=break_minutes,
            total_cycles=cycles,
            phase_started=now,
            phase_end=now + timedelta(minutes=focus_minutes),
        )

        self.pomodoros[key] = state
        state.task = asyncio.create_task(self._run_pomodoro(state))

        await ctx.send(
            "🍅 **POMODORO STARTED**\n\n"
            f"Topic: **{state.topic}**\n"
            f"Focus: `{focus_minutes}m`\n"
            f"Break: `{break_minutes}m`\n"
            f"Cycles: `{cycles}`"
            f"{warning}"
        )

    @pomo.command(name="pause")
    async def pomo_pause(self, ctx: commands.Context):
        """Pause your active Pomodoro."""

        state = self.pomodoros.get((ctx.guild.id, ctx.author.id))
        if state is None:
            await ctx.send("❌ Không có Pomodoro đang chạy.")
            return

        if state.paused:
            await ctx.send("ℹ️ Pomodoro đã pause.")
            return

        state.paused = True
        state.pause_started = self._now()

        voice = ctx.guild.get_channel(state.voice_channel_id) if state.voice_channel_id else None
        if isinstance(voice, discord.VoiceChannel):
            await self._set_voice_status(
                voice,
                f"Paused • {state.topic}",
            )

        await ctx.send("⏸ Pomodoro paused.")

    @pomo.command(name="resume")
    async def pomo_resume(self, ctx: commands.Context):
        """Resume your active Pomodoro."""

        state = self.pomodoros.get((ctx.guild.id, ctx.author.id))
        if state is None:
            await ctx.send("❌ Không có Pomodoro đang chạy.")
            return

        if not state.paused:
            await ctx.send("ℹ️ Pomodoro không ở trạng thái pause.")
            return

        now = self._now()
        if state.pause_started is not None:
            state.phase_end += now - state.pause_started

        state.paused = False
        state.pause_started = None

        await ctx.send("▶️ Pomodoro resumed.")

    @pomo.command(name="stop")
    async def pomo_stop(self, ctx: commands.Context):
        """Stop your active Pomodoro."""

        key = (ctx.guild.id, ctx.author.id)
        state = self.pomodoros.get(key)

        if state is None:
            await ctx.send("❌ Không có Pomodoro đang chạy.")
            return

        if state.task is not None:
            state.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.task

        await ctx.send(
            "⏹ **POMODORO STOPPED**\n"
            f"Completed focus sessions: `{state.completed_cycles}/{state.total_cycles}`"
        )

    @pomo.command(name="stats")
    async def pomo_stats(self, ctx: commands.Context):
        """Show today's and seven-day Pomodoro statistics."""

        today_stats = await self._calculate_stats(ctx.author, days=1)
        week_stats = await self._calculate_stats(ctx.author, days=7)

        await ctx.send(
            "**🍅 POMODORO STATS**\n\n"
            f"Today: `{today_stats['pomodoro_sessions']}` sessions • "
            f"`{self._format_minutes(today_stats['focus_minutes'])}`\n"
            f"Last 7 days: `{week_stats['pomodoro_sessions']}` sessions • "
            f"`{self._format_minutes(week_stats['focus_minutes'])}`"
        )

    async def _run_pomodoro(self, state: PomoState):
        key = (state.guild_id, state.user_id)
        guild = self.bot.get_guild(state.guild_id)

        try:
            while state.cycle <= state.total_cycles:
                state.phase = "focus"
                state.warned_five_minutes = False
                state.phase_started = self._now()
                state.phase_end = state.phase_started + timedelta(
                    minutes=state.focus_minutes
                )

                await self._send_pomo_notice(
                    state,
                    "🎯 **FOCUS STARTED**\n"
                    f"Cycle: `{state.cycle}/{state.total_cycles}`\n"
                    f"Topic: **{state.topic}**\n"
                    f"Duration: `{state.focus_minutes} minutes`",
                )

                await self._run_pomo_phase(state)

                focus_end = self._now()
                state.completed_cycles += 1

                if guild is not None:
                    member = guild.get_member(state.user_id)
                    if member is not None:
                        await self._record_study(
                            member=member,
                            guild=guild,
                            topic=state.topic,
                            minutes=state.focus_minutes,
                            start=state.phase_started,
                            end=focus_end,
                            source="pomodoro",
                        )

                if state.cycle >= state.total_cycles:
                    break

                await self._send_pomo_notice(
                    state,
                    "☕ **FOCUS COMPLETE — BREAK STARTED**\n"
                    f"Cycle: `{state.cycle}/{state.total_cycles}`\n"
                    f"Break: `{state.break_minutes} minutes`",
                )

                state.phase = "break"
                state.warned_five_minutes = False
                state.phase_started = self._now()
                state.phase_end = state.phase_started + timedelta(
                    minutes=state.break_minutes
                )

                await self._run_pomo_phase(state)

                await self._send_pomo_notice(
                    state,
                    "🔔 **BREAK COMPLETE**\n"
                    f"Next focus cycle: `{state.cycle + 1}/{state.total_cycles}`",
                )

                state.cycle += 1

            await self._send_pomo_notice(
                state,
                "🏁 **POMODORO COMPLETE**\n\n"
                f"Topic: **{state.topic}**\n"
                f"Completed: `{state.completed_cycles}/{state.total_cycles}` focus sessions\n"
                f"Focused time: `{self._format_minutes(state.completed_cycles * state.focus_minutes)}`",
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if guild is not None:
                await self._report_error(
                    guild,
                    operation=f"Run Pomodoro for user {state.user_id}",
                    error=exc,
                )
            else:
                log.exception("Pomodoro loop failed", exc_info=exc)
        finally:
            if guild is not None and state.voice_channel_id:
                voice = guild.get_channel(state.voice_channel_id)
                if isinstance(voice, discord.VoiceChannel):
                    await self._set_voice_status(voice, None)

            self.pomodoros.pop(key, None)

    async def _run_pomo_phase(self, state: PomoState):
        last_status_second: Optional[int] = None

        while True:
            if state.paused:
                await asyncio.sleep(1)
                continue

            now = self._now()
            remaining = max(0, int((state.phase_end - now).total_seconds()))

            if remaining <= 0:
                break

            if (
                state.phase == "focus"
                and remaining <= 300
                and not state.warned_five_minutes
                and state.focus_minutes > 5
            ):
                state.warned_five_minutes = True
                await self._send_pomo_notice(
                    state,
                    "⏳ **5 MINUTES REMAINING**\n"
                    f"Cycle: `{state.cycle}/{state.total_cycles}`\n"
                    f"Topic: **{state.topic}**",
                )

            # Update the ephemeral voice-channel status about every 30 seconds.
            status_bucket = remaining // 30
            if status_bucket != last_status_second:
                last_status_second = status_bucket
                guild = self.bot.get_guild(state.guild_id)
                voice = (
                    guild.get_channel(state.voice_channel_id)
                    if guild is not None and state.voice_channel_id
                    else None
                )

                if isinstance(voice, discord.VoiceChannel):
                    label = "Focus" if state.phase == "focus" else "Break"
                    await self._set_voice_status(
                        voice,
                        f"{label} {state.cycle}/{state.total_cycles} — "
                        f"{self._format_seconds(remaining)} • {state.topic}",
                    )

            await asyncio.sleep(min(5, remaining))

    async def _send_pomo_notice(self, state: PomoState, content: str):
        channel = self.bot.get_channel(state.text_channel_id)
        if isinstance(channel, discord.TextChannel):
            with contextlib.suppress(discord.HTTPException):
                await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    # ------------------------------------------------------------------
    # Temporary room commands
    # ------------------------------------------------------------------

    @commands.group(name="room")
    @commands.guild_only()
    async def room(self, ctx: commands.Context):
        """Manage your join-to-create study room."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @room.command(name="lock")
    async def room_lock(self, ctx: commands.Context):
        """Lock your temporary study room."""

        channel = await self._owned_temp_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                connect=False,
                reason=f"Study room locked by {ctx.author}",
            )
            await channel.set_permissions(
                ctx.author,
                view_channel=True,
                connect=True,
                move_members=True,
                reason="Preserve study-room owner access",
            )
        except discord.HTTPException as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Lock study room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await self._audit(ctx, "Locked study room", "unlocked", channel.name)
        await ctx.send("🔒 Room locked.")

    @room.command(name="unlock")
    async def room_unlock(self, ctx: commands.Context):
        """Unlock your temporary study room."""

        channel = await self._owned_temp_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                connect=None,
                reason=f"Study room unlocked by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Unlock study room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await self._audit(ctx, "Unlocked study room", "locked", channel.name)
        await ctx.send("🔓 Room unlocked.")

    @room.command(name="limit")
    async def room_limit(self, ctx: commands.Context, limit: int):
        """Set room user limit from 0 to 99."""

        channel = await self._owned_temp_room(ctx)
        if channel is None:
            return

        if not 0 <= limit <= 99:
            await ctx.send("❌ Limit phải từ 0 đến 99; 0 là không giới hạn.")
            return

        old_limit = channel.user_limit

        try:
            await channel.edit(
                user_limit=limit,
                reason=f"Study room limit changed by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Change limit for room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await self._audit(
            ctx,
            "Changed study room user limit",
            str(old_limit),
            str(limit),
        )
        await ctx.send(f"👥 Room limit: **{limit or 'unlimited'}**")

    @room.command(name="rename")
    async def room_rename(self, ctx: commands.Context, *, name: str):
        """Rename your temporary study room."""

        channel = await self._owned_temp_room(ctx)
        if channel is None:
            return

        name = name.strip()
        if not 1 <= len(name) <= 100:
            await ctx.send("❌ Tên phòng phải từ 1 đến 100 ký tự.")
            return

        old_name = channel.name

        try:
            await channel.edit(
                name=name,
                reason=f"Study room renamed by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Rename study room {old_name}",
                error=exc,
                ctx=ctx,
            )
            return

        await self._audit(ctx, "Renamed study room", old_name, name)
        await ctx.send(f"✏️ Room renamed to **{name}**.")

    @room.command(name="permit")
    async def room_permit(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        """Permit one member to join your locked room."""

        channel = await self._owned_temp_room(ctx)
        if channel is None:
            return

        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                connect=True,
                reason=f"Study room permit granted by {ctx.author}",
            )
        except discord.HTTPException as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Permit user in room {channel.name}",
                error=exc,
                ctx=ctx,
            )
            return

        await self._audit(
            ctx,
            "Permitted user in study room",
            "not permitted",
            member.display_name,
        )
        await ctx.send(f"✅ Permitted **{member.display_name}**.")

    async def _owned_temp_room(
        self,
        ctx: commands.Context,
    ) -> Optional[discord.VoiceChannel]:
        voice = ctx.author.voice
        if voice is None or not isinstance(voice.channel, discord.VoiceChannel):
            await ctx.send("❌ Bạn phải ở trong temporary study room.")
            return None

        rooms = await self.config.guild(ctx.guild).temp_rooms()
        room_data = rooms.get(str(voice.channel.id))

        is_admin = ctx.author.guild_permissions.manage_channels
        if not room_data or (
            int(room_data.get("owner_id", 0)) != ctx.author.id and not is_admin
        ):
            await ctx.send("❌ Đây không phải room bạn sở hữu.")
            return None

        return voice.channel

    # ------------------------------------------------------------------
    # Voice events and temporary-room lifecycle
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        guild = member.guild
        guild_conf = self.config.guild(guild)

        trigger_id = await guild_conf.join_to_create_id()

        if after.channel is not None and after.channel.id == trigger_id:
            await self._create_temp_room(member, after.channel)
            return

        if before.channel is not None and before.channel != after.channel:
            await self._finish_voice_tracking(member, before.channel)
            await self._maybe_schedule_room_delete(before.channel)

        if after.channel is not None and before.channel != after.channel:
            await self._start_voice_tracking(member, after.channel)

            delete_task = self.room_delete_tasks.pop(after.channel.id, None)
            if delete_task is not None:
                delete_task.cancel()

    async def _create_temp_room(
        self,
        member: discord.Member,
        trigger: discord.VoiceChannel,
    ):
        guild = member.guild
        guild_conf = self.config.guild(guild)

        category_id = await guild_conf.temp_room_category_id()
        category = guild.get_channel(category_id) if category_id else trigger.category
        room_name = f"Study • {member.display_name}"[:100]

        try:
            room = await guild.create_voice_channel(
                room_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                bitrate=trigger.bitrate,
                user_limit=0,
                overwrites=trigger.overwrites,
                reason=f"Join-to-create room for {member}",
            )

            await room.set_permissions(
                member,
                view_channel=True,
                connect=True,
                move_members=True,
                manage_channels=True,
                reason="Temporary study-room owner permissions",
            )

            async with guild_conf.temp_rooms() as rooms:
                rooms[str(room.id)] = {
                    "owner_id": member.id,
                    "created_at": self._now().isoformat(),
                    "name": room.name,
                }

            await member.move_to(
                room,
                reason="Move member into newly-created study room",
            )

            await self._start_voice_tracking(member, room)

        except discord.HTTPException as exc:
            await self._report_error(
                guild,
                operation=f"Create temporary study room for {member.display_name}",
                error=exc,
            )

    async def _start_voice_tracking(
        self,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
    ):
        if not isinstance(channel, discord.VoiceChannel):
            return

        rooms = await self.config.guild(member.guild).temp_rooms()
        if str(channel.id) not in rooms:
            return

        self.voice_join_times[(member.guild.id, member.id, channel.id)] = self._now()

    async def _finish_voice_tracking(
        self,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
    ):
        if not isinstance(channel, discord.VoiceChannel):
            return

        key = (member.guild.id, member.id, channel.id)
        started = self.voice_join_times.pop(key, None)

        if started is None:
            return

        if not await self.config.guild(member.guild).track_room_time():
            return

        ended = self._now()
        minutes = int((ended - started).total_seconds() // 60)

        if minutes < 5:
            return

        await self._record_study(
            member=member,
            guild=member.guild,
            topic=channel.name,
            minutes=minutes,
            start=started,
            end=ended,
            source="voice",
        )

    async def _maybe_schedule_room_delete(
        self,
        channel: discord.abc.GuildChannel,
    ):
        if not isinstance(channel, discord.VoiceChannel):
            return

        rooms = await self.config.guild(channel.guild).temp_rooms()
        if str(channel.id) not in rooms:
            return

        if any(not member.bot for member in channel.members):
            return

        old_task = self.room_delete_tasks.pop(channel.id, None)
        if old_task is not None:
            old_task.cancel()

        delay = await self.config.guild(channel.guild).empty_room_delay()
        self.room_delete_tasks[channel.id] = asyncio.create_task(
            self._delete_empty_room_after(channel.id, channel.guild.id, delay)
        )

    async def _delete_empty_room_after(
        self,
        channel_id: int,
        guild_id: int,
        delay: int,
    ):
        try:
            await asyncio.sleep(delay)

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return

            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                await self._remove_temp_room_config(guild, channel_id)
                return

            if any(not member.bot for member in channel.members):
                return

            await channel.delete(reason="Temporary study room became empty")
            await self._remove_temp_room_config(guild, channel_id)

        except asyncio.CancelledError:
            raise
        except discord.HTTPException as exc:
            guild = self.bot.get_guild(guild_id)
            if guild is not None:
                await self._report_error(
                    guild,
                    operation=f"Delete empty temporary room {channel_id}",
                    error=exc,
                )
        finally:
            self.room_delete_tasks.pop(channel_id, None)

    async def _remove_temp_room_config(
        self,
        guild: discord.Guild,
        channel_id: int,
    ):
        async with self.config.guild(guild).temp_rooms() as rooms:
            rooms.pop(str(channel_id), None)

    # ------------------------------------------------------------------
    # Study recording and automatic posts
    # ------------------------------------------------------------------

    async def _record_study(
        self,
        *,
        member: discord.Member,
        guild: discord.Guild,
        topic: str,
        minutes: int,
        start: datetime,
        end: datetime,
        source: str,
    ):
        day_key = end.strftime(DAY_FMT)

        async with self.config.member(member).metrics() as metrics:
            day = metrics.setdefault(
                day_key,
                {
                    "focus_minutes": 0,
                    "pomodoro_sessions": 0,
                    "voice_minutes": 0,
                    "logs": [],
                },
            )

            if source == "pomodoro":
                day["focus_minutes"] = int(day.get("focus_minutes", 0)) + minutes
                day["pomodoro_sessions"] = int(day.get("pomodoro_sessions", 0)) + 1
            else:
                day["voice_minutes"] = int(day.get("voice_minutes", 0)) + minutes

            logs = day.setdefault("logs", [])
            logs.append(
                {
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                    "topic": topic[:100],
                    "minutes": minutes,
                    "source": source,
                }
            )

            focus_total = int(day.get("focus_minutes", 0))
            voice_total = int(day.get("voice_minutes", 0))

        channel_id = await self.config.guild(guild).study_log_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None

        if isinstance(channel, discord.TextChannel):
            total = focus_total if source == "pomodoro" else voice_total
            suffix = "" if source == "pomodoro" else " • voice room"

            with contextlib.suppress(discord.HTTPException):
                await channel.send(
                    f"`{start.strftime('%H:%M')}–{end.strftime('%H:%M')}`"
                    f" | **{topic}** | `{minutes} phút`{suffix}\n"
                    f"Total today ({'focus' if source == 'pomodoro' else 'voice'}): "
                    f"`{self._format_minutes(total)}`",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    @tasks.loop(seconds=60)
    async def scheduler_loop(self):
        now = self._now()
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            member = guild.get_member(data.get("owner_id"))
            if member is None:
                continue

            today_key = now.strftime(DAY_FMT)

            if (
                data.get("last_daily_post") != today_key
                and self._within_schedule_window(
                    now,
                    int(data.get("morning_hour", 7)),
                    int(data.get("morning_minute", 0)),
                    180,
                )
            ):
                await self._post_daily_goals(guild, member)

            if (
                data.get("last_review_post") != today_key
                and self._within_schedule_window(
                    now,
                    int(data.get("review_hour", 22)),
                    int(data.get("review_minute", 0)),
                    180,
                )
            ):
                await self._post_daily_review(guild, member)

            week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
            if (
                now.weekday() == 6
                and data.get("last_weekly_post") != week_key
                and self._within_schedule_window(
                    now,
                    int(data.get("weekly_hour", 20)),
                    int(data.get("weekly_minute", 0)),
                    240,
                )
            ):
                await self._post_weekly_summary(guild, member)

    @scheduler_loop.before_loop
    async def before_scheduler_loop(self):
        await self.bot.wait_until_ready()

    async def _post_daily_goals(
        self,
        guild: discord.Guild,
        member: discord.Member,
        *,
        force: bool = False,
    ):
        channel_id = await self.config.guild(guild).daily_goals_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        goals = await self._get_goals(member, self._today_key())
        target = await self.config.guild(guild).focus_target_minutes()
        content = self._build_daily_goal_text(goals, target)

        try:
            message = await channel.send(
                content,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            await self._report_error(
                guild,
                operation="Post daily study goals",
                error=exc,
            )
            return

        day_key = self._today_key()
        async with self.config.guild(guild).daily_message_ids() as message_ids:
            message_ids[day_key] = message.id
            self._trim_date_mapping(message_ids, 40)

        if not force:
            await self.config.guild(guild).last_daily_post.set(day_key)

    async def _post_daily_review(
        self,
        guild: discord.Guild,
        member: discord.Member,
        *,
        force: bool = False,
    ):
        channel_id = await self.config.guild(guild).daily_goals_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        day_key = self._today_key()
        goals = await self._get_goals(member, day_key)
        metrics = await self._get_day_metrics(member, day_key)
        target = await self.config.guild(guild).focus_target_minutes()

        content = self._build_daily_goal_text(
            goals,
            target,
            include_review=True,
            metrics=metrics,
        )

        message_ids = await self.config.guild(guild).daily_message_ids()
        message_id = message_ids.get(day_key)
        updated = False

        if message_id:
            with contextlib.suppress(discord.HTTPException):
                message = await channel.fetch_message(int(message_id))
                await message.edit(
                    content=content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                updated = True

        if not updated:
            with contextlib.suppress(discord.HTTPException):
                message = await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                async with self.config.guild(guild).daily_message_ids() as stored:
                    stored[day_key] = message.id
                    self._trim_date_mapping(stored, 40)

        if not force:
            await self.config.guild(guild).last_review_post.set(day_key)

    async def _refresh_daily_message(
        self,
        guild: discord.Guild,
        member: discord.Member,
    ):
        day_key = self._today_key()
        message_ids = await self.config.guild(guild).daily_message_ids()
        message_id = message_ids.get(day_key)

        if not message_id:
            return

        channel_id = await self.config.guild(guild).daily_goals_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        goals = await self._get_goals(member, day_key)
        target = await self.config.guild(guild).focus_target_minutes()

        try:
            message = await channel.fetch_message(int(message_id))
            await message.edit(
                content=self._build_daily_goal_text(goals, target),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.NotFound:
            async with self.config.guild(guild).daily_message_ids() as stored:
                stored.pop(day_key, None)
        except discord.HTTPException:
            pass

    async def _post_weekly_summary(
        self,
        guild: discord.Guild,
        member: discord.Member,
        *,
        force: bool = False,
    ):
        channel_id = await self.config.guild(guild).progress_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        stats = await self._calculate_stats(member, days=7)
        progress = await self.config.member(member).progress()

        lines = [
            "🏛 **WEEKLY STUDY REPORT**",
            "",
            f"Period: `{(self._now().date() - timedelta(days=6)).strftime(DISPLAY_DAY_FMT)}"
            f"–{self._now().date().strftime(DISPLAY_DAY_FMT)}`",
            f"Goals completed: `{stats['completed_goals']}/{stats['total_goals']}` "
            f"(`{stats['completion_rate']:.0f}%`)",
            f"Focused time: `{self._format_minutes(stats['focus_minutes'])}`",
            f"Pomodoro sessions: `{stats['pomodoro_sessions']}`",
            f"Study-room time: `{self._format_minutes(stats['voice_minutes'])}`",
            f"Current streak: `{stats['streak']} day(s)`",
        ]

        if progress:
            lines.extend(["", "**Long-term tracks**"])
            for track, item in sorted(progress.items()):
                percent = int(item.get("percent", 0))
                note = item.get("note") or "No note"
                lines.append(
                    f"• **{track}** — `{percent}%` {self._progress_bar(percent)}"
                )
                lines.append(f"  {note}")

        try:
            await channel.send(
                "\n".join(lines),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            await self._report_error(
                guild,
                operation="Post weekly study report",
                error=exc,
            )
            return

        if not force:
            now = self._now()
            week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
            await self.config.guild(guild).last_weekly_post.set(week_key)

    # ------------------------------------------------------------------
    # Temporary room sweeper
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def temp_room_sweeper(self):
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            rooms = data.get("temp_rooms", {})
            for channel_id_text in list(rooms):
                channel_id = int(channel_id_text)
                channel = guild.get_channel(channel_id)

                if not isinstance(channel, discord.VoiceChannel):
                    await self._remove_temp_room_config(guild, channel_id)
                    continue

                if not any(not member.bot for member in channel.members):
                    await self._maybe_schedule_room_delete(channel)

    @temp_room_sweeper.before_loop
    async def before_temp_room_sweeper(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(VN_TZ)

    def _today_key(self) -> str:
        return self._now().strftime(DAY_FMT)

    async def _primary_member(
        self,
        guild: discord.Guild,
    ) -> Optional[discord.Member]:
        owner_id = await self.config.guild(guild).owner_id()
        return guild.get_member(owner_id) if owner_id else None

    async def _get_goals(
        self,
        member: discord.Member,
        day_key: str,
    ) -> List[Dict[str, Any]]:
        all_goals = await self.config.member(member).goals()
        return list(all_goals.get(day_key, []))

    async def _get_day_metrics(
        self,
        member: discord.Member,
        day_key: str,
    ) -> Dict[str, Any]:
        metrics = await self.config.member(member).metrics()
        return dict(
            metrics.get(
                day_key,
                {
                    "focus_minutes": 0,
                    "pomodoro_sessions": 0,
                    "voice_minutes": 0,
                    "logs": [],
                },
            )
        )

    def _build_daily_goal_text(
        self,
        goals: List[Dict[str, Any]],
        focus_target_minutes: int,
        *,
        include_review: bool = False,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> str:
        now = self._now()
        lines = [f"📚 **DAILY GOALS — {now.strftime(DISPLAY_DAY_FMT)}**", ""]

        if goals:
            for index, item in enumerate(goals, start=1):
                mark = "x" if item.get("done") else " "
                lines.append(f"{index}. [{mark}] {item.get('text', 'Untitled goal')}")
        else:
            lines.append("_No goals yet._")

        lines.extend(
            [
                "",
                f"Focus target: **{self._format_minutes(focus_target_minutes)}**",
                "Use: `!goal done 1`",
            ]
        )

        if include_review:
            metrics = metrics or {}
            completed = sum(1 for item in goals if item.get("done"))
            remaining = [item.get("text", "Untitled") for item in goals if not item.get("done")]
            remaining_text = ", ".join(remaining) if remaining else "None"

            lines.extend(
                [
                    "",
                    "📊 **DAILY REVIEW**",
                    "",
                    f"Completed: `{completed}/{len(goals)}`",
                    f"Focused time: `{self._format_minutes(int(metrics.get('focus_minutes', 0)))}`",
                    f"Pomodoro sessions: `{int(metrics.get('pomodoro_sessions', 0))}`",
                    f"Remaining: {remaining_text}",
                ]
            )

        return "\n".join(lines)

    async def _calculate_stats(
        self,
        member: discord.Member,
        *,
        days: int,
    ) -> Dict[str, Any]:
        goals = await self.config.member(member).goals()
        metrics = await self.config.member(member).metrics()

        today = self._now().date()
        total_goals = 0
        completed_goals = 0
        focus_minutes = 0
        pomodoro_sessions = 0
        voice_minutes = 0

        for offset in range(days):
            day_key = (today - timedelta(days=offset)).strftime(DAY_FMT)
            day_goals = goals.get(day_key, [])
            day_metrics = metrics.get(day_key, {})

            total_goals += len(day_goals)
            completed_goals += sum(1 for item in day_goals if item.get("done"))
            focus_minutes += int(day_metrics.get("focus_minutes", 0))
            pomodoro_sessions += int(day_metrics.get("pomodoro_sessions", 0))
            voice_minutes += int(day_metrics.get("voice_minutes", 0))

        completion_rate = (
            completed_goals / total_goals * 100 if total_goals else 0.0
        )

        streak = 0
        for offset in range(366):
            day_key = (today - timedelta(days=offset)).strftime(DAY_FMT)
            day_goals = goals.get(day_key, [])
            day_metrics = metrics.get(day_key, {})

            active = (
                any(item.get("done") for item in day_goals)
                or int(day_metrics.get("focus_minutes", 0)) > 0
            )

            if not active:
                break

            streak += 1

        return {
            "total_goals": total_goals,
            "completed_goals": completed_goals,
            "completion_rate": completion_rate,
            "focus_minutes": focus_minutes,
            "pomodoro_sessions": pomodoro_sessions,
            "voice_minutes": voice_minutes,
            "streak": streak,
        }

    @staticmethod
    def _within_schedule_window(
        now: datetime,
        hour: int,
        minute: int,
        window_minutes: int,
    ) -> bool:
        scheduled = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        delta = (now - scheduled).total_seconds()
        return 0 <= delta <= window_minutes * 60

    @staticmethod
    def _format_minutes(minutes: int) -> str:
        minutes = max(0, int(minutes))
        hours, remaining = divmod(minutes, 60)

        if hours and remaining:
            return f"{hours}h {remaining:02d}m"
        if hours:
            return f"{hours}h"
        return f"{remaining}m"

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        minutes, seconds = divmod(max(0, int(seconds)), 60)
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _progress_bar(percent: int) -> str:
        filled = max(0, min(10, round(percent / 10)))
        return "█" * filled + "░" * (10 - filled)

    @staticmethod
    def _trim_date_mapping(mapping: Dict[str, Any], keep: int):
        if len(mapping) <= keep:
            return

        for key in sorted(mapping)[:-keep]:
            mapping.pop(key, None)

    @staticmethod
    def _missing_text_permissions(
        channel: discord.TextChannel,
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

        return missing

    async def _set_voice_status(
        self,
        channel: discord.VoiceChannel,
        status: Optional[str],
    ) -> bool:
        """Set Discord's ephemeral voice-channel status via the official endpoint."""

        try:
            route_cls = getattr(discord.http, "Route", None)
            if route_cls is None:
                return False

            route = route_cls(
                "PUT",
                "/channels/{channel_id}/voice-status",
                channel_id=channel.id,
            )
            await self.bot.http.request(
                route,
                json={"status": status[:500] if status else None},
            )
            return True
        except discord.HTTPException as exc:
            log.debug(
                "Unable to set voice status for channel %s",
                channel.id,
                exc_info=exc,
            )
            return False
        except Exception as exc:
            log.debug(
                "Voice-status compatibility failure for channel %s",
                channel.id,
                exc_info=exc,
            )
            return False

    async def _audit(
        self,
        ctx: commands.Context,
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

    async def _report_error(
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

        log.exception("StudyOps operation failed: %s", operation, exc_info=error)
