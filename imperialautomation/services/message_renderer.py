\
from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List, Optional

import discord


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: Any, limit: int = 500) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def funny_headline(title: str, topic: str) -> str:
    title = clean_text(title, 180)
    topic_key = topic.casefold()

    suffixes = {
        "dev": "cộng đồng đã kịp đề nghị viết lại toàn bộ dự án.",
        "development": "cộng đồng long trọng chuẩn bị cho lần rewrite tiếp theo.",
        "tech": "triều đình công nghệ lập tức triệu tập một cuộc họp khẩn.",
        "game": "game thủ tuyên bố hoàn toàn bình tĩnh theo cách rất không bình tĩnh.",
        "anime": "hội đồng otaku mở phiên tranh luận dài hơn chính bộ phim.",
        "meme-news": "sử quan xác nhận đây là chuyện thật, đáng tiếc thay.",
        "meme": "sử quan xác nhận đây là chuyện thật, đáng tiếc thay.",
    }
    suffix = suffixes.get(
        topic_key,
        "quần thần đồng loạt gật đầu dù chưa ai đọc hết bài.",
    )
    return f"“{title} — {suffix}”"


def feed_embed(item: Dict[str, Any]) -> discord.Embed:
    topic = str(item.get("topic") or "general")
    score = int(item.get("score") or 0)

    embed = discord.Embed(
        title="🗞 TRIỀU ĐÌNH HÓNG CHUYỆN",
        description=funny_headline(str(item.get("title") or "Untitled"), topic),
        colour=discord.Colour.gold(),
        url=item.get("url"),
    )
    embed.add_field(
        name="Nguồn",
        value=clean_text(item.get("source") or "Unknown", 200),
        inline=True,
    )
    embed.add_field(
        name="Chủ đề",
        value=clean_text(topic, 50),
        inline=True,
    )
    embed.add_field(
        name="Độ thú vị",
        value=f"`{score}/100`",
        inline=True,
    )

    summary = clean_text(item.get("summary"), 700)
    if summary:
        embed.add_field(name="Tóm tắt", value=summary, inline=False)

    embed.set_footer(text="ImperialAutomation • filtered feed")
    return embed


def security_embed(item: Dict[str, Any]) -> discord.Embed:
    severity = str(item.get("severity") or "Security alert")
    embed = discord.Embed(
        title=f"🛡 {severity.upper()}",
        description=clean_text(item.get("title") or "Untitled alert", 500),
        colour=discord.Colour.red(),
        url=item.get("url"),
    )
    embed.add_field(
        name="Source",
        value=clean_text(item.get("source") or "Unknown", 200),
        inline=True,
    )
    embed.add_field(
        name="Topic",
        value=clean_text(item.get("topic") or "security", 80),
        inline=True,
    )
    summary = clean_text(item.get("summary"), 900)
    if summary:
        embed.add_field(name="Summary", value=summary, inline=False)
    embed.set_footer(text="ImperialAutomation • security routing • no humour")
    return embed


def progress_bar(position_ms: int, length_ms: int, width: int = 13) -> str:
    if length_ms <= 0:
        return "━" * width
    ratio = max(0.0, min(1.0, position_ms / length_ms))
    marker = min(width - 1, int(round(ratio * (width - 1))))
    chars = ["━"] * width
    chars[marker] = "●"
    return "".join(chars)


def format_ms(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds // 1000))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def now_playing_embed(
    *,
    title: str,
    artist: str,
    position_ms: int,
    length_ms: int,
    requester: str,
    queue_size: int,
    volume: int,
    url: Optional[str] = None,
    thumbnail: Optional[str] = None,
    is_stream: bool = False,
) -> discord.Embed:
    if is_stream:
        progress = "LIVE"
    else:
        progress = (
            f"`{format_ms(position_ms)}` "
            f"{progress_bar(position_ms, length_ms)} "
            f"`{format_ms(length_ms)}`"
        )

    embed = discord.Embed(
        title="🎵 NOW PLAYING",
        description=f"**{clean_text(title, 250)}**",
        colour=discord.Colour.blurple(),
        url=url if url and str(url).startswith("http") else None,
    )
    embed.add_field(
        name="Artist",
        value=clean_text(artist or "Unknown", 200),
        inline=False,
    )
    embed.add_field(name="Progress", value=progress, inline=False)
    embed.add_field(
        name="Requested by",
        value=clean_text(requester or "Unknown", 120),
        inline=True,
    )
    embed.add_field(name="Queue", value=f"`{queue_size}` tracks", inline=True)
    embed.add_field(name="Volume", value=f"`{volume}%`", inline=True)
    if thumbnail and str(thumbnail).startswith("http"):
        embed.set_thumbnail(url=thumbnail)
    embed.set_footer(text="ImperialAutomation • Red Audio")
    return embed


def idle_music_embed(prefix: str = "!") -> discord.Embed:
    embed = discord.Embed(
        title="🎵 NOW PLAYING",
        description=(
            "Nothing is currently playing.\n"
            f"Join **Music Lounge** and use `{prefix}play <name/link>`."
        ),
        colour=discord.Colour.dark_grey(),
    )
    embed.set_footer(text="ImperialAutomation • Red Audio")
    return embed


def digest_text(items: List[Dict[str, Any]], date_text: str) -> str:
    lines = [f"👑 **DAILY GOSSIP DIGEST — {date_text}**", ""]

    if not items:
        lines.append("_Triều đình hôm nay yên ắng một cách đáng ngờ._")
        return "\n".join(lines)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("topic") or "general"), []).append(item)

    for topic, topic_items in sorted(grouped.items()):
        lines.append(f"### {topic.upper()}")
        for item in sorted(
            topic_items,
            key=lambda value: int(value.get("score") or 0),
            reverse=True,
        )[:5]:
            title = clean_text(item.get("title"), 160)
            url = item.get("url")
            lines.append(
                f"• **{title}** — `{int(item.get('score') or 0)}/100`"
                + (f"\n  <{url}>" if url else "")
            )
        lines.append("")

    return "\n".join(lines)[:1900]
