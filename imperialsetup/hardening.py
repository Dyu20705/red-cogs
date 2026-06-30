from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple, Union

import discord

from .imperialsetup import ImperialSetup as BaseImperialSetup
from .imperialsetup import MARKER, REASON, Channel, matches, normalise
from .safety import merge_owned_entries

OverwriteTarget = Union[discord.Role, discord.Member]
OverwriteMap = Dict[OverwriteTarget, discord.PermissionOverwrite]


class ImperialSetup(BaseImperialSetup):
    @staticmethod
    def _managed_overwrite_targets(
        guild: discord.Guild, roles: Dict[str, discord.Role]
    ) -> set[OverwriteTarget]:
        targets: set[OverwriteTarget] = {
            guild.default_role,
            roles["👑 Quân Vương"],
            roles["🏛️ Nội Các"],
            roles["🛡️ Cận Vệ"],
        }
        if guild.me is not None:
            targets.add(guild.me)
        return targets

    def _merge_blueprint_overwrites(
        self,
        existing: OverwriteMap,
        desired: OverwriteMap,
        guild: discord.Guild,
        roles: Dict[str, discord.Role],
    ) -> OverwriteMap:
        desired = {
            target: value
            for target, value in desired.items()
            if target is not None
        }
        return merge_owned_entries(
            existing,
            desired,
            self._managed_overwrite_targets(guild, roles),
        )

    @staticmethod
    def _matching_channels(
        guild: discord.Guild,
        channel_type: str,
        name: str,
        aliases: Iterable[str],
    ) -> List[Channel]:
        expected = (
            discord.TextChannel
            if channel_type == "text"
            else discord.VoiceChannel
        )
        return [
            channel
            for channel in guild.channels
            if isinstance(channel, expected)
            and matches(channel.name, name, aliases)
        ]

    def _find_channel_anywhere(
        self,
        guild: discord.Guild,
        channel_type: str,
        name: str,
        aliases: Iterable[str],
    ) -> Optional[Channel]:
        candidates = self._matching_channels(
            guild, channel_type, name, aliases
        )
        if not candidates:
            return None

        canonical_key = normalise(name)
        return min(
            candidates,
            key=lambda channel: (
                normalise(channel.name) != canonical_key,
                getattr(channel, "position", 0),
                channel.id,
            ),
        )

    def _find_unambiguous_channel(
        self,
        guild: discord.Guild,
        channel_type: str,
        name: str,
        aliases: Iterable[str],
    ) -> Optional[Channel]:
        candidates = self._matching_channels(
            guild, channel_type, name, aliases
        )
        if len(candidates) > 1:
            locations = ", ".join(
                f"{channel.category.name if channel.category else 'NO CATEGORY'}/"
                f"{channel.name} ({channel.id})"
                for channel in candidates
            )
            raise RuntimeError(
                f"Ambiguous {channel_type} channel match for {name!r}: "
                f"{locations}. Rename duplicates or narrow aliases before "
                "running a mutating command."
            )
        return candidates[0] if candidates else None

    async def _ensure_category(
        self,
        guild: discord.Guild,
        spec: dict,
        roles: Dict[str, discord.Role],
        position: int,
        optimize: bool,
    ) -> Tuple[discord.CategoryChannel, List[str]]:
        existing = self._find_category(
            guild, spec["name"], spec.get("aliases", [])
        )
        desired = self._policy_overwrites(
            guild, spec["policy"], roles, is_voice=False
        )
        guild_available = guild.me.guild_permissions if guild.me else None
        desired = self._cap_overwrites(
            guild, desired, guild_available
        )
        desired = {
            target: value
            for target, value in desired.items()
            if target is not None
        }

        if existing is None:
            self._op(guild, f"create category: {spec['name']}")
            category = await guild.create_category(
                spec["name"],
                overwrites=desired,
                position=position,
                reason=REASON,
            )
            return category, ["categories_created"]

        changes: List[str] = ["reused"]
        edit_kwargs = {}
        if existing.name != spec["name"]:
            edit_kwargs["name"] = spec["name"]
            changes.append("renamed")

        me = guild.me
        if optimize and me is not None:
            effective = existing.permissions_for(me)
            if effective.manage_roles or me.guild_permissions.administrator:
                safe_desired = self._cap_overwrites(
                    guild, desired, effective
                )
                merged = self._merge_blueprint_overwrites(
                    existing.overwrites,
                    safe_desired,
                    guild,
                    roles,
                )
                if merged != existing.overwrites:
                    edit_kwargs["overwrites"] = merged
                    changes.append("optimized")

        if edit_kwargs:
            self._op(guild, f"edit category: {existing.name}")
            await existing.edit(reason=REASON, **edit_kwargs)

        if optimize:
            try:
                self._op(guild, f"reorder category: {existing.name}")
                await existing.edit(position=position, reason=REASON)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return existing, changes

    async def _ensure_channel(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        spec: dict,
        base_policy: str,
        roles: Dict[str, discord.Role],
        optimize: bool,
    ) -> Tuple[Channel, List[str]]:
        is_voice = spec["type"] == "voice"
        desired = self._channel_overwrites(
            guild,
            base_policy,
            spec.get("policy", "inherit"),
            roles,
            is_voice,
        )
        parent_effective = (
            category.permissions_for(guild.me)
            if guild.me is not None
            else None
        )
        safe_desired = self._cap_overwrites(
            guild, desired, parent_effective
        )
        safe_desired = {
            target: value
            for target, value in safe_desired.items()
            if target is not None
        }
        existing = self._find_unambiguous_channel(
            guild,
            spec["type"],
            spec["name"],
            spec.get("aliases", []),
        )

        if existing is None:
            me = guild.me
            can_set_overwrites = (
                parent_effective is not None
                and me is not None
                and (
                    parent_effective.manage_roles
                    or me.guild_permissions.administrator
                )
            )
            create_overwrites = (
                safe_desired if can_set_overwrites else None
            )
            self._op(
                guild,
                f"create {'voice' if is_voice else 'text'} channel: "
                f"{category.name}/{spec['name']}",
            )
            if is_voice:
                channel = await guild.create_voice_channel(
                    spec["name"],
                    category=category,
                    overwrites=create_overwrites,
                    user_limit=spec.get("user_limit", 0),
                    reason=REASON,
                )
            else:
                channel = await guild.create_text_channel(
                    spec["name"],
                    category=category,
                    overwrites=create_overwrites,
                    topic=spec.get("topic"),
                    slowmode_delay=spec.get("slowmode_delay", 0),
                    reason=REASON,
                )
            return channel, ["channels_created"]

        changes: List[str] = ["reused"]
        edit_kwargs = {}
        me = guild.me
        if me is None:
            return existing, changes

        effective = existing.permissions_for(me)
        can_manage_channel = (
            effective.manage_channels
            or me.guild_permissions.administrator
        )
        can_manage_overwrites = (
            effective.manage_roles
            or me.guild_permissions.administrator
        )

        if can_manage_channel and existing.name != spec["name"]:
            edit_kwargs["name"] = spec["name"]
            changes.append("renamed")

        target_effective = category.permissions_for(me)
        can_manage_target = (
            target_effective.manage_channels
            or me.guild_permissions.administrator
        )
        if (
            can_manage_channel
            and can_manage_target
            and existing.category_id != category.id
        ):
            edit_kwargs["category"] = category
            changes.append("moved")

        optimized = False
        if optimize and can_manage_channel:
            if can_manage_overwrites:
                capped = self._cap_overwrites(
                    guild, desired, effective
                )
                merged = self._merge_blueprint_overwrites(
                    existing.overwrites,
                    capped,
                    guild,
                    roles,
                )
                if merged != existing.overwrites:
                    edit_kwargs["overwrites"] = merged
                    optimized = True

            if isinstance(existing, discord.TextChannel):
                topic = spec.get("topic")
                slowmode = spec.get("slowmode_delay", 0)
                if existing.topic != topic:
                    edit_kwargs["topic"] = topic
                    optimized = True
                if existing.slowmode_delay != slowmode:
                    edit_kwargs["slowmode_delay"] = slowmode
                    optimized = True
            elif isinstance(existing, discord.VoiceChannel):
                user_limit = spec.get("user_limit", 0)
                if existing.user_limit != user_limit:
                    edit_kwargs["user_limit"] = user_limit
                    optimized = True
        elif (
            can_manage_channel
            and isinstance(existing, discord.TextChannel)
            and not existing.topic
            and spec.get("topic")
        ):
            edit_kwargs["topic"] = spec["topic"]

        if optimized:
            changes.append("optimized")

        if edit_kwargs:
            self._op(
                guild,
                "edit channel: "
                f"{existing.category.name + '/' if existing.category else ''}"
                f"{existing.name}",
            )
            await existing.edit(reason=REASON, **edit_kwargs)
        return existing, changes

    async def _seed_if_empty(
        self,
        channel: discord.TextChannel,
        seed: dict,
    ) -> bool:
        try:
            messages = [
                message
                async for message in channel.history(limit=20)
            ]
        except discord.Forbidden:
            return False

        for message in messages:
            if any(
                embed.footer and embed.footer.text == MARKER
                for embed in message.embeds
            ):
                return False
        if messages:
            return False

        embed = discord.Embed(
            title=seed["title"],
            description=seed["description"],
            colour=discord.Colour.gold(),
        )
        embed.set_footer(text=MARKER)
        self._op(
            channel.guild,
            f"send starter embed: #{channel.name}",
        )
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
