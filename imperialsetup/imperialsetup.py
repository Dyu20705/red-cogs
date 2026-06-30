from __future__ import annotations

import asyncio
import io
import re
import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import discord
from redbot.core import commands

from .blueprint import CATEGORIES, ROLE_SPECS


MARKER = "IMPERIAL_SETUP_ADAPTIVE_V2_2"
LAUNCH_MARKER = "IMPERIAL_LAUNCH_ADAPTIVE_V2_2"
REASON = "ImperialSetup adaptive v2.2 channel-aware reconciliation"

Channel = Union[discord.TextChannel, discord.VoiceChannel]


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def matches(name: str, target: str, aliases: Iterable[str] = ()) -> bool:
    candidate = normalise(name)
    return any(candidate == normalise(item) for item in (target, *aliases))


class ImperialSetup(commands.Cog):
    """
    Preserve-first server setup.

    The flow is:
    audit -> plan -> reconcile -> optimize -> launch.
    Nothing outside the declared blueprint is deleted.
    """

    def __init__(self, bot):
        self.bot = bot
        self._locks: Dict[int, asyncio.Lock] = {}
        self._current_operation: Dict[int, str] = {}

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    @commands.guild_only()
    @commands.guildowner_or_permissions(administrator=True)
    @commands.group(
        name="deche",
        aliases=["imperialsetup", "serverflow", "setupserver"],
        invoke_without_command=True,
    )
    async def deche(self, ctx: commands.Context):
        """Audit and finish an already partially built server."""
        await ctx.send_help()

    @deche.command(name="audit", aliases=["scan", "quet"])
    async def audit(self, ctx: commands.Context):
        """Scan the existing server without changing anything."""
        lines = self._audit_lines(ctx.guild)
        await self._send_report(ctx, "ImperialSetup audit", lines)

    @deche.command(name="plan", aliases=["kehoach"])
    async def plan(self, ctx: commands.Context):
        """Show exactly what the reconciler intends to do."""
        lines = self._plan_lines(ctx.guild)
        await self._send_report(ctx, "ImperialSetup plan", lines)

    @deche.command(name="reconcile", aliases=["sync", "dongbo"])
    @commands.bot_has_permissions(
        manage_roles=True,
        manage_channels=True,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
    )
    async def reconcile(self, ctx: commands.Context, confirmation: str = ""):
        """
        Reuse/move/rename matching objects and create only missing objects.

        Existing channel permission overwrites and existing messages are preserved.
        """
        if not self._confirmed(confirmation):
            await ctx.send(
                "Chạy bước an toàn trước: "
                f"`{ctx.clean_prefix}deche audit` → `{ctx.clean_prefix}deche plan`.\n"
                "Sau đó dùng "
                f"`{ctx.clean_prefix}deche reconcile CONFIRM`.\n"
                "Bước này không xóa channel, role hoặc tin nhắn."
            )
            return
        await self._run_locked(ctx, "reconcile")

    @deche.command(name="optimize", aliases=["optimise", "toiuu"])
    @commands.bot_has_permissions(
        manage_roles=True,
        manage_channels=True,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
    )
    async def optimize(self, ctx: commands.Context, confirmation: str = ""):
        """
        Apply the recommended permissions, topics, slowmode, and category order.

        Only blueprint-matched roles/channels are managed. Unrecognized objects remain untouched.
        """
        if not self._confirmed(confirmation):
            await ctx.send(
                "Bước này chuẩn hóa permission của những channel thuộc blueprint.\n"
                f"Dùng `{ctx.clean_prefix}deche optimize CONFIRM` để tiếp tục."
            )
            return
        await self._run_locked(ctx, "optimize")

    @deche.command(name="launch", aliases=["start", "khoidong"])
    @commands.bot_has_permissions(
        view_channel=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
    )
    async def launch(self, ctx: commands.Context, confirmation: str = ""):
        """
        Post starter content only into empty managed channels and create a readiness dashboard.
        """
        if not self._confirmed(confirmation):
            await ctx.send(
                "Bước này chỉ đăng nội dung mẫu vào các channel trống và tạo bảng bắt đầu.\n"
                f"Dùng `{ctx.clean_prefix}deche launch CONFIRM` để tiếp tục."
            )
            return
        await self._run_locked(ctx, "launch")

    @deche.command(name="auto", aliases=["all", "tudong"])
    @commands.bot_has_permissions(
        manage_roles=True,
        manage_channels=True,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
    )
    async def auto(self, ctx: commands.Context, confirmation: str = ""):
        """
        Run the full preserve-first flow: reconcile -> optimize -> launch.

        Recommended after reviewing `[p]deche audit` and `[p]deche plan`.
        """
        if not self._confirmed(confirmation):
            await ctx.send(
                "Đây là flow một lệnh, nhưng vẫn theo nguyên tắc **không xóa**:\n"
                "1. Tái sử dụng phần đã dựng.\n"
                "2. Chỉ tạo phần còn thiếu.\n"
                "3. Tối ưu permission cho phần được nhận diện.\n"
                "4. Chỉ đăng nội dung mẫu vào channel trống.\n\n"
                f"Xem trước: `{ctx.clean_prefix}deche audit` và "
                f"`{ctx.clean_prefix}deche plan`.\n"
                f"Thực hiện: `{ctx.clean_prefix}deche auto CONFIRM`."
            )
            return
        await self._run_locked(ctx, "auto")

    @deche.command(name="diagnose", aliases=["debug", "chan-doan"])
    async def diagnose(self, ctx: commands.Context):
        """Report role hierarchy and effective per-channel permissions."""
        guild = ctx.guild
        me = guild.me
        if me is None:
            await ctx.send("❌ Không tìm thấy bot member trong guild cache.")
            return

        lines = [
            f"Bot: {me} ({me.id})",
            f"Top role: {me.top_role.name} | position={me.top_role.position}",
            f"Administrator: {me.guild_permissions.administrator}",
            f"Manage Roles (guild): {me.guild_permissions.manage_roles}",
            f"Manage Channels (guild): {me.guild_permissions.manage_channels}",
            "",
            "ROLE MANAGEABILITY",
        ]

        for spec in ROLE_SPECS:
            role = self._find_role(guild, spec["name"], spec.get("aliases", []))
            if role is None:
                lines.append(f"[MISSING] {spec['name']}")
                continue
            manageable = (
                not role.managed
                and role != guild.default_role
                and role < me.top_role
            )
            lines.append(
                f"[{'OK' if manageable else 'BLOCKED'}] {role.name} "
                f"position={role.position} managed={role.managed}"
            )

        lines.extend(["", "EFFECTIVE CHANNEL PERMISSIONS"])
        for category in guild.categories:
            perms = category.permissions_for(me)
            lines.append(
                f"[CATEGORY] {category.name}: "
                f"view={perms.view_channel} "
                f"manage_channels={perms.manage_channels} "
                f"manage_roles={perms.manage_roles}"
            )
            for channel in category.channels:
                ch_perms = channel.permissions_for(me)
                lines.append(
                    f"  [{channel.type}] {channel.name}: "
                    f"view={ch_perms.view_channel} "
                    f"send={getattr(ch_perms, 'send_messages', False)} "
                    f"manage_channels={ch_perms.manage_channels} "
                    f"manage_roles={ch_perms.manage_roles}"
                )

        uncategorized = [
            channel for channel in guild.channels
            if not isinstance(channel, discord.CategoryChannel)
            and channel.category is None
        ]
        if uncategorized:
            lines.extend(["", "UNCATEGORIZED"])
            for channel in uncategorized:
                perms = channel.permissions_for(me)
                lines.append(
                    f"[{channel.type}] {channel.name}: "
                    f"view={perms.view_channel} "
                    f"manage_channels={perms.manage_channels} "
                    f"manage_roles={perms.manage_roles}"
                )

        await self._send_report(ctx, "ImperialSetup diagnose", lines)

    @deche.command(name="status")
    async def status(self, ctx: commands.Context):
        """Display concise readiness status after setup."""
        lines = self._status_lines(ctx.guild)
        await self._send_report(ctx, "ImperialSetup status", lines)

    async def _run_locked(self, ctx: commands.Context, mode: str) -> None:
        lock = self._lock_for(ctx.guild.id)
        if lock.locked():
            await ctx.send("⏳ Một tiến trình ImperialSetup khác đang chạy.")
            return

        async with lock:
            progress = await ctx.send(f"🏗️ Đang chạy `{mode}`…")
            try:
                if mode == "reconcile":
                    result = await self._reconcile(ctx.guild, optimize=False)
                elif mode == "optimize":
                    result = await self._reconcile(ctx.guild, optimize=True)
                elif mode == "launch":
                    result = await self._launch(ctx)
                else:
                    first = await self._reconcile(ctx.guild, optimize=False)
                    second = await self._reconcile(ctx.guild, optimize=True)
                    third = await self._launch(ctx)
                    result = self._merge_reports(first, second, third)
            except discord.Forbidden as exc:
                operation = self._current_operation.get(
                    ctx.guild.id, "không xác định được bước API"
                )
                detail = getattr(exc, "text", None) or str(exc)
                await progress.edit(
                    content=(
                        "❌ Discord trả về `403 Forbidden`.\n"
                        f"**Bước bị chặn:** `{operation}`\n"
                        f"**HTTP status:** `{getattr(exc, 'status', 'unknown')}`\n"
                        f"**Discord code:** `{getattr(exc, 'code', 'unknown')}`\n"
                        f"**Chi tiết:** `{detail[:500]}`\n\n"
                        f"Chạy `{ctx.clean_prefix}deche diagnose` rồi gửi báo cáo nếu lỗi còn lặp lại."
                    )
                )
                return
            except discord.HTTPException as exc:
                await progress.edit(content=f"❌ Discord API báo lỗi: `{exc}`")
                return
            except Exception as exc:
                await progress.edit(
                    content=f"❌ Dừng vì `{type(exc).__name__}: {exc}`. "
                    "Traceback chi tiết nằm trong cửa sổ chạy Red."
                )
                raise

            await progress.edit(content=self._format_result(mode, result, ctx.clean_prefix))

    def _op(self, guild: discord.Guild, label: str) -> None:
        self._current_operation[guild.id] = label

    @staticmethod
    def _confirmed(value: str) -> bool:
        return value.strip().upper() == "CONFIRM"

    @staticmethod
    def _merge_reports(*reports: Dict[str, int]) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for report in reports:
            for key, value in report.items():
                merged[key] = merged.get(key, 0) + value
        return merged

    def _format_result(
        self, mode: str, report: Dict[str, int], prefix: str
    ) -> str:
        labels = {
            "roles_created": "Role tạo mới",
            "categories_created": "Category tạo mới",
            "channels_created": "Channel tạo mới",
            "reused": "Thành phần tái sử dụng",
            "renamed": "Thành phần đổi tên chuẩn",
            "moved": "Channel được đưa về đúng category",
            "optimized": "Thành phần được tối ưu",
            "seeded": "Channel nhận nội dung khởi đầu",
            "launch_dashboard": "Bảng bắt đầu được tạo",
        }
        body = [f"✅ `{mode}` hoàn tất."]
        for key, label in labels.items():
            if report.get(key):
                body.append(f"• {label}: **{report[key]}**")
        body.append(f"\nKiểm tra bằng `{prefix}deche status`.")
        return "\n".join(body)

    async def _send_report(
        self, ctx: commands.Context, title: str, lines: Sequence[str]
    ) -> None:
        text = "\n".join(lines)
        message = f"**{title}**\n```text\n{text}\n```"
        if len(message) <= 1950:
            await ctx.send(message)
            return

        payload = io.BytesIO(text.encode("utf-8"))
        await ctx.send(
            f"**{title}** — báo cáo dài nên được đính kèm.",
            file=discord.File(payload, filename=f"{normalise(title) or 'report'}.txt"),
        )

    def _required_permission_lines(self, guild: discord.Guild) -> List[str]:
        me = guild.me
        if me is None:
            return ["[ERROR] Không xác định được bot member trong server."]

        required = [
            ("manage_roles", "Manage Roles"),
            ("manage_channels", "Manage Channels"),
            ("view_channel", "View Channels"),
            ("send_messages", "Send Messages"),
            ("embed_links", "Embed Links"),
            ("read_message_history", "Read Message History"),
            ("connect", "Connect"),
            ("speak", "Speak"),
        ]
        missing = [
            label for attribute, label in required
            if not getattr(me.guild_permissions, attribute, False)
        ]
        if missing:
            return ["[MISSING BOT PERMISSIONS] " + ", ".join(missing)]
        return ["[OK] Bot có đủ permission cốt lõi."]

    def _audit_lines(self, guild: discord.Guild) -> List[str]:
        lines: List[str] = []
        lines.extend(self._required_permission_lines(guild))
        lines.append("")

        role_found = 0
        for spec in ROLE_SPECS:
            role = self._find_role(guild, spec["name"], spec.get("aliases", []))
            if role:
                role_found += 1
                lines.append(f"[REUSE ROLE] {role.name}")
            else:
                lines.append(f"[MISSING ROLE] {spec['name']}")

        lines.append("")
        matched_category_ids = set()
        matched_channel_ids = set()

        for category_spec in CATEGORIES:
            category = self._find_category(
                guild, category_spec["name"], category_spec.get("aliases", [])
            )
            if category is None:
                lines.append(f"[MISSING CATEGORY] {category_spec['name']}")
            else:
                matched_category_ids.add(category.id)
                rename = (
                    f" -> {category_spec['name']}"
                    if category.name != category_spec["name"]
                    else ""
                )
                lines.append(f"[REUSE CATEGORY] {category.name}{rename}")

            for channel_spec in category_spec["channels"]:
                channel = self._find_channel_anywhere(
                    guild,
                    channel_spec["type"],
                    channel_spec["name"],
                    channel_spec.get("aliases", []),
                )
                if channel is None:
                    lines.append(
                        f"  [MISSING CHANNEL] {channel_spec['type']}: "
                        f"{channel_spec['name']}"
                    )
                    continue

                matched_channel_ids.add(channel.id)
                current_parent = channel.category.name if channel.category else "NO CATEGORY"
                target_parent = category_spec["name"]
                notes = []
                if channel.name != channel_spec["name"]:
                    notes.append(f"rename → {channel_spec['name']}")
                if category is not None and channel.category_id != category.id:
                    notes.append(f"move → {target_parent}")
                suffix = f" ({'; '.join(notes)})" if notes else ""
                lines.append(
                    f"  [REUSE CHANNEL] {channel.name} @ {current_parent}{suffix}"
                )

        unmanaged_categories = [
            category.name
            for category in guild.categories
            if category.id not in matched_category_ids
        ]
        unmanaged_channels = [
            channel.name
            for channel in guild.channels
            if not isinstance(channel, discord.CategoryChannel)
            and channel.id not in matched_channel_ids
        ]

        lines.append("")
        if unmanaged_categories:
            lines.append(
                "[UNMANAGED CATEGORIES — GIỮ NGUYÊN] "
                + ", ".join(unmanaged_categories)
            )
        if unmanaged_channels:
            preview = unmanaged_channels[:20]
            suffix = (
                f", … +{len(unmanaged_channels) - 20}"
                if len(unmanaged_channels) > 20
                else ""
            )
            lines.append(
                "[UNMANAGED CHANNELS — GIỮ NGUYÊN] "
                + ", ".join(preview)
                + suffix
            )

        duplicate_categories = self._duplicate_names(
            [category.name for category in guild.categories]
        )
        duplicate_channels = self._duplicate_names(
            [
                channel.name
                for channel in guild.channels
                if not isinstance(channel, discord.CategoryChannel)
            ]
        )
        if duplicate_categories:
            lines.append(
                "[POSSIBLE DUPLICATE CATEGORIES] "
                + ", ".join(duplicate_categories)
            )
        if duplicate_channels:
            lines.append(
                "[POSSIBLE DUPLICATE CHANNELS] "
                + ", ".join(duplicate_channels)
            )

        lines.append("")
        lines.append(
            f"Summary: {role_found}/{len(ROLE_SPECS)} roles recognized; "
            f"{len(matched_category_ids)}/{len(CATEGORIES)} categories recognized; "
            f"{len(matched_channel_ids)} blueprint channels recognized."
        )
        lines.append(
            "Lưu ý: category như `MIU R|C` nếu không khớp blueprint sẽ được giữ nguyên, "
            "không bị xóa hoặc tự ý gộp."
        )
        return lines

    def _plan_lines(self, guild: discord.Guild) -> List[str]:
        lines: List[str] = [
            "PRESERVE-FIRST PLAN",
            "Không xóa role, category, channel hoặc tin nhắn.",
            "",
        ]

        for spec in ROLE_SPECS:
            role = self._find_role(guild, spec["name"], spec.get("aliases", []))
            if role is None:
                lines.append(f"[CREATE ROLE] {spec['name']}")
            elif role.name != spec["name"]:
                lines.append(f"[REUSE + RENAME ROLE] {role.name} -> {spec['name']}")
            else:
                lines.append(f"[REUSE ROLE] {role.name}")

        lines.append("")
        for category_spec in CATEGORIES:
            category = self._find_category(
                guild, category_spec["name"], category_spec.get("aliases", [])
            )
            if category is None:
                lines.append(f"[CREATE CATEGORY] {category_spec['name']}")
            elif category.name != category_spec["name"]:
                lines.append(
                    f"[REUSE + RENAME CATEGORY] {category.name} "
                    f"-> {category_spec['name']}"
                )
            else:
                lines.append(f"[REUSE CATEGORY] {category.name}")

            for channel_spec in category_spec["channels"]:
                channel = self._find_channel_anywhere(
                    guild,
                    channel_spec["type"],
                    channel_spec["name"],
                    channel_spec.get("aliases", []),
                )
                if channel is None:
                    lines.append(
                        f"  [CREATE] {channel_spec['type']} {channel_spec['name']}"
                    )
                    continue

                actions = ["REUSE"]
                if channel.name != channel_spec["name"]:
                    actions.append("RENAME")
                if category is not None and channel.category_id != category.id:
                    actions.append("MOVE")
                lines.append(
                    f"  [{' + '.join(actions)}] {channel.name} "
                    f"-> {category_spec['name']}"
                )

        lines.extend(
            [
                "",
                "[OPTIMIZE]",
                "• Chuẩn hóa permission của các thành phần được blueprint nhận diện.",
                "• Khóa bot-errors/bot-logs cho Nội Các + bot.",
                "• Đặt resources, feeds và now-playing thành kênh chỉ đọc.",
                "• Cấp Connect/Speak cho bot tại voice channel.",
                "• Giữ nguyên mọi thành phần không được nhận diện.",
                "",
                "[LAUNCH]",
                "• Chỉ đăng nội dung mẫu vào channel trống.",
                "• Không ghi đè tin nhắn đã có.",
                "• Tạo dashboard kiểm tra Audio và các cog hữu ích.",
            ]
        )
        return lines

    def _status_lines(self, guild: discord.Guild) -> List[str]:
        missing_roles: List[str] = []
        missing_categories: List[str] = []
        missing_channels: List[str] = []

        for spec in ROLE_SPECS:
            if self._find_role(guild, spec["name"], spec.get("aliases", [])) is None:
                missing_roles.append(spec["name"])

        for category_spec in CATEGORIES:
            category = self._find_category(
                guild, category_spec["name"], category_spec.get("aliases", [])
            )
            if category is None:
                missing_categories.append(category_spec["name"])

            for channel_spec in category_spec["channels"]:
                channel = self._find_channel_anywhere(
                    guild,
                    channel_spec["type"],
                    channel_spec["name"],
                    channel_spec.get("aliases", []),
                )
                if channel is None:
                    missing_channels.append(
                        f"{category_spec['name']} / {channel_spec['name']}"
                    )

        lines = self._required_permission_lines(guild)
        lines.append("")
        if not missing_roles and not missing_categories and not missing_channels:
            lines.append("[READY] Cây server theo blueprint đã đầy đủ.")
        else:
            if missing_roles:
                lines.append("[MISSING ROLES] " + ", ".join(missing_roles))
            if missing_categories:
                lines.append("[MISSING CATEGORIES] " + ", ".join(missing_categories))
            if missing_channels:
                preview = missing_channels[:25]
                suffix = (
                    f", … +{len(missing_channels) - 25}"
                    if len(missing_channels) > 25
                    else ""
                )
                lines.append("[MISSING CHANNELS] " + ", ".join(preview) + suffix)

        loaded = self._loaded_cog_status()
        lines.append("")
        lines.extend(loaded)
        return lines

    def _loaded_cog_status(self) -> List[str]:
        checks = [
            ("Audio", "nghe nhạc"),
            ("Downloader", "cài community cog"),
            ("General", "tiện ích cơ bản"),
            ("CustomCommands", "lệnh tùy chỉnh"),
            ("Permissions", "giới hạn lệnh theo role/channel"),
        ]
        result = []
        for cog_name, purpose in checks:
            state = "LOADED" if self.bot.get_cog(cog_name) else "NOT LOADED"
            result.append(f"[{state}] {cog_name}: {purpose}")
        return result

    @staticmethod
    def _duplicate_names(names: Sequence[str]) -> List[str]:
        counts = Counter(normalise(name) for name in names)
        duplicate_keys = {key for key, value in counts.items() if key and value > 1}
        return sorted({name for name in names if normalise(name) in duplicate_keys})

    def _find_role(
        self, guild: discord.Guild, name: str, aliases: Iterable[str]
    ) -> Optional[discord.Role]:
        return next(
            (
                role
                for role in guild.roles
                if role != guild.default_role and matches(role.name, name, aliases)
            ),
            None,
        )

    def _find_category(
        self, guild: discord.Guild, name: str, aliases: Iterable[str]
    ) -> Optional[discord.CategoryChannel]:
        return next(
            (
                category
                for category in guild.categories
                if matches(category.name, name, aliases)
            ),
            None,
        )

    def _find_channel_anywhere(
        self,
        guild: discord.Guild,
        channel_type: str,
        name: str,
        aliases: Iterable[str],
    ) -> Optional[Channel]:
        expected = (
            discord.TextChannel
            if channel_type == "text"
            else discord.VoiceChannel
        )
        return next(
            (
                channel
                for channel in guild.channels
                if isinstance(channel, expected)
                and matches(channel.name, name, aliases)
            ),
            None,
        )

    async def _reconcile(
        self, guild: discord.Guild, optimize: bool
    ) -> Dict[str, int]:
        report = {
            "roles_created": 0,
            "categories_created": 0,
            "channels_created": 0,
            "reused": 0,
            "renamed": 0,
            "moved": 0,
            "optimized": 0,
        }

        roles: Dict[str, discord.Role] = {}
        for spec in ROLE_SPECS:
            role, changes = await self._ensure_role(guild, spec, optimize)
            roles[spec["name"]] = role
            self._record_changes(report, changes)

        owner_role = roles.get("👑 Quân Vương")
        if owner_role and guild.owner and owner_role not in guild.owner.roles:
            try:
                await guild.owner.add_roles(owner_role, reason=REASON)
            except (discord.Forbidden, discord.HTTPException):
                pass

        category_map: Dict[str, discord.CategoryChannel] = {}
        for position, category_spec in enumerate(CATEGORIES):
            category, changes = await self._ensure_category(
                guild, category_spec, roles, position, optimize
            )
            category_map[category_spec["name"]] = category
            self._record_changes(report, changes)

            for channel_spec in category_spec["channels"]:
                _, channel_changes = await self._ensure_channel(
                    guild,
                    category,
                    channel_spec,
                    category_spec["policy"],
                    roles,
                    optimize,
                )
                self._record_changes(report, channel_changes)

        if optimize:
            await self._set_afk_channel_if_possible(guild, category_map)

        return report

    @staticmethod
    def _record_changes(report: Dict[str, int], changes: Sequence[str]) -> None:
        for change in changes:
            report[change] = report.get(change, 0) + 1

    def _cap_role_permissions(
        self, guild: discord.Guild, desired: discord.Permissions
    ) -> discord.Permissions:
        """
        Discord does not allow a bot to grant guild permissions it does not possess.
        Keep only supported permissions instead of failing the entire flow.
        """
        me = guild.me
        if me is None or me.guild_permissions.administrator:
            return desired

        allowed = discord.Permissions.none()
        for name, enabled in desired:
            if enabled and getattr(me.guild_permissions, name, False):
                setattr(allowed, name, True)
        return allowed

    def _cap_overwrites(
        self,
        guild: discord.Guild,
        overwrites: Dict[
            Union[discord.Role, discord.Member], discord.PermissionOverwrite
        ],
        available: Optional[discord.Permissions] = None,
    ) -> Dict[
        Union[discord.Role, discord.Member], discord.PermissionOverwrite
    ]:
        """
        Channel overwrite endpoints are checked against the bot's effective
        permissions in the guild or parent channel. Positive grants that the bot
        cannot currently exercise are omitted.
        """
        me = guild.me
        if me is None:
            return {}
        if me.guild_permissions.administrator:
            return overwrites

        available = available or me.guild_permissions
        filtered: Dict[
            Union[discord.Role, discord.Member], discord.PermissionOverwrite
        ] = {}

        for target, overwrite in overwrites.items():
            safe = discord.PermissionOverwrite()
            for name, value in overwrite:
                if value is True and not getattr(available, name, False):
                    continue
                setattr(safe, name, value)
            filtered[target] = safe

        return filtered

    async def _ensure_role(
        self, guild: discord.Guild, spec: dict, optimize: bool
    ) -> Tuple[discord.Role, List[str]]:
        existing = self._find_role(guild, spec["name"], spec.get("aliases", []))
        desired = discord.Permissions.none()
        desired.update(**spec.get("permissions", {}))
        desired = self._cap_role_permissions(guild, desired)

        if existing is None:
            self._op(guild, f"create role: {spec['name']}")
            role = await guild.create_role(
                name=spec["name"],
                colour=discord.Colour(spec["colour"]),
                permissions=desired,
                hoist=spec.get("hoist", False),
                mentionable=False,
                reason=REASON,
            )
            return role, ["roles_created"]

        changes: List[str] = ["reused"]
        editable = (
            guild.me is not None
            and existing < guild.me.top_role
            and not existing.managed
        )
        if not editable:
            return existing, changes

        edit_kwargs = {}
        if existing.name != spec["name"]:
            edit_kwargs["name"] = spec["name"]
            changes.append("renamed")

        if optimize:
            merged = existing.permissions
            for permission_name, enabled in desired:
                if enabled:
                    setattr(merged, permission_name, True)
            edit_kwargs.update(
                colour=discord.Colour(spec["colour"]),
                hoist=spec.get("hoist", False),
                permissions=merged,
            )
            changes.append("optimized")

        if edit_kwargs:
            self._op(guild, f"edit role: {existing.name}")
            await existing.edit(reason=REASON, **edit_kwargs)
        return existing, changes

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
        overwrites = self._policy_overwrites(
            guild, spec["policy"], roles, is_voice=False
        )
        guild_available = guild.me.guild_permissions if guild.me else None
        overwrites = self._cap_overwrites(guild, overwrites, guild_available)

        if existing is None:
            self._op(guild, f"create category: {spec['name']}")
            category = await guild.create_category(
                spec["name"],
                overwrites=overwrites,
                position=position,
                reason=REASON,
            )
            return category, ["categories_created"]

        changes: List[str] = ["reused"]
        edit_kwargs = {}
        if existing.name != spec["name"]:
            edit_kwargs["name"] = spec["name"]
            changes.append("renamed")
        if optimize:
            effective = existing.permissions_for(guild.me)
            if effective.manage_roles or guild.me.guild_permissions.administrator:
                safe_overwrites = self._cap_overwrites(
                    guild, overwrites, effective
                )
                edit_kwargs["overwrites"] = safe_overwrites
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
        overwrites = self._channel_overwrites(
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
        safe_overwrites = self._cap_overwrites(
            guild, overwrites, parent_effective
        )
        existing = self._find_channel_anywhere(
            guild,
            spec["type"],
            spec["name"],
            spec.get("aliases", []),
        )

        if existing is None:
            create_overwrites = (
                safe_overwrites
                if parent_effective is not None
                and (
                    parent_effective.manage_roles
                    or guild.me.guild_permissions.administrator
                )
                else None
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
        effective = existing.permissions_for(guild.me)
        can_manage_channel = (
            effective.manage_channels
            or guild.me.guild_permissions.administrator
        )
        can_manage_overwrites = (
            effective.manage_roles
            or guild.me.guild_permissions.administrator
        )

        if can_manage_channel and existing.name != spec["name"]:
            edit_kwargs["name"] = spec["name"]
            changes.append("renamed")

        target_effective = category.permissions_for(guild.me)
        can_manage_target = (
            target_effective.manage_channels
            or guild.me.guild_permissions.administrator
        )
        if (
            can_manage_channel
            and can_manage_target
            and existing.category_id != category.id
        ):
            edit_kwargs["category"] = category
            changes.append("moved")

        if optimize and can_manage_channel:
            if can_manage_overwrites:
                edit_kwargs["overwrites"] = self._cap_overwrites(
                    guild, overwrites, effective
                )
            if isinstance(existing, discord.TextChannel):
                edit_kwargs["topic"] = spec.get("topic")
                edit_kwargs["slowmode_delay"] = spec.get("slowmode_delay", 0)
            elif isinstance(existing, discord.VoiceChannel):
                edit_kwargs["user_limit"] = spec.get("user_limit", 0)
            changes.append("optimized")
        elif (
            can_manage_channel
            and isinstance(existing, discord.TextChannel)
            and not existing.topic
            and spec.get("topic")
        ):
            edit_kwargs["topic"] = spec["topic"]

        if edit_kwargs:
            self._op(
                guild,
                f"edit channel: "
                f"{existing.category.name + '/' if existing.category else ''}"
                f"{existing.name}",
            )
            await existing.edit(reason=REASON, **edit_kwargs)
        return existing, changes

    def _policy_overwrites(
        self,
        guild: discord.Guild,
        policy: str,
        roles: Dict[str, discord.Role],
        is_voice: bool,
    ) -> Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:
        everyone = guild.default_role
        owner_role = roles["👑 Quân Vương"]
        cabinet = roles["🏛️ Nội Các"]
        guard = roles["🛡️ Cận Vệ"]
        bot_member = guild.me

        if is_voice:
            public = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
            )
            denied = discord.PermissionOverwrite(view_channel=False, connect=False)
            staff = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                move_members=True,
                mute_members=True,
                deafen_members=True,
            )
            bot = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
            )
        else:
            public = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
                embed_links=True,
                attach_files=True,
                create_public_threads=True,
                send_messages_in_threads=True,
                mention_everyone=False,
            )
            denied = discord.PermissionOverwrite(view_channel=False)
            staff = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_threads=True,
                create_public_threads=True,
                create_private_threads=True,
                send_messages_in_threads=True,
                mention_everyone=False,
            )
            bot = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_threads=True,
                connect=True,
                speak=True,
                mention_everyone=False,
            )

        if policy == "private_staff":
            return {
                everyone: denied,
                owner_role: staff,
                cabinet: staff,
                guard: staff,
                bot_member: bot,
            }

        if policy == "public_read_only":
            read_only = (
                discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=False
                )
                if is_voice
                else discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                    add_reactions=True,
                    create_public_threads=False,
                    send_messages_in_threads=False,
                    mention_everyone=False,
                )
            )
            return {
                everyone: read_only,
                owner_role: staff,
                cabinet: staff,
                guard: staff,
                bot_member: bot,
            }

        return {
            everyone: public,
            owner_role: staff,
            cabinet: staff,
            guard: staff,
            bot_member: bot,
        }

    def _channel_overwrites(
        self,
        guild: discord.Guild,
        base_policy: str,
        channel_policy: str,
        roles: Dict[str, discord.Role],
        is_voice: bool,
    ) -> Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:
        policy = base_policy if channel_policy == "inherit" else channel_policy
        overwrites = self._policy_overwrites(
            guild, policy, roles, is_voice=is_voice
        )
        if is_voice:
            return overwrites

        everyone = guild.default_role
        owner_role = roles["👑 Quân Vương"]
        cabinet = roles["🏛️ Nội Các"]
        guard = roles["🛡️ Cận Vệ"]
        bot_member = guild.me

        if channel_policy == "private_staff_bot":
            staff = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                mention_everyone=False,
            )
            overwrites = {
                everyone: discord.PermissionOverwrite(view_channel=False),
                owner_role: staff,
                cabinet: staff,
                guard: staff,
                bot_member: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    manage_messages=True,
                    mention_everyone=False,
                ),
            }

        elif channel_policy == "bot_post_only":
            staff = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                mention_everyone=False,
            )
            overwrites = {
                everyone: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                    add_reactions=True,
                    mention_everyone=False,
                ),
                owner_role: staff,
                cabinet: staff,
                guard: staff,
                bot_member: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    mention_everyone=False,
                ),
            }

        elif channel_policy == "staff_post_only":
            staff_post = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                mention_everyone=False,
            )
            overwrites = {
                everyone: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                    add_reactions=True,
                    mention_everyone=False,
                ),
                owner_role: staff_post,
                cabinet: staff_post,
                guard: staff_post,
                bot_member: staff_post,
            }

        return overwrites

    async def _set_afk_channel_if_possible(
        self,
        guild: discord.Guild,
        category_map: Dict[str, discord.CategoryChannel],
    ) -> None:
        me = guild.me
        if me is None or not me.guild_permissions.manage_guild:
            return
        afk = self._find_channel_anywhere(guild, "voice", "🔇 AFK", ["AFK"])
        if isinstance(afk, discord.VoiceChannel) and guild.afk_channel != afk:
            try:
                await guild.edit(
                    afk_channel=afk,
                    afk_timeout=300,
                    reason=REASON,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _launch(self, ctx: commands.Context) -> Dict[str, int]:
        guild = ctx.guild
        report = {"seeded": 0, "launch_dashboard": 0}

        for category_spec in CATEGORIES:
            for channel_spec in category_spec["channels"]:
                seed = channel_spec.get("seed")
                if not seed or channel_spec["type"] != "text":
                    continue

                channel = self._find_channel_anywhere(
                    guild,
                    "text",
                    channel_spec["name"],
                    channel_spec.get("aliases", []),
                )
                if isinstance(channel, discord.TextChannel):
                    if await self._seed_if_empty(channel, seed):
                        report["seeded"] += 1

        command_channel = self._find_channel_anywhere(
            guild, "text", "bot-commands", []
        )
        if isinstance(command_channel, discord.TextChannel):
            if await self._post_launch_dashboard(command_channel, ctx.clean_prefix):
                report["launch_dashboard"] += 1
        else:
            await ctx.send(
                "⚠️ Không tìm thấy `#bot-commands`; hãy chạy bước reconcile trước."
            )

        return report

    async def _seed_if_empty(
        self, channel: discord.TextChannel, seed: dict
    ) -> bool:
        try:
            messages = [message async for message in channel.history(limit=20)]
        except discord.Forbidden:
            return False

        for message in messages:
            if any(
                embed.footer and embed.footer.text == MARKER
                for embed in message.embeds
            ):
                return False

        # Preserve user/bot content. Starter content is only added to an empty channel.
        if messages:
            return False

        embed = discord.Embed(
            title=seed["title"],
            description=seed["description"],
            colour=discord.Colour.gold(),
        )
        embed.set_footer(text=MARKER)
        self._op(channel.guild, f"send starter embed: #{channel.name}")
        self._op(channel.guild, f"send launch dashboard: #{channel.name}")
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True

    async def _post_launch_dashboard(
        self, channel: discord.TextChannel, prefix: str
    ) -> bool:
        try:
            async for message in channel.history(limit=50):
                if any(
                    embed.footer and embed.footer.text == LAUNCH_MARKER
                    for embed in message.embeds
                ):
                    return False
        except discord.Forbidden:
            return False

        checks = {
            "Audio": self.bot.get_cog("Audio") is not None,
            "Downloader": self.bot.get_cog("Downloader") is not None,
            "General": self.bot.get_cog("General") is not None,
            "CustomCommands": self.bot.get_cog("CustomCommands") is not None,
            "Permissions": self.bot.get_cog("Permissions") is not None,
        }
        status = "\n".join(
            f"{'✅' if loaded else '⚠️'} **{name}**"
            for name, loaded in checks.items()
        )
        next_commands = [
            f"`{prefix}help` — kiểm tra bot",
            f"`{prefix}help Audio` — xem lệnh nhạc",
            f"`{prefix}deche status` — kiểm tra cây server",
        ]
        if not checks["Audio"]:
            next_commands.append(f"`{prefix}load audio` — nạp Audio cog")
        if not checks["General"]:
            next_commands.append(f"`{prefix}load general` — nạp tiện ích cơ bản")
        if not checks["Permissions"]:
            next_commands.append(
                f"`{prefix}load permissions` — quản lý quyền lệnh nâng cao"
            )

        embed = discord.Embed(
            title="🚀 Server đã sẵn sàng để bắt đầu",
            description=(
                "ImperialSetup đã tái sử dụng phần bạn dựng, bổ sung phần thiếu "
                "và tối ưu các thành phần được nhận diện."
            ),
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Cog readiness", value=status, inline=False)
        embed.add_field(
            name="Ba việc đầu tiên",
            value="\n".join(next_commands),
            inline=False,
        )
        embed.add_field(
            name="Quy tắc vận hành",
            value=(
                "Dùng `#bot-commands` cho lệnh, `#music-request` cho nhạc, "
                "`#bot-errors` cho lỗi và `#server-todo` cho việc cần cải tiến."
            ),
            inline=False,
        )
        embed.set_footer(text=LAUNCH_MARKER)
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
