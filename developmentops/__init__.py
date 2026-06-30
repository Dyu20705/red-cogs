from .developmentops import DevelopmentOps


async def setup(bot):
    await bot.add_cog(DevelopmentOps(bot))
