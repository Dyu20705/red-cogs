from __future__ import annotations

import discord
from redbot.core import commands

from .blueprint import CATEGORIES
from .hardening import ImperialSetup as BaseImperialSetup


ANNOUNCEMENT_MARKER = "IMPERIAL_SERVER_ANNOUNCEMENT_V1"


def _category(name: str) -> dict:
    return next(item for item in CATEGORIES if item["name"] == name)


def _text_channel(category: dict, name: str) -> dict | None:
    return next(
        (
            item
            for item in category["channels"]
            if item.get("type") == "text" and item.get("name") == name
        ),
        None,
    )


def _extend_blueprint() -> None:
    about = _category("📜 ABOUT")
    announcements = _text_channel(about, "announcements")
    if announcements is not None:
        announcements.update(
            topic="Cáo thị và cập nhật quan trọng được bot tự động công bố.",
            seed={
                "title": "📢 Bảng cáo thị",
                "description": "Các cập nhật quan trọng của server sẽ xuất hiện tại đây.",
            },
        )

    cabinet = _category("🔒 NỘI CÁC")
    audit = _text_channel(cabinet, "audit-and-mod-log")
    if audit is not None:
        audit.update(
            topic="Nhật ký tự động về kiểm duyệt, quản trị và biến động server.",
            seed={
                "title": "🛡️ AUDIT & MOD LOG — NGỰ SỬ ĐÀI",
                "description": (
                    "Nơi ghi lại mọi biến động quan trọng trong triều đình:\n\n"
                    "• Tin nhắn bị sửa hoặc xóa.\n"
                    "• Thành viên vào, rời hoặc bị xử lý.\n"
                    "• Thay đổi role, kênh và quyền hạn.\n"
                    "• Hoạt động quản trị và cảnh báo bảo mật.\n"
                    "• Những hành vi đáng ngờ cần được kiểm tra.\n\n"
                    "Đây là **kênh nhật ký tự động**, không dùng để trò chuyện "
                    "hay gọi lệnh bot.\n\n"
                    "> Mọi dấu vết đều được lưu.\n"
                    "> Ngự Sử có thể im lặng, nhưng chưa bao giờ không nhìn thấy."
                ),
            },
        )

    study = _category("📚 STUDY")
    study_log = _text_channel(study, "study-log")
    if study_log is not None:
        study_log.update(
            topic="Nhật ký học tự động từ Pomodoro và phòng học voice.",
            policy="bot_post_only",
            seed={
                "title": "📝 STUDY LOG — NHẬT TRÌNH HỌC TẬP",
                "description": (
                    "Bot tự ghi lại Pomodoro hoàn thành, thời lượng học trong voice "
                    "và tổng thời gian tập trung trong ngày tại đây.\n\n"
                    "Đây là **kênh log tự động**, không dùng để trò chuyện."
                ),
            },
        )

    if _text_channel(study, "leet-code") is None:
        insert_at = next(
            (
                index
                for index, item in enumerate(study["channels"])
                if item.get("type") == "voice"
            ),
            len(study["channels"]),
        )
        study["channels"].insert(
            insert_at,
            {
                "type": "text",
                "name": "leet-code",
                "aliases": ["leetcode", "leet-code-daily"],
                "topic": "Nhắc LeetCode Daily và quy trình luyện thuật toán mỗi ngày.",
                "policy": "bot_post_only",
                "seed": {
                    "title": "🧩 LEETCODE — LUYỆN CÔNG THUẬT TOÁN",
                    "description": (
                        "Bot sẽ đăng lời nhắc LeetCode hằng ngày tại đây.\n\n"
                        "Quy trình gợi ý: đọc đề → tự phân tích → code → tối ưu → "
                        "ghi lại độ phức tạp và bài học rút ra."
                    ),
                },
            },
        )


_extend_blueprint()


class ImperialSetup(BaseImperialSetup):
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
                        f"Chạy `{ctx.clean_prefix}deche diagnose` rồi gửi báo cáo "
                        "nếu lỗi còn lặp lại."
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

            await self._auto_wire_cogs(ctx.guild, post_leetcode=mode in {"launch", "auto"})
            await progress.edit(
                content=self._format_result(mode, result, ctx.clean_prefix)
            )
            await self._post_server_announcement(ctx.guild, ctx.author, mode, result)

    async def _auto_wire_cogs(
        self,
        guild: discord.Guild,
        *,
        post_leetcode: bool,
    ) -> None:
        def text(name: str, aliases: list[str] | None = None):
            channel = self._find_channel_anywhere(
                guild,
                "text",
                name,
                aliases or [],
            )
            return channel if isinstance(channel, discord.TextChannel) else None

        study = self.bot.get_cog("StudyOps")
        if study is not None and hasattr(study, "config"):
            guild_conf = study.config.guild(guild)
            bindings = {
                "daily_goals_channel_id": text("goals-and-progress"),
                "progress_channel_id": text("goals-and-progress"),
                "study_log_channel_id": text("study-log"),
                "leetcode_channel_id": text("leet-code", ["leetcode", "leet-code-daily"]),
            }
            for key, channel in bindings.items():
                if channel is not None and hasattr(guild_conf, key):
                    await getattr(guild_conf, key).set(channel.id)

            post_method = getattr(study, "post_leetcode_daily", None)
            if post_leetcode and callable(post_method):
                await post_method(guild, force=True)

        botops = self.bot.get_cog("BotOps")
        if botops is not None and hasattr(botops, "config"):
            guild_conf = botops.config.guild(guild)
            bindings = {
                "audit_channel_id": text("audit-and-mod-log"),
                "errors_channel_id": text("bot-errors"),
                "logs_channel_id": text("bot-logs"),
            }
            for key, channel in bindings.items():
                if channel is not None and hasattr(guild_conf, key):
                    await getattr(guild_conf, key).set(channel.id)

    async def _post_server_announcement(
        self,
        guild: discord.Guild,
        actor: discord.abc.User,
        mode: str,
        report: dict[str, int],
    ) -> None:
        channel = self._find_channel_anywhere(
            guild,
            "text",
            "announcements",
            [],
        )
        if not isinstance(channel, discord.TextChannel):
            return

        labels = {
            "roles_created": "role mới",
            "categories_created": "category mới",
            "channels_created": "channel mới",
            "renamed": "thành phần đổi tên",
            "moved": "channel được sắp lại",
            "optimized": "thành phần tối ưu",
            "seeded": "kênh nhận nội dung mở đầu",
        }
        changes = [
            f"• **{value}** {labels[key]}"
            for key, value in report.items()
            if value and key in labels
        ]
        if not changes:
            changes = ["• Không có thay đổi cấu trúc mới; hệ thống đã được kiểm tra."]

        embed = discord.Embed(
            title="📢 CÁO THỊ CẬP NHẬT SERVER",
            description=(
                f"ImperialSetup đã hoàn tất chế độ **{mode}**.\n\n"
                + "\n".join(changes)
            ),
            colour=discord.Colour.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Người thực hiện",
            value=getattr(actor, "display_name", str(actor)),
            inline=False,
        )
        embed.set_footer(text=ANNOUNCEMENT_MARKER)

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            return
