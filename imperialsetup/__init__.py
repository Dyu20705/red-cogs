"""ImperialSetup cog package."""

from .automation import ImperialSetup

__red_end_user_data_statement__ = (
    "This cog does not persistently store end-user data. It reads guild structure "
    "and permissions only while commands are running."
)


async def setup(bot):
    await bot.add_cog(ImperialSetup(bot))
