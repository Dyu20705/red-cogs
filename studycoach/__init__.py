from .studycoach import StudyCoach


async def setup(bot):
    await bot.add_cog(StudyCoach(bot))
