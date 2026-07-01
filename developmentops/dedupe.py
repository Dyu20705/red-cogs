from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone


class DeliveryDedupe:
    def __init__(self, *, ttl_seconds: int = 86400, max_size: int = 1000):
        self.ttl = timedelta(seconds=max(1, int(ttl_seconds)))
        self.max_size = max(1, int(max_size))
        self._items: OrderedDict[str, datetime] = OrderedDict()

    def seen(self, key: str, *, now: datetime | None = None) -> bool:
        if not key:
            return False
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        self.prune(now=now)
        if key in self._items:
            return True
        self._items[key] = now
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)
        return False

    def prune(self, *, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        cutoff = now - self.ttl
        while self._items:
            first_key = next(iter(self._items))
            if self._items[first_key] >= cutoff:
                break
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
