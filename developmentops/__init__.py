"""DevelopmentOps cog package."""

from .hardening import DevelopmentOps

__red_end_user_data_statement__ = (
    "This cog stores guild/channel/thread IDs, GitHub repository names, Forum/Issue "
    "mappings, PR thread mappings, and schedule settings. It may copy configured "
    "Discord Forum content, attachment URLs, and creator IDs to GitHub Issues. "
    "Credentials and webhook secrets are read only from process environment variables."
)


async def setup(bot):
    await bot.add_cog(DevelopmentOps(bot))
