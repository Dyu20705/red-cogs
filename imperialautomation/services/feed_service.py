\
from __future__ import annotations

import asyncio
import calendar
import contextlib
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp
import discord
from discord.ext import tasks
import feedparser
from red_commons.logging import getLogger

from .message_renderer import (
    clean_text,
    digest_text,
    feed_embed,
    security_embed,
)


log = getLogger("red.imperialautomation.feed")
VN_TZ = timezone(timedelta(hours=7), name="UTC+7")

SECURITY_TERMS = {
    "cve",
    "vulnerability",
    "zero-day",
    "zero day",
    "remote code execution",
    "rce",
    "privilege escalation",
    "exploit",
    "malware",
    "ransomware",
    "supply chain attack",
    "critical security",
    "authentication bypass",
}

INTEREST_TERMS = {
    "release",
    "launch",
    "announced",
    "open source",
    "benchmark",
    "performance",
    "framework",
    "compiler",
    "linux",
    "kubernetes",
    "python",
    "rust",
    "typescript",
    "javascript",
    "anime",
    "game",
    "update",
    "research",
    "security",
    "critical",
}

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


class FeedService:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.http: Optional[aiohttp.ClientSession] = None
        self.force_lock = asyncio.Lock()

    def start(self):
        self.feed_loop.start()

    def stop(self):
        self.feed_loop.cancel()
        if self.http is not None and not self.http.closed:
            asyncio.create_task(self.http.close())

    async def _session(self) -> aiohttp.ClientSession:
        if self.http is None or self.http.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self.http = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "ImperialAutomation/1.0 "
                        "(Red-DiscordBot filtered RSS reader)"
                    )
                },
            )
        return self.http

    @tasks.loop(minutes=5)
    async def feed_loop(self):
        now = datetime.now(VN_TZ)
        all_guilds = await self.cog.config.all_guilds()

        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            try:
                if self._feed_cycle_due(now, data):
                    await self.run_cycle(guild)

                if self._digest_due(now, data):
                    await self.post_digest(guild)
            except Exception as exc:
                await self.cog.report_error(
                    guild,
                    operation="Run ImperialAutomation feed scheduler",
                    error=exc,
                )

    @feed_loop.before_loop
    async def before_feed_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _feed_cycle_due(now: datetime, data: Dict[str, Any]) -> bool:
        last_text = data.get("feed_last_cycle")
        interval = max(20, min(30, int(data.get("feed_interval_minutes", 25))))

        if not last_text:
            return True

        try:
            last = datetime.fromisoformat(last_text)
        except (TypeError, ValueError):
            return True

        return now - last >= timedelta(minutes=interval)

    @staticmethod
    def _digest_due(now: datetime, data: Dict[str, Any]) -> bool:
        today = now.strftime("%Y-%m-%d")
        if data.get("feed_last_digest") == today:
            return False

        scheduled = now.replace(
            hour=int(data.get("feed_digest_hour", 21)),
            minute=int(data.get("feed_digest_minute", 30)),
            second=0,
            microsecond=0,
        )
        delta = (now - scheduled).total_seconds()
        return 0 <= delta <= 3 * 3600

    async def run_cycle(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ) -> int:
        if self.force_lock.locked() and force:
            return 0

        async with self.force_lock:
            data = await self.cog.config.guild(guild).all()
            sources = [
                source
                for source in data.get("feed_sources", [])
                if source.get("enabled", True)
            ]

            if not sources:
                if not force:
                    await self.cog.config.guild(guild).feed_last_cycle.set(
                        datetime.now(VN_TZ).isoformat()
                    )
                return 0

            candidates: List[Dict[str, Any]] = []
            for source in sources:
                try:
                    candidates.extend(
                        await self._fetch_source(
                            guild,
                            source,
                            max_age_hours=int(
                                data.get("feed_max_age_hours", 24)
                            ),
                        )
                    )
                except Exception as exc:
                    log.warning(
                        "Feed fetch failed for %s",
                        source.get("url"),
                        exc_info=exc,
                    )
                    await self.cog.report_error(
                        guild,
                        operation=(
                            f"Fetch RSS source "
                            f"{source.get('name') or source.get('url')}"
                        ),
                        error=exc,
                    )

            candidates.sort(
                key=lambda item: (
                    bool(item.get("security")),
                    int(item.get("score") or 0),
                    item.get("published_ts") or 0,
                ),
                reverse=True,
            )

            max_items = max(
                1,
                min(3, int(data.get("feed_max_items_per_cycle", 3))),
            )
            selected = candidates[:max_items]
            posted = 0

            for item in selected:
                if await self._post_item(guild, item):
                    await self._remember_item(guild, item)
                    posted += 1

            await self._cleanup_state(guild)
            await self.cog.config.guild(guild).feed_last_cycle.set(
                datetime.now(VN_TZ).isoformat()
            )
            return posted

    async def _fetch_source(
        self,
        guild: discord.Guild,
        source: Dict[str, Any],
        *,
        max_age_hours: int,
    ) -> List[Dict[str, Any]]:
        session = await self._session()
        url = str(source.get("url") or "")

        async with session.get(url) as response:
            response.raise_for_status()
            body = await response.read()

        parsed = await asyncio.to_thread(feedparser.parse, body)
        now_ts = datetime.now(timezone.utc).timestamp()
        cutoff_ts = now_ts - max_age_hours * 3600
        seen = await self.cog.config.guild(guild).feed_seen_urls()

        result = []
        for entry in parsed.entries[:30]:
            item_url = self._canonical_url(
                str(entry.get("link") or entry.get("id") or "")
            )
            if not item_url:
                continue

            url_hash = self._url_hash(item_url)
            if url_hash in seen:
                continue

            published_ts = self._entry_timestamp(entry)
            # Strict freshness rule: entries without a trustworthy timestamp
            # are skipped because their age cannot be verified.
            if published_ts is None or published_ts < cutoff_ts:
                continue

            title = clean_text(entry.get("title"), 300)
            summary = clean_text(
                entry.get("summary")
                or entry.get("description")
                or "",
                1000,
            )
            searchable = f"{title} {summary}".casefold()

            include = [
                str(value).casefold().strip()
                for value in source.get("include_keywords", [])
                if str(value).strip()
            ]
            exclude = [
                str(value).casefold().strip()
                for value in source.get("exclude_keywords", [])
                if str(value).strip()
            ]

            if include and not any(keyword in searchable for keyword in include):
                continue

            if exclude and any(keyword in searchable for keyword in exclude):
                continue

            security = bool(source.get("security")) or any(
                term in searchable for term in SECURITY_TERMS
            )
            score = self._score(
                searchable=searchable,
                source=source,
                published_ts=published_ts or now_ts,
                now_ts=now_ts,
                include_keywords=include,
            )

            if score < int(source.get("minimum_score", 25)):
                continue

            result.append(
                {
                    "url": item_url,
                    "url_hash": url_hash,
                    "title": title or "Untitled",
                    "summary": summary,
                    "source": source.get("name")
                    or parsed.feed.get("title")
                    or urlsplit(url).netloc,
                    "topic": source.get("topic") or "general",
                    "score": score,
                    "security": security,
                    "severity": self._security_severity(searchable),
                    "published_ts": published_ts or now_ts,
                    "fetched_at": datetime.now(VN_TZ).isoformat(),
                }
            )

        return result

    @staticmethod
    def _entry_timestamp(entry: Dict[str, Any]) -> Optional[float]:
        parsed_time = (
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or entry.get("created_parsed")
        )
        if not parsed_time:
            return None

        try:
            return float(calendar.timegm(parsed_time))
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _canonical_url(url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return ""

        parts = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMS
        ]
        return urlunsplit(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                parts.path.rstrip("/") or "/",
                urlencode(query, doseq=True),
                "",
            )
        )

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    @staticmethod
    def _score(
        *,
        searchable: str,
        source: Dict[str, Any],
        published_ts: float,
        now_ts: float,
        include_keywords: Sequence[str],
    ) -> int:
        age_hours = max(0.0, (now_ts - published_ts) / 3600)
        freshness = max(0, round(40 - age_hours * 1.5))
        priority = max(0, min(100, int(source.get("priority", 50))))
        priority_points = round(priority * 0.2)
        include_hits = sum(1 for keyword in include_keywords if keyword in searchable)
        interest_hits = sum(1 for keyword in INTEREST_TERMS if keyword in searchable)
        keyword_points = min(25, include_hits * 8 + interest_hits * 3)

        penalty = 0
        if any(
            term in searchable
            for term in ("sponsored", "advertorial", "deal:", "coupon")
        ):
            penalty += 25

        return max(
            0,
            min(100, freshness + priority_points + keyword_points - penalty),
        )

    @staticmethod
    def _security_severity(searchable: str) -> str:
        if any(
            term in searchable
            for term in (
                "critical",
                "zero-day",
                "zero day",
                "remote code execution",
                "rce",
                "actively exploited",
            )
        ):
            return "Critical security alert"
        return "Security alert"

    async def _post_item(
        self,
        guild: discord.Guild,
        item: Dict[str, Any],
    ) -> bool:
        data = await self.cog.config.guild(guild).all()

        if item.get("security"):
            channel_id = data.get("feed_alert_channel_id")
            channel = guild.get_channel(channel_id) if channel_id else None
            if not isinstance(channel, discord.TextChannel):
                channel_id = data.get("all_feeds_channel_id")
                channel = guild.get_channel(channel_id) if channel_id else None

            if not isinstance(channel, discord.TextChannel):
                return False

            await channel.send(
                embed=security_embed(item),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True

        channel_id = data.get("all_feeds_channel_id")
        parent = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(parent, discord.TextChannel):
            return False

        destination: Any = parent
        if data.get("feed_thread_mode", True):
            destination = await self._topic_thread(
                guild,
                parent,
                str(item.get("topic") or "general"),
            )

        await destination.send(
            embed=feed_embed(item),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True

    async def _topic_thread(
        self,
        guild: discord.Guild,
        parent: discord.TextChannel,
        topic: str,
    ):
        date_key = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        mapping_key = f"{date_key}:{topic.casefold()}"
        guild_conf = self.cog.config.guild(guild)
        thread_ids = await guild_conf.feed_topic_threads()
        thread_id = thread_ids.get(mapping_key)

        if thread_id:
            thread = guild.get_thread(int(thread_id))
            if thread is None:
                with contextlib.suppress(discord.HTTPException):
                    fetched = await self.bot.fetch_channel(int(thread_id))
                    if isinstance(fetched, discord.Thread):
                        thread = fetched
            if thread is not None:
                if thread.archived:
                    with contextlib.suppress(discord.HTTPException):
                        await thread.edit(archived=False)
                return thread

        try:
            thread = await parent.create_thread(
                name=f"{topic.lower()} • {date_key}"[:100],
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,
                reason="ImperialAutomation feed topic thread",
            )
        except discord.HTTPException:
            return parent

        async with guild_conf.feed_topic_threads() as stored:
            stored[mapping_key] = thread.id
            if len(stored) > 100:
                for key in sorted(stored)[:-100]:
                    stored.pop(key, None)

        return thread

    async def _remember_item(
        self,
        guild: discord.Guild,
        item: Dict[str, Any],
    ):
        guild_conf = self.cog.config.guild(guild)
        now_iso = datetime.now(VN_TZ).isoformat()

        async with guild_conf.feed_seen_urls() as seen:
            seen[item["url_hash"]] = now_iso

        if not item.get("security"):
            async with guild_conf.feed_digest_items() as digest:
                digest.append(
                    {
                        "date": datetime.now(VN_TZ).strftime("%Y-%m-%d"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "topic": item.get("topic"),
                        "score": item.get("score"),
                        "source": item.get("source"),
                    }
                )
                if len(digest) > 200:
                    del digest[:-200]

    async def _cleanup_state(self, guild: discord.Guild):
        cutoff = datetime.now(VN_TZ) - timedelta(days=30)
        guild_conf = self.cog.config.guild(guild)

        async with guild_conf.feed_seen_urls() as seen:
            for key, timestamp in list(seen.items()):
                try:
                    recorded = datetime.fromisoformat(timestamp)
                except (TypeError, ValueError):
                    seen.pop(key, None)
                    continue
                if recorded < cutoff:
                    seen.pop(key, None)

        digest_cutoff = (
            datetime.now(VN_TZ).date() - timedelta(days=7)
        ).strftime("%Y-%m-%d")
        async with guild_conf.feed_digest_items() as items:
            items[:] = [
                item
                for item in items
                if str(item.get("date") or "") >= digest_cutoff
            ]

    async def post_digest(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ) -> bool:
        guild_conf = self.cog.config.guild(guild)
        data = await guild_conf.all()
        channel_id = data.get("all_feeds_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return False

        today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        items = [
            item
            for item in data.get("feed_digest_items", [])
            if item.get("date") == today
        ]
        items.sort(
            key=lambda item: int(item.get("score") or 0),
            reverse=True,
        )

        await channel.send(
            digest_text(items[:15], datetime.now(VN_TZ).strftime("%d/%m/%Y")),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if not force:
            await guild_conf.feed_last_digest.set(today)
        return True
