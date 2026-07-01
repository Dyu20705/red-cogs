"""BotOps package entry point."""

from .automation import BotOps


async def setup(bot):
    await bot.add_cog(BotOps(bot))
