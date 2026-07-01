from __future__ import annotations

import contextlib

import discord
from discord.ext import tasks

from .studyops import StudyOps as BaseStudyOps


class StudyOps(BaseStudyOps):
    """StudyOps with automatic channel discovery and LeetCode reminders."""

    def __init__(self, bot):
        super().__init__(bot)
        self.config.register_guild(
            leetcode_channel_id=None,
            leetcode_enabled=True,
            leetcode_hour=8,
            leetcode_minute=0,
            last_leetcode_post="",
        )
        self.leetcode_loop.start()

    def cog_unload(self):
        self.leetcode_loop.cancel()
        super().cog_unload()

    @staticmethod
    def _normalise_channel_name(name: str) -> str:
        return "".join(character for character in name.casefold() if character.isalnum())

    def _find_text_channel(
        self,
        guild: discord.Guild,
        *names: str,
    ) -> discord.TextChannel | None:
        expected = {
            self._normalise_channel_name(name)
            for name in names
        }
        return next(
            (
                channel
                for channel in guild.text_channels
                if self._normalise_channel_name(channel.name) in expected
            ),
            None,
        )

    async def _bind_default_channels(self, guild: discord.Guild) -> None:
        guild_conf = self.config.guild(guild)
        bindings = {
            "daily_goals_channel_id": self._find_text_channel(
                guild,
                "goals-and-progress",
            ),
            "progress_channel_id": self._find_text_channel(
                guild,
                "goals-and-progress",
            ),
            "study_log_channel_id": self._find_text_channel(
                guild,
                "study-log",
            ),
            "leetcode_channel_id": self._find_text_channel(
                guild,
                "leet-code",
                "leetcode",
                "leet-code-daily",
            ),
        }

        for key, channel in bindings.items():
            if channel is None:
                continue
            current_id = await getattr(guild_conf, key)()
            current = guild.get_channel(current_id) if current_id else None
            if not isinstance(current, discord.TextChannel):
                await getattr(guild_conf, key).set(channel.id)

    @discord.ext.commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            with contextlib.suppress(Exception):
                await self._bind_default_channels(guild)

    async def post_leetcode_daily(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ) -> bool:
        await self._bind_default_channels(guild)
        guild_conf = self.config.guild(guild)
        data = await guild_conf.all()

        if not bool(data.get("leetcode_enabled", True)):
            return False

        day_key = self._today_key()
        if not force and data.get("last_leetcode_post") == day_key:
            return False

        channel_id = data.get("leetcode_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return False

        now = self._now()
        weekday_plan = (
            "Array / Hash Map",
            "Two Pointers / Sliding Window",
            "Stack / Queue",
            "Binary Search / Greedy",
            "Tree / Graph",
            "Dynamic Programming",
            "Review, rewrite, and benchmark",
        )[now.weekday()]

        embed = discord.Embed(
            title=f"🧩 LEETCODE DAILY — {now.strftime(DISPLAY_DAY_FMT)}",
            description=(
                "Đã đến giờ luyện thuật toán. Mở **LeetCode Daily Challenge** "
                "hoặc chọn một bài phù hợp với mục tiêu hôm nay."
            ),
            url="https://leetcode.com/problemset/",
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Chủ đề gợi ý",
            value=f"**{weekday_plan}**",
            inline=False,
        )
        embed.add_field(
            name="Quy trình 45–90 phút",
            value=(
                "1. Đọc đề và tự tạo test case.\n"
                "2. Viết hướng giải trước khi code.\n"
                "3. Chạy, sửa lỗi và tối ưu độ phức tạp.\n"
                "4. Ghi lại pattern, time và space complexity."
            ),
            inline=False,
        )
        embed.add_field(
            name="Gắn vào StudyOps",
            value=(
                "Dùng `!goal add LeetCode: <tên bài>` rồi đánh dấu bằng "
                "`!goal done <số>` khi hoàn thành."
            ),
            inline=False,
        )
        embed.set_footer(text="STUDYOPS_LEETCODE_DAILY_V1")

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            await self._report_error(
                guild,
                operation="Post daily LeetCode reminder",
                error=exc,
            )
            return False

        await guild_conf.last_leetcode_post.set(day_key)
        return True

    @tasks.loop(seconds=60)
    async def leetcode_loop(self):
        now = self._now()
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            if not bool(data.get("leetcode_enabled", True)):
                continue
            if not self._within_schedule_window(
                now,
                int(data.get("leetcode_hour", 8)),
                int(data.get("leetcode_minute", 0)),
                180,
            ):
                continue

            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            with contextlib.suppress(Exception):
                await self.post_leetcode_daily(guild)

    @leetcode_loop.before_loop
    async def before_leetcode_loop(self):
        await self.bot.wait_until_ready()
