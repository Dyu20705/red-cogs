from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone


class DeliveryDedupe:
    """Bounded in-memory delivery cache with explicit check/commit semantics."""

    def __init__(self, *, ttl_seconds: int = 86400, max_size: int = 1000):
        self.ttl = timedelta(seconds=max(1, int(ttl_seconds)))
        self.max_size = max(1, int(max_size))
        self._items: OrderedDict[str, datetime] = OrderedDict()

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def contains(self, key: str, *, now: datetime | None = None) -> bool:
        if not key:
            return False
        value = self._normalize_now(now)
        self.prune(now=value)
        return key in self._items

    def remember(self, key: str, *, now: datetime | None = None) -> None:
        if not key:
            return
        value = self._normalize_now(now)
        self.prune(now=value)
        self._items.pop(key, None)
        self._items[key] = value
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def discard(self, key: str) -> None:
        self._items.pop(key, None)

    def seen(self, key: str, *, now: datetime | None = None) -> bool:
        """Backward-compatible check-and-record helper.

        New ingress code should call ``contains`` before accepting work and
        ``remember`` only after the work has been queued successfully.
        """

        value = self._normalize_now(now)
        if self.contains(key, now=value):
            return True
        self.remember(key, now=value)
        return False

    def prune(self, *, now: datetime | None = None) -> None:
        value = self._normalize_now(now)
        cutoff = value - self.ttl
        while self._items:
            first_key = next(iter(self._items))
            if self._items[first_key] >= cutoff:
                break
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
