from __future__ import annotations

from redbot.core import commands


class StudyCoach(commands.Cog):
    """STUDY category coach."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="studycoach_ping")
    async def studycoach_ping(self, ctx: commands.Context):
        """Check StudyCoach is loaded."""
        await ctx.send("StudyCoach loaded.")
