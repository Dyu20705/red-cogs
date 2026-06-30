from .studyops import StudyOps


async def setup(bot):
    await bot.add_cog(StudyOps(bot))
