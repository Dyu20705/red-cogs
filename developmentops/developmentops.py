\
from __future__ import annotations

import asyncio
import contextlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
from aiohttp import web
import discord
from discord.ext import tasks
from red_commons.logging import getLogger
from redbot.core import Config, commands

from .dedupe import DeliveryDedupe
from .security import verify_github_signature
from .settings import DevelopmentOpsSettings


log = getLogger("red.developmentops")
VN_TZ = timezone(timedelta(hours=7), name="UTC+7")
API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
DAY_FMT = "%Y-%m-%d"

MANAGED_FORUM_LABELS = {
    "bug",
    "feature",
    "question",
    "ui-ux",
    "performance",
    "blocked",
    "resolved",
}

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status
        self.message = message


class DevelopmentOps(commands.Cog):
    """GitHub webhook routing and development workflow automation."""

    __red_end_user_data_statement__ = (
        "This cog stores Discord guild/channel/thread IDs, GitHub repository names, "
        "issue-to-forum mappings, pull-request thread mappings, and schedule settings. "
        "GitHub tokens and webhook secrets are read only from environment variables."
    )

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=2809200504,
            force_registration=True,
        )

        self.config.register_guild(
            repositories=[],
            primary_repo=None,
            github_feed_channel_id=None,
            release_channel_id=None,
            code_review_channel_id=None,
            bugs_forum_channel_id=None,
            daily_goals_channel_id=None,
            daily_hour=7,
            daily_minute=5,
            timezone="Asia/Bangkok",
            milestone_title=None,
            review_label="review-needed",
            daily_labels=["daily-goal", "weekly-goal"],
            forum_sync_enabled=True,
            last_daily_post="",
            pr_threads={},
            forum_to_issue={},
            issue_to_forum={},
        )

        self.settings = DevelopmentOpsSettings.from_env()
        self.webhook_secret = self.settings.webhook_secret
        self.github_token = self.settings.github_token
        self.web_host = self.settings.host
        self.web_port = self.settings.port

        self.http_session: Optional[aiohttp.ClientSession] = None
        self.web_runner: Optional[web.AppRunner] = None
        self.web_site: Optional[web.TCPSite] = None
        self.web_start_error: Optional[str] = None

        self.delivery_dedupe = DeliveryDedupe(ttl_seconds=24 * 3600, max_size=1000)
        self.webhook_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._tasks: set[asyncio.Task] = set()
        self.web_start_task = self._track_task(
            self._start_webserver(),
            "start DevelopmentOps receiver",
        )
        self.web_worker_task = self._track_task(
            self._webhook_worker(),
            "DevelopmentOps webhook worker",
        )
        self.daily_loop.start()

    def cog_unload(self):
        self.daily_loop.cancel()

        for task in list(self._tasks):
            task.cancel()

        self._track_task(self._close_resources(), "close DevelopmentOps resources")

    def _track_task(self, awaitable, label: str) -> asyncio.Task:
        task = asyncio.create_task(awaitable)
        self._tasks.add(task)

        def _done(done: asyncio.Task) -> None:
            self._tasks.discard(done)
            if done.cancelled():
                return
            with contextlib.suppress(Exception):
                exc = done.exception()
                if exc is not None:
                    log.error(
                        "DevelopmentOps task failed: %s: %s",
                        label,
                        exc.__class__.__name__,
                        exc_info=exc,
                    )

        task.add_done_callback(_done)
        return task

    async def _close_resources(self):
        if self.web_runner is not None:
            with contextlib.suppress(Exception):
                await self.web_runner.cleanup()
            self.web_runner = None
            self.web_site = None

        if self.http_session is not None and not self.http_session.closed:
            with contextlib.suppress(Exception):
                await self.http_session.close()

    # ------------------------------------------------------------------
    # Configuration commands
    # ------------------------------------------------------------------

    @commands.group(name="devset")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def devset(self, ctx: commands.Context):
        """Configure DevelopmentOps."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @devset.group(name="repo")
    async def devset_repo(self, ctx: commands.Context):
        """Manage watched GitHub repositories."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @devset_repo.command(name="add")
    async def devset_repo_add(self, ctx: commands.Context, repository: str):
        """Add `owner/repository` to this Discord server."""

        repository = repository.strip()

        if not REPO_PATTERN.fullmatch(repository):
            await ctx.send("❌ Repository phải có dạng `owner/repository`.")
            return

        guild_conf = self.config.guild(ctx.guild)

        async with guild_conf.repositories() as repositories:
            normalized = {repo.casefold() for repo in repositories}

            if repository.casefold() not in normalized:
                repositories.append(repository)

        primary_repo = await guild_conf.primary_repo()
        if not primary_repo:
            await guild_conf.primary_repo.set(repository)

        await self._audit(
            ctx,
            "Added GitHub repository",
            "not watched",
            repository,
        )
        await ctx.send(f"✅ Watching **{repository}**.")

    @devset_repo.command(name="remove")
    async def devset_repo_remove(self, ctx: commands.Context, repository: str):
        """Remove a watched repository."""

        guild_conf = self.config.guild(ctx.guild)
        removed = None

        async with guild_conf.repositories() as repositories:
            for existing in list(repositories):
                if existing.casefold() == repository.casefold():
                    repositories.remove(existing)
                    removed = existing
                    break

        if removed is None:
            await ctx.send("❌ Repository không nằm trong danh sách theo dõi.")
            return

        if (await guild_conf.primary_repo() or "").casefold() == removed.casefold():
            remaining = await guild_conf.repositories()
            await guild_conf.primary_repo.set(remaining[0] if remaining else None)

        await self._audit(
            ctx,
            "Removed GitHub repository",
            removed,
            "not watched",
        )
        await ctx.send(f"✅ Removed **{removed}**.")

    @devset_repo.command(name="primary")
    async def devset_repo_primary(self, ctx: commands.Context, repository: str):
        """Set the repository used for Forum sync and daily goals."""

        repositories = await self.config.guild(ctx.guild).repositories()
        matched = next(
            (
                repo
                for repo in repositories
                if repo.casefold() == repository.casefold()
            ),
            None,
        )

        if matched is None:
            await ctx.send(
                "❌ Repository chưa được theo dõi. "
                f"Dùng `{ctx.clean_prefix}devset repo add owner/repository`."
            )
            return

        old_value = await self.config.guild(ctx.guild).primary_repo()
        await self.config.guild(ctx.guild).primary_repo.set(matched)

        await self._audit(
            ctx,
            "Changed primary GitHub repository",
            old_value or "none",
            matched,
        )
        await ctx.send(f"✅ Primary repository: **{matched}**.")

    @devset.command(name="channel")
    async def devset_channel(
        self,
        ctx: commands.Context,
        kind: str,
        channel: discord.TextChannel,
    ):
        """Set `feed`, `release`, `review`, or `daily` channel."""

        mapping = {
            "feed": "github_feed_channel_id",
            "release": "release_channel_id",
            "review": "code_review_channel_id",
            "daily": "daily_goals_channel_id",
        }
        key = mapping.get(kind.lower().strip())

        if key is None:
            await ctx.send("❌ Chọn `feed`, `release`, `review`, hoặc `daily`.")
            return

        missing = self._missing_text_permissions(
            channel,
            require_threads=(kind == "review"),
        )
        if missing:
            await ctx.send(
                f"❌ Bot thiếu quyền trong {channel.mention}: "
                f"**{', '.join(missing)}**"
            )
            return

        guild_conf = self.config.guild(ctx.guild)
        old_id = await getattr(guild_conf, key)()
        old_channel = ctx.guild.get_channel(old_id) if old_id else None

        await getattr(guild_conf, key).set(channel.id)

        await self._audit(
            ctx,
            f"Changed DevelopmentOps {kind} channel",
            old_channel.mention if old_channel else "none",
            channel.mention,
        )
        await ctx.send(f"✅ `{kind}` channel: {channel.mention}")

    @devset.command(name="forum")
    async def devset_forum(
        self,
        ctx: commands.Context,
        forum: discord.ForumChannel,
    ):
        """Set the bugs-and-ideas Forum channel."""

        available = {tag.name.casefold() for tag in forum.available_tags}
        missing_tags = sorted(MANAGED_FORUM_LABELS - available)

        old_id = await self.config.guild(ctx.guild).bugs_forum_channel_id()
        old_forum = ctx.guild.get_channel(old_id) if old_id else None

        await self.config.guild(ctx.guild).bugs_forum_channel_id.set(forum.id)

        await self._audit(
            ctx,
            "Changed bugs-and-ideas Forum channel",
            old_forum.name if old_forum else "none",
            forum.name,
        )

        message = f"✅ Forum channel: **{forum.name}**"
        if missing_tags:
            message += (
                "\n⚠ Hãy tạo thêm Forum tags: "
                + ", ".join(f"`{tag}`" for tag in missing_tags)
            )

        await ctx.send(message)

    @devset.command(name="forumsync")
    async def devset_forum_sync(
        self,
        ctx: commands.Context,
        enabled: bool,
    ):
        """Enable or disable Discord Forum → GitHub Issue sync."""

        old_value = await self.config.guild(ctx.guild).forum_sync_enabled()
        await self.config.guild(ctx.guild).forum_sync_enabled.set(enabled)

        await self._audit(
            ctx,
            "Changed Forum/GitHub sync",
            str(old_value),
            str(enabled),
        )
        await ctx.send(
            "✅ Forum sync: " + ("**enabled**" if enabled else "**disabled**")
        )

    @devset.command(name="milestone")
    async def devset_milestone(
        self,
        ctx: commands.Context,
        *,
        title: str,
    ):
        """Set the milestone used in morning development goals."""

        title = title.strip()

        if title.casefold() in {"none", "off", "clear"}:
            old_value = await self.config.guild(ctx.guild).milestone_title()
            await self.config.guild(ctx.guild).milestone_title.set(None)
            await self._audit(
                ctx,
                "Cleared development milestone",
                old_value or "none",
                "none",
            )
            await ctx.send("✅ Milestone filter cleared.")
            return

        old_value = await self.config.guild(ctx.guild).milestone_title()
        await self.config.guild(ctx.guild).milestone_title.set(title)

        await self._audit(
            ctx,
            "Changed development milestone",
            old_value or "none",
            title,
        )
        await ctx.send(f"✅ Development milestone: **{title}**")

    @devset.command(name="reviewlabel")
    async def devset_review_label(
        self,
        ctx: commands.Context,
        *,
        label: str,
    ):
        """Set the label that creates a code-review thread."""

        label = label.strip()
        if not label:
            await ctx.send("❌ Label không được để trống.")
            return

        old_value = await self.config.guild(ctx.guild).review_label()
        await self.config.guild(ctx.guild).review_label.set(label)

        await self._audit(
            ctx,
            "Changed PR review label",
            old_value,
            label,
        )
        await ctx.send(f"✅ Review label: **{label}**")

    @devset.command(name="schedule")
    async def devset_schedule(
        self,
        ctx: commands.Context,
        hour: int,
        minute: int = 5,
    ):
        """Set the morning DEVELOPMENT GOALS time in the configured timezone."""

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            await ctx.send("❌ Giờ hoặc phút không hợp lệ.")
            return

        guild_conf = self.config.guild(ctx.guild)
        old_hour = await guild_conf.daily_hour()
        old_minute = await guild_conf.daily_minute()

        await guild_conf.daily_hour.set(hour)
        await guild_conf.daily_minute.set(minute)

        await self._audit(
            ctx,
            "Changed development-goals schedule",
            f"{old_hour:02d}:{old_minute:02d}",
            f"{hour:02d}:{minute:02d}",
        )
        tz_name = await guild_conf.timezone()
        await ctx.send(f"✅ DEVELOPMENT GOALS: **{hour:02d}:{minute:02d} {tz_name}**")

    @devset.command(name="timezone")
    async def devset_timezone(self, ctx: commands.Context, timezone_name: str):
        """Set the DEVELOPMENT GOALS timezone, e.g. Asia/Bangkok."""

        timezone_name = timezone_name.strip()
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            await ctx.send("❌ Timezone không hợp lệ. Ví dụ: `Asia/Bangkok`.")
            return

        old_value = await self.config.guild(ctx.guild).timezone()
        await self.config.guild(ctx.guild).timezone.set(timezone_name)
        await self._audit(
            ctx,
            "Changed DevelopmentOps timezone",
            old_value,
            timezone_name,
        )
        await ctx.send(f"✅ DevelopmentOps timezone: **{timezone_name}**")

    @devset.command(name="status")
    async def devset_status(self, ctx: commands.Context):
        """Show configuration without revealing any secret."""

        data = await self.config.guild(ctx.guild).all()

        def channel_text(key: str) -> str:
            channel_id = data.get(key)
            channel = ctx.guild.get_channel(channel_id) if channel_id else None

            if isinstance(channel, discord.TextChannel):
                return channel.mention
            if isinstance(channel, discord.ForumChannel):
                return f"#{channel.name}"
            return "Not configured"

        receiver_state = (
            f"Listening on `{self.web_host}:{self.web_port}/github`"
            if self.web_site is not None
            else f"Not listening: `{self.web_start_error or 'starting'}`"
        )

        await ctx.send(
            "**🧰 DEVELOPMENTOPS CONFIGURATION**\n\n"
            f"Repositories: `{', '.join(data['repositories']) or 'none'}`\n"
            f"Primary repository: `{data['primary_repo'] or 'none'}`\n"
            f"GitHub feed: {channel_text('github_feed_channel_id')}\n"
            f"Release: {channel_text('release_channel_id')}\n"
            f"Code review: {channel_text('code_review_channel_id')}\n"
            f"Bugs Forum: {channel_text('bugs_forum_channel_id')}\n"
            f"Daily goals: {channel_text('daily_goals_channel_id')}\n"
            f"Schedule: `{data['daily_hour']:02d}:{data['daily_minute']:02d} {data.get('timezone', 'Asia/Bangkok')}`\n"
            f"Milestone: `{data['milestone_title'] or 'none'}`\n"
            f"Review label: `{data['review_label']}`\n"
            f"Forum sync: `{data['forum_sync_enabled']}`\n"
            f"Webhook secret present: `{bool(self.webhook_secret)}`\n"
            f"GitHub token present: `{bool(self.github_token)}`\n"
            f"Receiver: {receiver_state}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @devset.command(name="postgoals")
    async def devset_post_goals(self, ctx: commands.Context):
        """Post DEVELOPMENT GOALS immediately."""

        await self._post_development_goals(ctx.guild, force=True)
        await ctx.tick()

    @devset.command(name="refreshpr")
    async def devset_refresh_pr(
        self,
        ctx: commands.Context,
        number: int,
        repository: Optional[str] = None,
    ):
        """Create or refresh a PR review thread."""

        repository = repository or await self.config.guild(ctx.guild).primary_repo()
        if not repository:
            await ctx.send("❌ Chưa cấu hình primary repository.")
            return

        try:
            await self._ensure_review_thread(
                ctx.guild,
                repository,
                number,
                announce_refresh=True,
            )
        except Exception as exc:
            await self._report_error(
                ctx.guild,
                operation=f"Refresh PR review thread {repository}#{number}",
                error=exc,
                ctx=ctx,
            )
            return

        await ctx.tick()

    # ------------------------------------------------------------------
    # Embedded GitHub webhook receiver
    # ------------------------------------------------------------------

    async def _start_webserver(self):
        await self.bot.wait_until_ready()

        if not self.settings.receiver_enabled:
            self.web_start_error = "; ".join(self.settings.warnings) or "receiver disabled"
            log.warning(self.web_start_error)
            return

        if not self.webhook_secret:
            self.web_start_error = (
                "DEVELOPMENTOPS_WEBHOOK_SECRET is not set; receiver disabled"
            )
            log.warning(self.web_start_error)
            return

        app = web.Application(client_max_size=2 * 1024 * 1024)
        app.router.add_post("/github", self._github_webhook)
        app.router.add_get("/healthz", self._healthcheck)

        try:
            self.web_runner = web.AppRunner(
                app,
                access_log=None,
                handle_signals=False,
            )
            await self.web_runner.setup()

            self.web_site = web.TCPSite(
                self.web_runner,
                host=self.web_host,
                port=self.web_port,
            )
            await self.web_site.start()

            log.info(
                "DevelopmentOps receiver listening on %s:%s",
                self.web_host,
                self.web_port,
            )
        except Exception as exc:
            self.web_start_error = f"{exc.__class__.__name__}: {exc}"
            self.web_site = None
            log.exception("Unable to start DevelopmentOps receiver", exc_info=exc)

    async def _healthcheck(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "service": "DevelopmentOps",
                "receiver": self.web_site is not None,
            }
        )

    async def _github_webhook(self, request: web.Request) -> web.Response:
        raw_body = await request.read()
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not verify_github_signature(self.webhook_secret, raw_body, signature):
            return web.json_response(
                {"ok": False, "error": "invalid signature"},
                status=403,
            )

        delivery_id = request.headers.get("X-GitHub-Delivery", "")
        event = request.headers.get("X-GitHub-Event", "")

        if delivery_id and self._delivery_seen(delivery_id):
            return web.json_response(
                {"ok": True, "duplicate": True},
                status=202,
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return web.json_response(
                {"ok": False, "error": "invalid JSON"},
                status=400,
            )

        try:
            self.webhook_queue.put_nowait(
                {
                    "event": event,
                    "payload": payload,
                    "delivery_id": delivery_id,
                }
            )
        except asyncio.QueueFull:
            return web.json_response(
                {"ok": False, "error": "webhook queue full"},
                status=503,
            )

        return web.json_response({"ok": True}, status=202)

    def _delivery_seen(self, delivery_id: str) -> bool:
        return self.delivery_dedupe.seen(delivery_id)

    async def _webhook_worker(self):
        await self.bot.wait_until_ready()
        while True:
            item = await self.webhook_queue.get()
            try:
                await self._dispatch_webhook(
                    event=str(item.get("event") or ""),
                    payload=item.get("payload") or {},
                    delivery_id=str(item.get("delivery_id") or ""),
                )
            except Exception as exc:
                log.error(
                    "DevelopmentOps webhook dispatch failed: %s",
                    exc.__class__.__name__,
                    exc_info=exc,
                )
            finally:
                self.webhook_queue.task_done()

    async def _dispatch_webhook(
        self,
        *,
        event: str,
        payload: Dict[str, Any],
        delivery_id: str,
    ):
        repository = str(
            (payload.get("repository") or {}).get("full_name") or ""
        )

        if not repository:
            return

        guilds = await self._guilds_for_repository(repository)

        for guild in guilds:
            try:
                await self._handle_event_for_guild(
                    guild=guild,
                    repository=repository,
                    event=event,
                    payload=payload,
                )
            except Exception as exc:
                await self._report_error(
                    guild,
                    operation=(
                        f"Process GitHub webhook {event} "
                        f"for {repository} delivery {delivery_id or 'unknown'}"
                    ),
                    error=exc,
                )

    async def _guilds_for_repository(
        self,
        repository: str,
    ) -> List[discord.Guild]:
        result = []
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            repositories = {
                repo.casefold()
                for repo in data.get("repositories", [])
            }

            if repository.casefold() not in repositories:
                continue

            guild = self.bot.get_guild(int(guild_id))
            if guild is not None:
                result.append(guild)

        return result

    async def _handle_event_for_guild(
        self,
        *,
        guild: discord.Guild,
        repository: str,
        event: str,
        payload: Dict[str, Any],
    ):
        if event == "ping":
            await self._send_simple_feed(
                guild,
                "🟢 GITHUB WEBHOOK CONNECTED",
                f"Repository: **{repository}**",
            )
            return

        if event == "push":
            await self._handle_push(guild, repository, payload)
            return

        if event == "pull_request":
            await self._handle_pull_request(guild, repository, payload)
            return

        if event == "issues":
            await self._handle_issue(guild, repository, payload)
            return

        if event == "workflow_run":
            await self._handle_workflow_run(guild, repository, payload)
            return

        if event == "create":
            await self._handle_create(guild, repository, payload)
            return

        if event == "release":
            await self._handle_release(guild, repository, payload)
            return

        if event == "deployment_status":
            await self._handle_deployment_status(guild, repository, payload)
            return

        if event in {
            "pull_request_review",
            "pull_request_review_comment",
            "check_suite",
        }:
            await self._handle_review_related_event(
                guild,
                repository,
                event,
                payload,
            )

    # ------------------------------------------------------------------
    # GitHub feed and release routing
    # ------------------------------------------------------------------

    async def _handle_push(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        if payload.get("deleted"):
            return

        ref = str(payload.get("ref") or "")
        branch = ref.removeprefix("refs/heads/")
        commits = payload.get("commits") or []
        pusher = (payload.get("pusher") or {}).get("name") or "unknown"
        compare_url = payload.get("compare")
        head_commit = payload.get("head_commit") or {}

        lines = [
            f"Repository: **{repository}**",
            f"Branch: `{branch}`",
            f"Pusher: **{pusher}**",
            f"Commits: `{len(commits)}`",
        ]

        if head_commit:
            message = self._one_line(head_commit.get("message") or "No message")
            sha = str(head_commit.get("id") or "")[:7]
            lines.append(f"Head: `{sha}` {message}")

        if commits:
            lines.extend(["", "**Recent commits**"])
            for commit in commits[:5]:
                sha = str(commit.get("id") or "")[:7]
                message = self._one_line(commit.get("message") or "No message")
                author = (
                    (commit.get("author") or {}).get("username")
                    or (commit.get("author") or {}).get("name")
                    or "unknown"
                )
                lines.append(f"• `{sha}` {message} — **{author}**")

            if len(commits) > 5:
                lines.append(f"• …and `{len(commits) - 5}` more")

        await self._send_embed(
            guild,
            "github_feed_channel_id",
            title="🟪 PUSH",
            description="\n".join(lines),
            url=compare_url,
            colour=discord.Colour.purple(),
        )

    async def _handle_pull_request(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        action = str(payload.get("action") or "")
        pr = payload.get("pull_request") or {}
        number = int(pr.get("number") or payload.get("number") or 0)

        allowed_feed_actions = {
            "opened",
            "reopened",
            "closed",
            "ready_for_review",
            "converted_to_draft",
        }

        if action in allowed_feed_actions:
            if action == "closed" and pr.get("merged"):
                heading = "🟣 PULL REQUEST MERGED"
                status = "Merged"
                colour = discord.Colour.green()
            elif action == "closed":
                heading = "⚫ PULL REQUEST CLOSED"
                status = "Closed without merge"
                colour = discord.Colour.dark_grey()
            elif action == "opened":
                heading = "🟣 PULL REQUEST OPENED"
                status = "Awaiting review"
                colour = discord.Colour.purple()
            elif action == "reopened":
                heading = "🟣 PULL REQUEST REOPENED"
                status = "Awaiting review"
                colour = discord.Colour.purple()
            elif action == "ready_for_review":
                heading = "🟣 PULL REQUEST READY FOR REVIEW"
                status = "Awaiting review"
                colour = discord.Colour.purple()
            else:
                heading = "📝 PULL REQUEST CONVERTED TO DRAFT"
                status = "Draft"
                colour = discord.Colour.orange()

            author = (pr.get("user") or {}).get("login") or "unknown"
            head = ((pr.get("head") or {}).get("ref")) or "unknown"
            base = ((pr.get("base") or {}).get("ref")) or "unknown"
            additions = int(pr.get("additions") or 0)
            deletions = int(pr.get("deletions") or 0)
            changed_files = int(pr.get("changed_files") or 0)

            description = (
                f"**{repository} #{number}**\n"
                f"{pr.get('title') or 'Untitled PR'}\n\n"
                f"Author: **{author}**\n"
                f"Branch: `{head}` → `{base}`\n"
                f"Changed: `+{additions} / -{deletions}` "
                f"across `{changed_files}` file(s)\n"
                f"Status: **{status}**"
            )

            await self._send_embed(
                guild,
                "github_feed_channel_id",
                title=heading,
                description=description,
                url=pr.get("html_url"),
                colour=colour,
            )

        review_label = (
            await self.config.guild(guild).review_label()
        ).casefold()
        labels = {
            str(label.get("name") or "").casefold()
            for label in pr.get("labels") or []
        }

        should_create_review = (
            (
                action == "labeled"
                and str((payload.get("label") or {}).get("name") or "").casefold()
                == review_label
            )
            or (
                action in {"opened", "reopened", "ready_for_review", "synchronize"}
                and review_label in labels
            )
        )

        if should_create_review and number:
            await self._ensure_review_thread(guild, repository, number)

        if action == "closed" and number:
            await self._close_review_thread(
                guild,
                repository,
                number,
                merged=bool(pr.get("merged")),
            )

        if action in {"synchronize", "review_requested"} and number:
            await self._refresh_existing_review_thread(
                guild,
                repository,
                number,
            )

    async def _handle_issue(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        action = str(payload.get("action") or "")
        issue = payload.get("issue") or {}
        number = int(issue.get("number") or 0)

        if action in {"opened", "reopened", "closed"}:
            if action == "opened":
                heading = "🟢 ISSUE OPENED"
                colour = discord.Colour.green()
            elif action == "reopened":
                heading = "🟡 ISSUE REOPENED"
                colour = discord.Colour.orange()
            else:
                heading = "⚫ ISSUE CLOSED"
                colour = discord.Colour.dark_grey()

            labels = ", ".join(
                label.get("name", "")
                for label in issue.get("labels") or []
                if label.get("name")
            ) or "none"

            await self._send_embed(
                guild,
                "github_feed_channel_id",
                title=heading,
                description=(
                    f"**{repository} #{number}**\n"
                    f"{issue.get('title') or 'Untitled issue'}\n\n"
                    f"Author: **{(issue.get('user') or {}).get('login') or 'unknown'}**\n"
                    f"Labels: `{labels}`"
                ),
                url=issue.get("html_url"),
                colour=colour,
            )

        if action in {"closed", "reopened"} and number:
            await self._sync_issue_state_to_forum(
                guild,
                repository,
                number,
                resolved=(action == "closed"),
            )

    async def _handle_workflow_run(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        if payload.get("action") != "completed":
            return

        run = payload.get("workflow_run") or {}
        conclusion = str(run.get("conclusion") or "unknown")
        success = conclusion == "success"

        await self._send_embed(
            guild,
            "github_feed_channel_id",
            title=(
                "✅ GITHUB ACTIONS SUCCEEDED"
                if success
                else "❌ GITHUB ACTIONS FAILED"
            ),
            description=(
                f"Repository: **{repository}**\n"
                f"Workflow: **{run.get('name') or 'Unknown workflow'}**\n"
                f"Branch: `{run.get('head_branch') or 'unknown'}`\n"
                f"Conclusion: **{conclusion}**\n"
                f"Run: `#{run.get('run_number') or '?'} / attempt "
                f"{run.get('run_attempt') or 1}`"
            ),
            url=run.get("html_url"),
            colour=(
                discord.Colour.green()
                if success
                else discord.Colour.red()
            ),
        )

        pull_requests = run.get("pull_requests") or []
        for pr in pull_requests[:5]:
            number = int(pr.get("number") or 0)
            if number:
                await self._refresh_existing_review_thread(
                    guild,
                    repository,
                    number,
                )

    async def _handle_create(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        if payload.get("ref_type") != "tag":
            return

        tag = str(payload.get("ref") or "")
        sender = (payload.get("sender") or {}).get("login") or "unknown"
        url = f"https://github.com/{repository}/releases/tag/{quote(tag)}"

        description = (
            f"Repository: **{repository}**\n"
            f"Tag: `{tag}`\n"
            f"Created by: **{sender}**"
        )

        await self._send_embed(
            guild,
            "github_feed_channel_id",
            title="🏷 TAG CREATED",
            description=description,
            url=url,
            colour=discord.Colour.blurple(),
        )

        if tag.startswith("v"):
            await self._send_embed(
                guild,
                "release_channel_id",
                title="🏷 VERSION TAG CREATED",
                description=description,
                url=url,
                colour=discord.Colour.blurple(),
            )

    async def _handle_release(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        if payload.get("action") not in {"published", "released"}:
            return

        release = payload.get("release") or {}
        tag = release.get("tag_name") or "unknown"
        body = str(release.get("body") or "No changelog provided.").strip()
        body = body[:3000]

        await self._send_embed(
            guild,
            "release_channel_id",
            title=f"🚀 RELEASE PUBLISHED — {tag}",
            description=(
                f"Repository: **{repository}**\n"
                f"Name: **{release.get('name') or tag}**\n"
                f"Author: **{(release.get('author') or {}).get('login') or 'unknown'}**\n\n"
                f"**Changelog**\n{body}"
            ),
            url=release.get("html_url"),
            colour=discord.Colour.green(),
        )

    async def _handle_deployment_status(
        self,
        guild: discord.Guild,
        repository: str,
        payload: Dict[str, Any],
    ):
        status = payload.get("deployment_status") or {}
        deployment = payload.get("deployment") or {}

        state = str(status.get("state") or "")
        environment = str(
            deployment.get("environment")
            or status.get("environment")
            or ""
        )

        if state != "success":
            return

        if environment.casefold() not in {
            "production",
            "prod",
            "live",
        }:
            return

        await self._send_embed(
            guild,
            "release_channel_id",
            title="🌐 PRODUCTION DEPLOYMENT SUCCEEDED",
            description=(
                f"Repository: **{repository}**\n"
                f"Environment: **{environment}**\n"
                f"Ref: `{deployment.get('ref') or 'unknown'}`\n"
                f"SHA: `{str(deployment.get('sha') or '')[:7]}`\n"
                f"Description: {status.get('description') or 'Deployment succeeded.'}"
            ),
            url=status.get("environment_url") or status.get("target_url"),
            colour=discord.Colour.green(),
        )

    async def _send_simple_feed(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
    ):
        await self._send_embed(
            guild,
            "github_feed_channel_id",
            title=title,
            description=description,
            colour=discord.Colour.green(),
        )

    async def _send_embed(
        self,
        guild: discord.Guild,
        config_key: str,
        *,
        title: str,
        description: str,
        colour: discord.Colour,
        url: Optional[str] = None,
    ):
        channel_id = await getattr(self.config.guild(guild), config_key)()
        channel = guild.get_channel(channel_id) if channel_id else None

        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=title[:256],
            description=description[:4096],
            colour=colour,
            timestamp=datetime.now(timezone.utc),
            url=url if url and url.startswith("https://") else None,
        )
        embed.set_footer(text="DevelopmentOps")

        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # ------------------------------------------------------------------
    # PR code-review threads
    # ------------------------------------------------------------------

    async def _handle_review_related_event(
        self,
        guild: discord.Guild,
        repository: str,
        event: str,
        payload: Dict[str, Any],
    ):
        pr = payload.get("pull_request")

        if not pr and event == "check_suite":
            pull_requests = (
                (payload.get("check_suite") or {}).get("pull_requests") or []
            )
        else:
            pull_requests = [pr] if pr else []

        for pr_item in pull_requests[:5]:
            number = int(pr_item.get("number") or 0)
            if number:
                await self._refresh_existing_review_thread(
                    guild,
                    repository,
                    number,
                )

    async def _ensure_review_thread(
        self,
        guild: discord.Guild,
        repository: str,
        number: int,
        *,
        announce_refresh: bool = False,
    ):
        guild_conf = self.config.guild(guild)
        mapping_key = self._repo_number_key(repository, number)
        pr_threads = await guild_conf.pr_threads()
        thread_id = pr_threads.get(mapping_key)
        thread = await self._resolve_thread(guild, int(thread_id)) if thread_id else None

        snapshot = await self._build_pr_snapshot(repository, number)
        pr = snapshot["pr"]

        if thread is None:
            channel_id = await guild_conf.code_review_channel_id()
            channel = guild.get_channel(channel_id) if channel_id else None

            if not isinstance(channel, discord.TextChannel):
                return

            thread_name = f"PR #{number} — {pr.get('title') or 'Untitled PR'}"[:100]
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=10080,
                reason=f"Review-needed PR {repository}#{number}",
            )

            async with guild_conf.pr_threads() as stored:
                stored[mapping_key] = thread.id

        if thread.archived:
            with contextlib.suppress(discord.HTTPException):
                await thread.edit(archived=False)

        await thread.send(
            self._format_pr_snapshot(snapshot),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if announce_refresh:
            await thread.send(
                "🔄 Review snapshot refreshed manually.",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def _refresh_existing_review_thread(
        self,
        guild: discord.Guild,
        repository: str,
        number: int,
    ):
        mapping_key = self._repo_number_key(repository, number)
        thread_id = (
            await self.config.guild(guild).pr_threads()
        ).get(mapping_key)

        if not thread_id:
            return

        thread = await self._resolve_thread(guild, int(thread_id))
        if thread is None:
            return

        try:
            snapshot = await self._build_pr_snapshot(repository, number)
            await thread.send(
                self._format_pr_snapshot(snapshot),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except GitHubAPIError as exc:
            await thread.send(
                f"⚠ Unable to refresh review snapshot: GitHub API `{exc.status}`.",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def _close_review_thread(
        self,
        guild: discord.Guild,
        repository: str,
        number: int,
        *,
        merged: bool,
    ):
        mapping_key = self._repo_number_key(repository, number)
        thread_id = (
            await self.config.guild(guild).pr_threads()
        ).get(mapping_key)

        if not thread_id:
            return

        thread = await self._resolve_thread(guild, int(thread_id))
        if thread is None:
            return

        with contextlib.suppress(discord.HTTPException):
            await thread.send(
                "✅ PR merged; review thread archived."
                if merged
                else "⚫ PR closed without merge; review thread archived.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await thread.edit(archived=True, locked=False)

    async def _build_pr_snapshot(
        self,
        repository: str,
        number: int,
    ) -> Dict[str, Any]:
        pr = await self._github_request(
            "GET",
            f"/repos/{repository}/pulls/{number}",
        )

        files = await self._github_request(
            "GET",
            f"/repos/{repository}/pulls/{number}/files?per_page=100",
        )

        head_sha = str((pr.get("head") or {}).get("sha") or "")
        checks = []

        if head_sha:
            check_data = await self._github_request(
                "GET",
                f"/repos/{repository}/commits/{head_sha}/check-runs?per_page=100",
                accept="application/vnd.github+json",
                tolerate_statuses={403, 404},
            )

            if isinstance(check_data, dict):
                checks = check_data.get("check_runs") or []

        unresolved = await self._github_unresolved_review_threads(
            repository,
            number,
        )

        return {
            "repository": repository,
            "number": number,
            "pr": pr,
            "files": files if isinstance(files, list) else [],
            "checks": checks,
            "unresolved": unresolved,
        }

    async def _github_unresolved_review_threads(
        self,
        repository: str,
        number: int,
    ) -> List[Dict[str, Any]]:
        if not self.github_token:
            return []

        owner, name = repository.split("/", 1)
        query = """
        query($owner:String!, $name:String!, $number:Int!) {
          repository(owner:$owner, name:$name) {
            pullRequest(number:$number) {
              reviewThreads(first:100) {
                nodes {
                  isResolved
                  comments(first:20) {
                    nodes {
                      author { login }
                      body
                      url
                      path
                      line
                    }
                  }
                }
              }
            }
          }
        }
        """

        data = await self._github_graphql(
            query,
            {
                "owner": owner,
                "name": name,
                "number": number,
            },
        )

        nodes = (
            (((data.get("repository") or {}).get("pullRequest") or {})
             .get("reviewThreads") or {})
            .get("nodes")
            or []
        )

        result = []

        for node in nodes:
            if node.get("isResolved"):
                continue

            comments = (
                (node.get("comments") or {}).get("nodes") or []
            )
            if not comments:
                continue

            result.append(comments[-1])

        return result

    def _format_pr_snapshot(self, snapshot: Dict[str, Any]) -> str:
        repository = snapshot["repository"]
        number = snapshot["number"]
        pr = snapshot["pr"]
        files = snapshot["files"]
        checks = snapshot["checks"]
        unresolved = snapshot["unresolved"]

        additions = int(pr.get("additions") or 0)
        deletions = int(pr.get("deletions") or 0)
        changed_files = int(pr.get("changed_files") or len(files))
        draft = bool(pr.get("draft"))
        mergeable = pr.get("mergeable")
        body = str(pr.get("body") or "No PR description.").strip()
        body = body[:1200]

        passed = sum(
            1
            for check in checks
            if check.get("conclusion") in {"success", "neutral", "skipped"}
        )
        failed = sum(
            1
            for check in checks
            if check.get("conclusion") in {
                "failure",
                "timed_out",
                "cancelled",
                "action_required",
            }
        )
        pending = max(0, len(checks) - passed - failed)

        lines = [
            f"## PR #{number} — {pr.get('title') or 'Untitled PR'}",
            f"Repository: **{repository}**",
            f"Author: **{(pr.get('user') or {}).get('login') or 'unknown'}**",
            f"Branch: `{(pr.get('head') or {}).get('ref') or 'unknown'}` → "
            f"`{(pr.get('base') or {}).get('ref') or 'unknown'}`",
            f"Changed: `+{additions} / -{deletions}` across `{changed_files}` file(s)",
            f"State: **{'Draft' if draft else 'Ready for review'}**",
            f"Mergeable: `{mergeable}`",
            "",
            "### Mục tiêu PR",
            body,
            "",
            "### File thay đổi",
        ]

        if files:
            for file in files[:20]:
                lines.append(
                    f"• `{file.get('filename')}` "
                    f"(`+{file.get('additions', 0)} / -{file.get('deletions', 0)}`)"
                )

            if len(files) > 20:
                lines.append(f"• …and `{len(files) - 20}` more")
        else:
            lines.append("• File list unavailable.")

        lines.extend(
            [
                "",
                "### Checklist",
                "- [ ] Scope and acceptance criteria are clear",
                "- [ ] Tests are added or updated",
                "- [ ] CI is green",
                "- [ ] No token, secret, or generated artifact is committed",
                "- [ ] UI changes include screenshots when relevant",
                "",
                "### Test status",
                f"Passed: `{passed}` • Failed: `{failed}` • Pending: `{pending}`",
                "",
                "### Unresolved review comments",
            ]
        )

        if unresolved:
            for comment in unresolved[:15]:
                author = (comment.get("author") or {}).get("login") or "unknown"
                path = comment.get("path") or "general"
                line = comment.get("line")
                location = f"{path}:{line}" if line else path
                body = self._one_line(comment.get("body") or "No text")[:300]
                url = comment.get("url") or ""
                lines.append(
                    f"• **{author}** on `{location}` — {body}"
                    + (f" — <{url}>" if url else "")
                )
        elif not self.github_token:
            lines.append(
                "• Unresolved-thread data requires "
                "`DEVELOPMENTOPS_GITHUB_TOKEN`."
            )
        else:
            lines.append("• None.")

        html_url = pr.get("html_url")
        if html_url:
            lines.extend(["", f"PR: <{html_url}>"])

        text = "\n".join(lines)
        return text[:1900]

    # ------------------------------------------------------------------
    # Forum ↔ GitHub Issue synchronization
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        guild = thread.guild
        forum_id = await self.config.guild(guild).bugs_forum_channel_id()

        if thread.parent_id != forum_id:
            return

        if not await self.config.guild(guild).forum_sync_enabled():
            return

        if self.bot.user is not None and thread.owner_id == self.bot.user.id:
            return

        primary_repo = await self.config.guild(guild).primary_repo()
        if not primary_repo:
            return

        if not self.github_token:
            await self._send_thread_notice(
                thread,
                "⚠ GitHub issue was not created because "
                "`DEVELOPMENTOPS_GITHUB_TOKEN` is unavailable.",
            )
            return

        await asyncio.sleep(1)

        try:
            starter = await self._fetch_thread_starter(thread)
            content = starter.content if starter is not None else ""
            attachments = (
                [attachment.url for attachment in starter.attachments]
                if starter is not None
                else []
            )
            labels = self._thread_managed_tags(thread)

            body_lines = [
                content or "_No description supplied._",
                "",
                "---",
                f"Discord Forum: https://discord.com/channels/{guild.id}/{thread.id}",
                f"Created by Discord user ID: {thread.owner_id}",
            ]

            if attachments:
                body_lines.extend(["", "Attachments"])
                body_lines.extend(f"- {url}" for url in attachments)

            issue = await self._github_request(
                "POST",
                f"/repos/{primary_repo}/issues",
                json_body={
                    "title": thread.name[:256],
                    "body": "\n".join(body_lines),
                    "labels": [
                        label
                        for label in labels
                        if label != "resolved"
                    ],
                },
            )

            number = int(issue["number"])
            await self._store_forum_mapping(
                guild,
                thread.id,
                primary_repo,
                number,
            )

            await self._send_thread_notice(
                thread,
                f"✅ GitHub issue created: "
                f"**{primary_repo} #{number}**\n<{issue.get('html_url')}>",
            )

        except Exception as exc:
            await self._report_error(
                guild,
                operation=f"Create GitHub issue from Forum post {thread.id}",
                error=exc,
            )

    @commands.Cog.listener()
    async def on_thread_update(
        self,
        before: discord.Thread,
        after: discord.Thread,
    ):
        if before.applied_tags == after.applied_tags:
            return

        guild_conf = self.config.guild(after.guild)
        mapping = (await guild_conf.forum_to_issue()).get(str(after.id))

        if not mapping or not await guild_conf.forum_sync_enabled():
            return

        if not self.github_token:
            return

        repository = mapping["repo"]
        number = int(mapping["number"])

        try:
            issue = await self._github_request(
                "GET",
                f"/repos/{repository}/issues/{number}",
            )

            existing = {
                label.get("name")
                for label in issue.get("labels") or []
                if label.get("name")
            }
            preserved = {
                label
                for label in existing
                if label.casefold() not in MANAGED_FORUM_LABELS
            }
            managed = set(self._thread_managed_tags(after))

            await self._github_request(
                "PATCH",
                f"/repos/{repository}/issues/{number}",
                json_body={
                    "labels": sorted(preserved | managed),
                },
            )

        except Exception as exc:
            await self._report_error(
                after.guild,
                operation=(
                    f"Sync Forum tags to GitHub issue "
                    f"{repository}#{number}"
                ),
                error=exc,
            )

    async def _sync_issue_state_to_forum(
        self,
        guild: discord.Guild,
        repository: str,
        number: int,
        *,
        resolved: bool,
    ):
        key = self._repo_number_key(repository, number)
        thread_id = (
            await self.config.guild(guild).issue_to_forum()
        ).get(key)

        if not thread_id:
            return

        thread = await self._resolve_thread(guild, int(thread_id))
        if thread is None:
            return

        forum = thread.parent
        if not isinstance(forum, discord.ForumChannel):
            return

        resolved_tag = next(
            (
                tag
                for tag in forum.available_tags
                if tag.name.casefold() == "resolved"
            ),
            None,
        )
        blocked_tag_ids = {
            tag.id
            for tag in forum.available_tags
            if tag.name.casefold() == "blocked"
        }

        tags = [
            tag
            for tag in thread.applied_tags
            if tag.id not in blocked_tag_ids
            and tag.name.casefold() != "resolved"
        ]

        if resolved and resolved_tag is not None:
            tags.append(resolved_tag)

        try:
            await thread.edit(
                applied_tags=tags,
                archived=False if not resolved else thread.archived,
                reason=(
                    f"GitHub issue {repository}#{number} "
                    f"{'closed' if resolved else 'reopened'}"
                ),
            )
            await self._send_thread_notice(
                thread,
                (
                    f"✅ GitHub issue **{repository} #{number}** was closed."
                    if resolved
                    else f"🟡 GitHub issue **{repository} #{number}** was reopened."
                ),
            )
        except discord.HTTPException as exc:
            await self._report_error(
                guild,
                operation=(
                    f"Update Forum state for GitHub issue "
                    f"{repository}#{number}"
                ),
                error=exc,
            )

    async def _fetch_thread_starter(
        self,
        thread: discord.Thread,
    ) -> Optional[discord.Message]:
        with contextlib.suppress(discord.HTTPException):
            return await thread.fetch_message(thread.id)

        with contextlib.suppress(discord.HTTPException):
            async for message in thread.history(limit=1, oldest_first=True):
                return message

        return None

    def _thread_managed_tags(
        self,
        thread: discord.Thread,
    ) -> List[str]:
        return sorted(
            {
                tag.name.casefold()
                for tag in thread.applied_tags
                if tag.name.casefold() in MANAGED_FORUM_LABELS
            }
        )

    async def _store_forum_mapping(
        self,
        guild: discord.Guild,
        thread_id: int,
        repository: str,
        number: int,
    ):
        guild_conf = self.config.guild(guild)
        key = self._repo_number_key(repository, number)

        async with guild_conf.forum_to_issue() as mapping:
            mapping[str(thread_id)] = {
                "repo": repository,
                "number": number,
            }

        async with guild_conf.issue_to_forum() as mapping:
            mapping[key] = thread_id

    async def _send_thread_notice(
        self,
        thread: discord.Thread,
        content: str,
    ):
        with contextlib.suppress(discord.HTTPException):
            await thread.send(
                content,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    # ------------------------------------------------------------------
    # Morning DEVELOPMENT GOALS
    # ------------------------------------------------------------------

    @tasks.loop(seconds=60)
    async def daily_loop(self):
        all_guilds = await self.config.all_guilds()

        for guild_id, data in all_guilds.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            now = datetime.now(self._guild_timezone(data))

            today_key = now.strftime(DAY_FMT)

            if data.get("last_daily_post") == today_key:
                continue

            if not self._within_schedule_window(
                now,
                int(data.get("daily_hour", 7)),
                int(data.get("daily_minute", 5)),
                window_minutes=180,
            ):
                continue

            try:
                await self._post_development_goals(guild)
            except Exception as exc:
                await self._report_error(
                    guild,
                    operation="Post morning DEVELOPMENT GOALS",
                    error=exc,
                )

    @daily_loop.before_loop
    async def before_daily_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _guild_timezone(data: Dict[str, Any]):
        try:
            return ZoneInfo(str(data.get("timezone") or "Asia/Bangkok"))
        except ZoneInfoNotFoundError:
            return ZoneInfo("Asia/Bangkok")

    async def _post_development_goals(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ):
        guild_conf = self.config.guild(guild)
        channel_id = await guild_conf.daily_goals_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        repository = await guild_conf.primary_repo()
        data = await guild_conf.all()
        guild_tz = self._guild_timezone(data)

        if not isinstance(channel, discord.TextChannel) or not repository:
            return

        labels = await guild_conf.daily_labels()
        issue_map: Dict[int, Dict[str, Any]] = {}
        issue_source: Dict[int, str] = {}

        for label in labels:
            items = await self._github_request(
                "GET",
                (
                    f"/repos/{repository}/issues"
                    f"?state=open&labels={quote(label)}&per_page=100"
                ),
            )

            for item in items if isinstance(items, list) else []:
                if "pull_request" in item:
                    continue

                number = int(item["number"])
                issue_map[number] = item
                issue_source[number] = label

        review_label = await guild_conf.review_label()
        review_items = await self._github_request(
            "GET",
            (
                f"/repos/{repository}/issues"
                f"?state=open&labels={quote(review_label)}&per_page=100"
            ),
        )
        review_prs = [
            item
            for item in review_items
            if isinstance(item, dict) and "pull_request" in item
        ][:10]

        failing_data = await self._github_request(
            "GET",
            f"/repos/{repository}/actions/runs?status=failure&per_page=20",
            tolerate_statuses={403, 404},
        )
        failing_runs = (
            failing_data.get("workflow_runs", [])
            if isinstance(failing_data, dict)
            else []
        )

        milestone_title = await guild_conf.milestone_title()
        milestone_items = []

        if milestone_title:
            milestones = await self._github_request(
                "GET",
                f"/repos/{repository}/milestones?state=open&per_page=100",
            )
            milestone = next(
                (
                    item
                    for item in milestones
                    if str(item.get("title") or "").casefold()
                    == milestone_title.casefold()
                ),
                None,
            )

            if milestone:
                milestone_items = await self._github_request(
                    "GET",
                    (
                        f"/repos/{repository}/issues"
                        f"?state=open&milestone={milestone['number']}"
                        f"&sort=updated&direction=asc&per_page=100"
                    ),
                )
                milestone_items = [
                    item
                    for item in milestone_items
                    if "pull_request" not in item
                    and int(item["number"]) not in issue_map
                ][:5]

        lines = [
            f"💻 **DEVELOPMENT GOALS — {datetime.now(guild_tz).strftime('%d/%m/%Y')}**",
            "",
            f"Repository: **{repository}**",
            "",
        ]

        for number, issue in sorted(issue_map.items()):
            source = issue_source.get(number, "goal")
            prefix = "🗓" if source == "weekly-goal" else "[ ]"
            lines.append(
                f"{prefix} **#{number}** {issue.get('title') or 'Untitled issue'}"
            )

        for pr in review_prs:
            lines.append(
                f"[ ] Review PR **#{pr['number']}** "
                f"{pr.get('title') or 'Untitled PR'}"
            )

        seen_failure_keys = set()
        failure_lines = []

        for run in failing_runs:
            branch = run.get("head_branch") or "unknown"
            name = run.get("name") or "Unknown workflow"
            key = (name, branch)

            if key in seen_failure_keys:
                continue

            seen_failure_keys.add(key)
            failure_lines.append(
                f"⚠ CI failing: **{name}** on `{branch}`"
            )

            if len(failure_lines) >= 5:
                break

        lines.extend(failure_lines)

        if milestone_items:
            lines.extend(["", f"**Near milestone: {milestone_title}**"])
            for issue in milestone_items:
                lines.append(
                    f"[ ] **#{issue['number']}** "
                    f"{issue.get('title') or 'Untitled issue'}"
                )

        actionable_count = (
            len(issue_map)
            + len(review_prs)
            + len(failure_lines)
            + len(milestone_items)
        )

        if actionable_count == 0:
            lines.append("✅ No open development goals or failing workflows.")

        lines.extend(
            [
                "",
                "Source of truth: GitHub Issues, Pull Requests, Actions, and Milestones.",
            ]
        )

        await channel.send(
            "\n".join(lines)[:2000],
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if not force:
            await guild_conf.last_daily_post.set(
                datetime.now(guild_tz).strftime(DAY_FMT)
            )

    # ------------------------------------------------------------------
    # GitHub API helpers
    # ------------------------------------------------------------------

    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        if self.http_session is None or self.http_session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self.http_session = aiohttp.ClientSession(timeout=timeout)

        return self.http_session

    def _github_headers(
        self,
        *,
        accept: str = "application/vnd.github+json",
    ) -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "Red-DiscordBot-DevelopmentOps",
        }

        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        return headers

    async def _github_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        accept: str = "application/vnd.github+json",
        tolerate_statuses: Optional[set[int]] = None,
    ) -> Any:
        session = await self._ensure_http_session()
        url = path if path.startswith("https://") else API_BASE + path

        async with session.request(
            method,
            url,
            headers=self._github_headers(accept=accept),
            json=json_body,
        ) as response:
            text = await response.text()

            if tolerate_statuses and response.status in tolerate_statuses:
                return {}

            if response.status < 200 or response.status >= 300:
                message = text[:500].replace(self.github_token, "[REDACTED]") \
                    if self.github_token else text[:500]
                raise GitHubAPIError(response.status, message)

            if not text:
                return {}

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

    async def _github_graphql(
        self,
        query: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        session = await self._ensure_http_session()

        async with session.post(
            GRAPHQL_URL,
            headers=self._github_headers(),
            json={
                "query": query,
                "variables": variables,
            },
        ) as response:
            payload = await response.json(content_type=None)

            if response.status < 200 or response.status >= 300:
                raise GitHubAPIError(
                    response.status,
                    str(payload)[:500],
                )

            errors = payload.get("errors")
            if errors:
                raise GitHubAPIError(200, str(errors)[:500])

            return payload.get("data") or {}

    # ------------------------------------------------------------------
    # Shared helpers and BotOps integration
    # ------------------------------------------------------------------

    async def _resolve_thread(
        self,
        guild: discord.Guild,
        thread_id: int,
    ) -> Optional[discord.Thread]:
        thread = guild.get_thread(thread_id)
        if thread is not None:
            return thread

        with contextlib.suppress(discord.HTTPException):
            fetched = await self.bot.fetch_channel(thread_id)
            if isinstance(fetched, discord.Thread) and fetched.guild.id == guild.id:
                return fetched

        return None

    @staticmethod
    def _repo_number_key(repository: str, number: int) -> str:
        return f"{repository.casefold()}#{number}"

    @staticmethod
    def _one_line(value: Any) -> str:
        return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())

    @staticmethod
    def _within_schedule_window(
        now: datetime,
        hour: int,
        minute: int,
        *,
        window_minutes: int,
    ) -> bool:
        scheduled = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        delta = (now - scheduled).total_seconds()
        return 0 <= delta <= window_minutes * 60

    @staticmethod
    def _missing_text_permissions(
        channel: discord.TextChannel,
        *,
        require_threads: bool = False,
    ) -> List[str]:
        me = channel.guild.me
        if me is None:
            return ["Bot member unavailable"]

        permissions = channel.permissions_for(me)
        missing = []

        if not permissions.view_channel:
            missing.append("View Channel")
        if not permissions.send_messages:
            missing.append("Send Messages")
        if not permissions.read_message_history:
            missing.append("Read Message History")
        if not permissions.embed_links:
            missing.append("Embed Links")
        if require_threads and not permissions.create_public_threads:
            missing.append("Create Public Threads")
        if require_threads and not permissions.send_messages_in_threads:
            missing.append("Send Messages in Threads")

        return missing

    async def _audit(
        self,
        ctx: commands.Context,
        action: str,
        before: Any,
        after: Any,
    ):
        botops = self.bot.get_cog("BotOps")

        if botops is None or not hasattr(botops, "audit"):
            return

        with contextlib.suppress(Exception):
            await botops.audit(
                guild=ctx.guild,
                user=ctx.author,
                action=action,
                before=before,
                after=after,
                result="Success",
            )

    async def _report_error(
        self,
        guild: discord.Guild,
        *,
        operation: str,
        error: BaseException,
        ctx: Optional[commands.Context] = None,
    ):
        botops = self.bot.get_cog("BotOps")

        if botops is not None and hasattr(botops, "report_error"):
            with contextlib.suppress(Exception):
                await botops.report_error(
                    guild=guild,
                    operation=operation,
                    error=error,
                    ctx=ctx,
                    cog_name=self.__class__.__name__,
                    command_name=(
                        ctx.command.qualified_name
                        if ctx is not None and ctx.command is not None
                        else "automatic task"
                    ),
                )
                return

        log.error(
            "DevelopmentOps operation failed: %s: %s",
            operation,
            error,
            exc_info=error,
        )
