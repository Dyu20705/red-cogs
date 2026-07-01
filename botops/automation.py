from __future__ import annotations

import contextlib
from typing import Any

import discord
from redbot.core import commands

from .botops import BotOps as BaseBotOps


class BotOps(BaseBotOps):
    """BotOps with automatic moderation and guild-change event logging."""

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
            "audit_channel_id": self._find_text_channel(guild, "audit-and-mod-log"),
            "errors_channel_id": self._find_text_channel(guild, "bot-errors"),
            "logs_channel_id": self._find_text_channel(guild, "bot-logs"),
        }

        for key, channel in bindings.items():
            if channel is None:
                continue
            current_id = await getattr(guild_conf, key)()
            current = guild.get_channel(current_id) if current_id else None
            if not isinstance(current, discord.TextChannel):
                await getattr(guild_conf, key).set(channel.id)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            with contextlib.suppress(Exception):
                await self._bind_default_channels(guild)

    async def _event(
        self,
        guild: discord.Guild,
        *,
        event: str,
        subject: Any,
        details: str,
        before: str | None = None,
        after: str | None = None,
    ) -> None:
        await self._bind_default_channels(guild)
        channel = await self._configured_channel(guild, "audit_channel_id")
        if channel is None:
            return

        incident = await self._next_incident(guild, "AUD")
        lines = [
            f"🛡️ **{self._short(event, 120)}**",
            f"Subject: {self._short(subject, 180)}",
            f"Details: {self._short(details, 700)}",
        ]
        if before is not None:
            lines.append(f"Before: {self._short(before, 500)}")
        if after is not None:
            lines.append(f"After: {self._short(after, 500)}")
        lines.extend(
            [
                f"Incident: `{incident}`",
                f"Time: `{self._now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}`",
            ]
        )

        with contextlib.suppress(discord.HTTPException):
            await channel.send(
                self.sanitize("\n".join(lines)),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def _is_audit_message(self, message: discord.Message) -> bool:
        if message.guild is None:
            return True
        audit_id = await self.config.guild(message.guild).audit_channel_id()
        return bool(audit_id and message.channel.id == audit_id)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if await self._is_audit_message(message):
            return

        content = message.content.strip() or "[No visible text content]"
        if message.attachments:
            content += f" | Attachments: {len(message.attachments)}"
        await self._event(
            message.guild,
            event="MESSAGE DELETED",
            subject=f"{message.author} in #{message.channel}",
            details=content,
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ):
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return
        if await self._is_audit_message(before):
            return

        await self._event(
            before.guild,
            event="MESSAGE EDITED",
            subject=f"{before.author} in #{before.channel}",
            details=f"Message ID: {before.id}",
            before=before.content or "[No visible text content]",
            after=after.content or "[No visible text content]",
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._event(
            member.guild,
            event="MEMBER JOINED",
            subject=f"{member} ({member.id})",
            details=f"Account created: {discord.utils.format_dt(member.created_at, 'F')}",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._event(
            member.guild,
            event="MEMBER LEFT OR REMOVED",
            subject=f"{member} ({member.id})",
            details="The member left the guild or was removed by moderation.",
        )

    @commands.Cog.listener()
    async def on_member_ban(
        self,
        guild: discord.Guild,
        user: discord.User | discord.Member,
    ):
        await self._event(
            guild,
            event="MEMBER BANNED",
            subject=f"{user} ({user.id})",
            details="A guild ban was applied.",
        )

    @commands.Cog.listener()
    async def on_member_unban(
        self,
        guild: discord.Guild,
        user: discord.User,
    ):
        await self._event(
            guild,
            event="MEMBER UNBANNED",
            subject=f"{user} ({user.id})",
            details="A guild ban was removed.",
        )

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ):
        changes = []
        if before.nick != after.nick:
            changes.append(("Nickname", before.nick or "none", after.nick or "none"))

        before_roles = {role.id: role.name for role in before.roles[1:]}
        after_roles = {role.id: role.name for role in after.roles[1:]}
        if before_roles != after_roles:
            removed = [name for role_id, name in before_roles.items() if role_id not in after_roles]
            added = [name for role_id, name in after_roles.items() if role_id not in before_roles]
            changes.append(
                (
                    "Roles",
                    ", ".join(removed) or "none removed",
                    ", ".join(added) or "none added",
                )
            )

        before_timeout = before.timed_out_until
        after_timeout = after.timed_out_until
        if before_timeout != after_timeout:
            changes.append(
                (
                    "Timeout",
                    str(before_timeout or "none"),
                    str(after_timeout or "none"),
                )
            )

        for label, old, new in changes:
            await self._event(
                after.guild,
                event=f"MEMBER UPDATED — {label.upper()}",
                subject=f"{after} ({after.id})",
                details=f"Member {label.lower()} changed.",
                before=old,
                after=new,
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self._event(
            channel.guild,
            event="CHANNEL CREATED",
            subject=f"{channel.name} ({channel.id})",
            details=f"Type: {channel.type} | Category: {channel.category or 'none'}",
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self._event(
            channel.guild,
            event="CHANNEL DELETED",
            subject=f"{channel.name} ({channel.id})",
            details=f"Type: {channel.type} | Category: {channel.category or 'none'}",
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ):
        old = (
            f"name={before.name}; category={before.category}; "
            f"position={before.position}"
        )
        new = (
            f"name={after.name}; category={after.category}; "
            f"position={after.position}"
        )
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            old += f"; topic={before.topic}; slowmode={before.slowmode_delay}"
            new += f"; topic={after.topic}; slowmode={after.slowmode_delay}"
        if old == new and before.overwrites == after.overwrites:
            return
        if before.overwrites != after.overwrites:
            old += "; permissions=changed"
            new += "; permissions=changed"

        await self._event(
            after.guild,
            event="CHANNEL OR PERMISSIONS UPDATED",
            subject=f"{after.name} ({after.id})",
            details=f"Type: {after.type}",
            before=old,
            after=new,
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self._event(
            role.guild,
            event="ROLE CREATED",
            subject=f"{role.name} ({role.id})",
            details=f"Permissions value: {role.permissions.value}",
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self._event(
            role.guild,
            event="ROLE DELETED",
            subject=f"{role.name} ({role.id})",
            details=f"Permissions value: {role.permissions.value}",
        )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ):
        old = (
            f"name={before.name}; colour={before.colour}; hoist={before.hoist}; "
            f"permissions={before.permissions.value}"
        )
        new = (
            f"name={after.name}; colour={after.colour}; hoist={after.hoist}; "
            f"permissions={after.permissions.value}"
        )
        if old == new:
            return

        await self._event(
            after.guild,
            event="ROLE OR PERMISSIONS UPDATED",
            subject=f"{after.name} ({after.id})",
            details="Role metadata or guild permissions changed.",
            before=old,
            after=new,
        )
