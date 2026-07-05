from __future__ import annotations

import contextlib
import io
import json
import random
from datetime import datetime, timedelta
from typing import Any

import discord
from redbot.core import commands

from .advisor import StudyAdvisor
from .parsing import parse_int_range, parse_key_value_tail, split_subject_goal
from .studyops import DAY_FMT
from .vocab_bank import VOCAB_BANK

DEFAULT_MODULES = {"questions": True, "studylog": True, "vocab": False, "goals": True, "voice": True}
DEFAULT_VOCAB = {"enabled": False, "language": "mixed", "difficulty": "easy", "current_quiz": None}
QUESTION_WORDS = ("?", "why", "how", "what", "tại sao", "vì sao", "giải thích", "なぜ")
REACTIONS = ("✅", "🔁", "🧠", "📝")


class StudyCoachMixin:
    """STUDY category automation layered on top of the existing StudyOps cog."""

    def _studycoach_init(self) -> None:
        self.advisor = StudyAdvisor()
        self.question_user_cooldowns: dict[tuple[int, int], datetime] = {}
        self.recent_activity: dict[int, datetime] = {}
        self.config.register_guild(
            study_category_id=None,
            questions_channel_id=None,
            study_chat_channel_id=None,
            study_room_voice_id=None,
            modules=DEFAULT_MODULES,
            vocab_settings=DEFAULT_VOCAB,
            schema_version=2,
        )
        self.config.register_member(question_notes={}, study_sessions={}, active_session=None, vocab_stats={})

    def _studycoach_unload(self) -> None:
        return None

    @staticmethod
    def _norm(name: str) -> str:
        return "".join(ch for ch in name.casefold() if ch.isalnum())

    def _find_category(self, guild: discord.Guild) -> discord.CategoryChannel | None:
        return next((c for c in guild.categories if self._norm(c.name) in {"study", self._norm("📚 STUDY")}), None)

    def _find_text_in_study(self, guild: discord.Guild, name: str) -> discord.TextChannel | None:
        category = self._find_category(guild)
        channels = category.text_channels if category else guild.text_channels
        return next((c for c in channels if self._norm(c.name) == self._norm(name)), None)

    def _find_voice_in_study(self, guild: discord.Guild, name: str) -> discord.VoiceChannel | None:
        category = self._find_category(guild)
        channels = category.voice_channels if category else guild.voice_channels
        return next((c for c in channels if self._norm(c.name) == self._norm(name)), None)

    async def _studycoach_bind(self, guild: discord.Guild) -> None:
        conf = self.config.guild(guild)
        category = self._find_category(guild)
        if category and not await conf.study_category_id():
            await conf.study_category_id.set(category.id)
        bindings = {
            "questions_channel_id": self._find_text_in_study(guild, "questions"),
            "study_log_channel_id": self._find_text_in_study(guild, "study-log"),
            "study_chat_channel_id": self._find_text_in_study(guild, "study-chat"),
            "daily_goals_channel_id": self._find_text_in_study(guild, "goals-and-progress"),
            "progress_channel_id": self._find_text_in_study(guild, "goals-and-progress"),
            "study_room_voice_id": self._find_voice_in_study(guild, "Study Room"),
            "pomodoro_voice_id": self._find_voice_in_study(guild, "Pomodoro"),
        }
        for key, channel in bindings.items():
            if channel is not None and not await getattr(conf, key)():
                await getattr(conf, key).set(channel.id)

    async def _module_enabled(self, guild: discord.Guild, module: str) -> bool:
        data = dict(DEFAULT_MODULES)
        stored = await self.config.guild(guild).modules()
        if isinstance(stored, dict):
            data.update(stored)
        return bool(data.get(module, False))

    @commands.group(name="study")
    @commands.guild_only()
    async def study(self, ctx: commands.Context):
        """Study setup, sessions, and summaries."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @study.command(name="setup")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_setup(self, ctx: commands.Context):
        """Auto-bind STUDY category channels."""
        await self._studycoach_bind(ctx.guild)
        await ctx.send("✅ STUDY channels scanned and saved.")
        await self._send_study_config(ctx)

    @study.command(name="config")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_config(self, ctx: commands.Context):
        """Show StudyCoach configuration."""
        await self._send_study_config(ctx)

    async def _send_study_config(self, ctx: commands.Context) -> None:
        await self._studycoach_bind(ctx.guild)
        data = await self.config.guild(ctx.guild).all()

        def show(key: str) -> str:
            channel = ctx.guild.get_channel(data.get(key) or 0)
            if isinstance(channel, discord.TextChannel):
                return channel.mention
            if isinstance(channel, discord.VoiceChannel):
                return channel.name
            if isinstance(channel, discord.CategoryChannel):
                return channel.name
            return "not configured"

        await ctx.send(
            "**STUDY CONFIG**\n"
            f"Category: {show('study_category_id')}\nQuestions: {show('questions_channel_id')}\n"
            f"Study log: {show('study_log_channel_id')}\nStudy chat: {show('study_chat_channel_id')}\n"
            f"Goals: {show('daily_goals_channel_id')}\nStudy Room: {show('study_room_voice_id')}\n"
            f"Pomodoro: {show('pomodoro_voice_id')}\nModules: `{data.get('modules')}`",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @study.command(name="enable")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_enable(self, ctx: commands.Context, module: str):
        """Enable one module."""
        async with self.config.guild(ctx.guild).modules() as modules:
            modules[module] = True
        await ctx.send(f"✅ `{module}` enabled.")

    @study.command(name="disable")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_disable(self, ctx: commands.Context, module: str):
        """Disable one module."""
        async with self.config.guild(ctx.guild).modules() as modules:
            modules[module] = False
        await ctx.send(f"✅ `{module}` disabled.")

    @study.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_setchannel(self, ctx: commands.Context, kind: str, channel: discord.TextChannel):
        """Set questions, log, chat, goals, or progress channel."""
        mapping = {"questions": "questions_channel_id", "log": "study_log_channel_id", "chat": "study_chat_channel_id", "goals": "daily_goals_channel_id", "progress": "progress_channel_id"}
        key = mapping.get(kind.casefold())
        if key is None:
            await ctx.send("❌ choose: questions, log, chat, goals, progress")
            return
        missing = self._missing_text_permissions(channel)
        if missing:
            await ctx.send(f"❌ missing permissions in {channel.mention}: {', '.join(missing)}")
            return
        await getattr(self.config.guild(ctx.guild), key).set(channel.id)
        await ctx.send(f"✅ saved {kind}: {channel.mention}")

    @study.command(name="setvoice")
    @commands.admin_or_permissions(manage_guild=True)
    async def study_setvoice(self, ctx: commands.Context, kind: str, *, channel: discord.VoiceChannel):
        """Set studyroom or pomodoro voice channel."""
        mapping = {"studyroom": "study_room_voice_id", "pomodoro": "pomodoro_voice_id", "pomo": "pomodoro_voice_id"}
        key = mapping.get(kind.casefold())
        if key is None:
            await ctx.send("❌ choose: studyroom or pomodoro")
            return
        await getattr(self.config.guild(ctx.guild), key).set(channel.id)
        await ctx.send(f"✅ saved {kind}: {channel.name}")

    @study.command(name="start")
    async def study_start(self, ctx: commands.Context, *, content: str):
        """Start a manual study session."""
        if not await self._module_enabled(ctx.guild, "studylog"):
            await ctx.send("❌ studylog module is disabled.")
            return
        if await self.config.member(ctx.author).active_session():
            await ctx.send("❌ You already have an active session.")
            return
        subject, goal = split_subject_goal(content)
        await self.config.member(ctx.author).active_session.set({"started_at": self._now().isoformat(), "subject": subject[:120], "goal": goal[:500], "channel_id": ctx.channel.id})
        await ctx.send(f"🚀 Study session started: **{subject[:120]}**\nGoal: {goal or 'not set'}")

    @study.command(name="stop")
    async def study_stop(self, ctx: commands.Context, *, details: str = ""):
        """Stop the active study session."""
        active = await self.config.member(ctx.author).active_session()
        if not active:
            await ctx.send("❌ No active study session.")
            return
        values = parse_key_value_tail(details)
        now = self._now()
        started = self._parse_dt(active.get("started_at")) or now
        minutes = max(1, int((now - started).total_seconds() // 60))
        session_id = self._new_id("s")
        session = {"id": session_id, "guild_id": ctx.guild.id, "user_id": ctx.author.id, "start_time": started.isoformat(), "end_time": now.isoformat(), "duration_minutes": minutes, "subject": active.get("subject", "Study"), "goal": active.get("goal", ""), "focus_score": parse_int_range(values.get("focus")), "energy_score": parse_int_range(values.get("energy")), "distraction_score": parse_int_range(values.get("distraction")), "learned_summary": str(values.get("learned", ""))[:1000], "blockers": str(values.get("blocker", ""))[:1000], "next_action": str(values.get("next", ""))[:1000], "source": "manual", "created_at": now.isoformat()}
        async with self.config.member(ctx.author).study_sessions() as sessions:
            sessions[session_id] = session
            self._trim_mapping(sessions, 500)
        await self.config.member(ctx.author).active_session.set(None)
        await self._record_session_metrics(ctx.author, session)
        await ctx.send(f"✅ Session saved: **{session['subject']}** | {self._format_minutes(minutes)}")

    @study.command(name="today")
    async def study_today(self, ctx: commands.Context):
        """Show today's study summary."""
        await self._send_study_period(ctx, days=1, label="today")

    @commands.command(name="qnote")
    @commands.guild_only()
    async def qnote(self, ctx: commands.Context, *, question: str):
        """Create a learning note manually."""
        await self._create_question_note(ctx.message, question, force=True)

    @commands.group(name="questions")
    @commands.guild_only()
    async def questions(self, ctx: commands.Context):
        """Review saved learning questions."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @questions.command(name="today")
    async def questions_today(self, ctx: commands.Context):
        """Show today's learning notes."""
        await self._send_questions(ctx, only_today=True)

    @questions.command(name="unresolved")
    async def questions_unresolved(self, ctx: commands.Context):
        """Show unresolved learning notes."""
        await self._send_questions(ctx, status="unresolved")

    @questions.command(name="solved")
    async def questions_solved(self, ctx: commands.Context):
        """Show solved learning notes."""
        await self._send_questions(ctx, status="solved")

    @questions.command(name="stats")
    async def questions_stats(self, ctx: commands.Context):
        """Show question-note statistics."""
        notes = await self.config.member(ctx.author).question_notes()
        solved = sum(1 for item in notes.values() if item.get("status") == "solved")
        await ctx.send(f"📊 Questions: `{len(notes)}` total, `{solved}` solved")

    @questions.command(name="export")
    async def questions_export(self, ctx: commands.Context):
        """Export question notes as JSON."""
        await self._send_json(ctx, await self.config.member(ctx.author).question_notes(), f"questions-{ctx.author.id}.json")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        self.recent_activity[message.guild.id] = self._now()
        if not await self._module_enabled(message.guild, "questions"):
            return
        if message.channel.id != await self.config.guild(message.guild).questions_channel_id():
            return
        if len(message.content) > 1500 or not any(word in message.content.casefold() for word in QUESTION_WORDS):
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid or not self._question_cooldown_ok(message):
            return
        await self._create_question_note(message, message.content)

    @commands.group(name="vocab")
    @commands.guild_only()
    async def vocab(self, ctx: commands.Context):
        """Configure and answer vocabulary quizzes."""
        if ctx.invoked_subcommand is None:
            await self._send_vocab_status(ctx)

    @vocab.command(name="start")
    async def vocab_start(self, ctx: commands.Context):
        """Enable vocab quiz and post one immediately."""
        await self._set_vocab(ctx.guild, "enabled", True)
        posted = await self._post_vocab_quiz(ctx.guild)
        await ctx.send("✅ Vocab enabled." if posted else "✅ Vocab enabled, but quiz channel is not ready.")

    @vocab.command(name="stop")
    async def vocab_stop(self, ctx: commands.Context):
        """Disable vocab quiz."""
        await self._set_vocab(ctx.guild, "enabled", False)
        await ctx.send("🛑 Vocab disabled.")

    @vocab.command(name="answer")
    async def vocab_answer(self, ctx: commands.Context, option: str):
        """Answer current vocab quiz."""
        option = option.strip().upper()[:1]
        settings = await self._vocab_settings(ctx.guild)
        quiz = settings.get("current_quiz")
        if option not in {"A", "B", "C", "D"} or not quiz:
            await ctx.send("❌ No active quiz, or answer must be A/B/C/D.")
            return
        correct = option == quiz.get("answer")
        async with self.config.member(ctx.author).vocab_stats() as stats:
            stats["total"] = int(stats.get("total", 0)) + 1
            stats["correct"] = int(stats.get("correct", 0)) + int(correct)
        await self._set_vocab(ctx.guild, "current_quiz", None)
        await ctx.send(await self.advisor.generate_vocab_explanation(quiz, correct), allowed_mentions=discord.AllowedMentions.none())

    @vocab.command(name="stats")
    async def vocab_stats(self, ctx: commands.Context):
        """Show vocab quiz stats."""
        stats = await self.config.member(ctx.author).vocab_stats()
        total = int(stats.get("total", 0))
        correct = int(stats.get("correct", 0))
        await ctx.send(f"🧩 Vocab: `{correct}/{total}` correct")

    async def _set_vocab(self, guild: discord.Guild, key: str, value: Any) -> None:
        async with self.config.guild(guild).vocab_settings() as settings:
            settings.setdefault("enabled", False)
            settings[key] = value

    async def _vocab_settings(self, guild: discord.Guild) -> dict[str, Any]:
        settings = dict(DEFAULT_VOCAB)
        stored = await self.config.guild(guild).vocab_settings()
        if isinstance(stored, dict):
            settings.update(stored)
        return settings

    async def _post_vocab_quiz(self, guild: discord.Guild) -> bool:
        channel_id = await self.config.guild(guild).study_chat_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return False
        item = dict(random.choice(VOCAB_BANK))
        options = item["options"]
        lines = ["🧩 **Vocab Quiz**", "", item["question"], ""]
        lines += [f"{key}. {options[key]}" for key in ("A", "B", "C", "D")]
        lines += ["", "Answer with `[p]vocab answer A/B/C/D`"]
        await channel.send("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())
        await self._set_vocab(guild, "current_quiz", item)
        return True

    async def _send_vocab_status(self, ctx: commands.Context) -> None:
        await ctx.send(f"Vocab settings: `{await self._vocab_settings(ctx.guild)}`")

    async def _create_question_note(self, message: discord.Message, question: str, *, force: bool = False) -> None:
        if not force and not await self._module_enabled(message.guild, "questions"):
            return
        data = await self.advisor.generate_question_note(question, author_name=getattr(message.author, "display_name", None))
        bot_message = await message.reply(data["text"], mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        for emoji in REACTIONS:
            with contextlib.suppress(discord.HTTPException):
                await bot_message.add_reaction(emoji)
        note_id = str(message.id)
        async with self.config.member(message.author).question_notes() as notes:
            notes[note_id] = {"id": note_id, "owner_id": message.author.id, "guild_id": message.guild.id, "channel_id": message.channel.id, "message_id": message.id, "note_message_id": bot_message.id, "question": question[:1500], "topic": data["topic"], "tags": data["tags"], "status": "unresolved", "created_at": self._now().isoformat(), "solved_at": None}
            self._trim_mapping(notes, 300)

    def _question_cooldown_ok(self, message: discord.Message) -> bool:
        now = self._now()
        key = (message.guild.id, message.author.id)
        if key in self.question_user_cooldowns and now - self.question_user_cooldowns[key] < timedelta(seconds=45):
            return False
        self.question_user_cooldowns[key] = now
        return True

    async def _send_questions(self, ctx: commands.Context, *, status: str | None = None, only_today: bool = False) -> None:
        notes = await self.config.member(ctx.author).question_notes()
        today = self._today_key()
        items = [n for n in notes.values() if (not status or n.get("status") == status) and (not only_today or str(n.get("created_at", "")).startswith(today))]
        if not items:
            await ctx.send("No matching notes.")
            return
        lines = ["**Learning questions**", ""]
        for note in items[:10]:
            lines.append(f"`{note.get('id')}` **{note.get('status')}** - {note.get('question', '')[:120]}")
        await ctx.send("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

    async def _record_session_metrics(self, member: discord.Member, session: dict[str, Any]) -> None:
        day_key = (self._parse_dt(session.get("end_time")) or self._now()).strftime(DAY_FMT)
        async with self.config.member(member).metrics() as metrics:
            day = metrics.setdefault(day_key, {"focus_minutes": 0, "pomodoro_sessions": 0, "voice_minutes": 0, "logs": []})
            day["focus_minutes"] = int(day.get("focus_minutes", 0)) + int(session.get("duration_minutes", 0))
            day.setdefault("logs", []).append({"topic": session.get("subject", "Study"), "minutes": session.get("duration_minutes", 0), "source": "manual"})

    async def _send_study_period(self, ctx: commands.Context, *, days: int, label: str) -> None:
        dates = {(self._now().date() - timedelta(days=i)).strftime(DAY_FMT) for i in range(days)}
        sessions = await self.config.member(ctx.author).study_sessions()
        items = [s for s in sessions.values() if (self._parse_dt(s.get("end_time")) or self._now()).strftime(DAY_FMT) in dates]
        await ctx.send(await self.advisor.generate_daily_summary(items, label=label), allowed_mentions=discord.AllowedMentions.none())

    async def _send_json(self, ctx: commands.Context, payload: Any, filename: str) -> None:
        await ctx.send(file=discord.File(io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")), filename=filename))

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{self._now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

    @staticmethod
    def _trim_mapping(mapping: dict[str, Any], keep: int) -> None:
        if len(mapping) <= keep:
            return
        for key in sorted(mapping)[:-keep]:
            mapping.pop(key, None)
