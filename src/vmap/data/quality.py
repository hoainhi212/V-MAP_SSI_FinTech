"""Theo dõi chất lượng dữ liệu: đếm sự kiện, phát hiện tin đến muộn / dữ liệu cũ."""
from __future__ import annotations

from collections import Counter
from datetime import datetime


class QualityTracker:
    def __init__(self, late_tolerance: int = 2, stale_after: int = 30):
        self.counts: Counter[str] = Counter()
        self._last_ts: dict[tuple[str, str], datetime] = {}
        self.late_tolerance = late_tolerance
        self.stale_after = stale_after

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] += n

    def check_late(self, kind: str, symbol: str, ts: datetime | None) -> bool:
        """Đến muộn = mốc thời gian lùi hơn `late_tolerance` giây so với tin mới nhất cùng khoá."""
        if ts is None:
            return False
        k = (kind, symbol)
        last = self._last_ts.get(k)
        late = last is not None and (last - ts).total_seconds() > self.late_tolerance
        if last is None or ts > last:
            self._last_ts[k] = ts
        if late:
            self.counts["late"] += 1
        return late

    def is_stale(self, ts: datetime | None, now: datetime) -> bool:
        return ts is None or (now - ts).total_seconds() > self.stale_after

    def valid_ratio(self) -> float | None:
        total = self.counts["received"]
        return None if total == 0 else self.counts["valid"] / total
