from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from aiohttp import web

from .developmentops import DevelopmentOps as BaseDevelopmentOps
from .security import verify_github_signature


class DevelopmentOps(BaseDevelopmentOps):
    """Compatibility hardening for webhook admission.

    A delivery is committed to the dedupe cache only after the bounded queue
    accepts it. This keeps a 503 retry from being incorrectly acknowledged as
    a duplicate and silently dropped.
    """

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

        if delivery_id and self.delivery_dedupe.contains(delivery_id):
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

        item: Dict[str, Any] = {
            "event": event,
            "payload": payload,
            "delivery_id": delivery_id,
        }
        try:
            self.webhook_queue.put_nowait(item)
        except asyncio.QueueFull:
            return web.json_response(
                {"ok": False, "error": "webhook queue full"},
                status=503,
            )

        if delivery_id:
            self.delivery_dedupe.remember(delivery_id)

        return web.json_response({"ok": True}, status=202)
