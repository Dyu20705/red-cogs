from .imperialsetup import ImperialSetup

async def setup(bot):
    await bot.add_cog(ImperialSetup(bot))
