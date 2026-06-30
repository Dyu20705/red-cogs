from .imperialautomation import ImperialAutomation


async def setup(bot):
    await bot.add_cog(ImperialAutomation(bot))
