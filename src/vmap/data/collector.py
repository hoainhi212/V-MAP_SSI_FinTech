"""Lớp thu thập: nhận thông điệp thô -> kiểm tra -> chuẩn hoá -> lưu. Dùng chung cho dữ liệu thật & mô phỏng."""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import VN_TZ, Settings
from . import normalize as nz
from .db import Database
from .quality import QualityTracker

log = logging.getLogger(__name__)


class Collector:
    def __init__(self, db: Database, settings: Settings, source: str = "live"):
        if source not in ("live", "simulated"):
            raise ValueError("source phải là 'live' hoặc 'simulated' để không lẫn dữ liệu thật/giả")
        self.db, self.s, self.source = db, settings, source
        self.q = QualityTracker(settings.late_tolerance, settings.stale_after)
        self.watch = set(settings.symbols)
        self._prev_quote: dict[str, object] = {}
        self._since_commit = 0

    def event(self, event_type: str, detail: str = "", ts: datetime | None = None) -> None:
        self.q.bump(f"event_{event_type}")
        self.db.log_event(ts or datetime.now(VN_TZ), self.source, event_type, detail)

    def handle_message(self, raw: str, recv_ts: datetime | None = None) -> str:
        """Trả về: stored | duplicate | ignored | invalid."""
        recv_ts = recv_ts or datetime.now(VN_TZ)
        self.q.bump("received")
        if self.s.store_raw and self.source == "live":
            self.db.insert_raw(self.source, recv_ts, raw if isinstance(raw, str) else str(raw))
        try:
            inner, rtype = nz.unwrap(raw)
            kind = nz.classify(rtype)
            if kind == "other":
                self.q.bump("ignored")
                return "ignored"
            outcome = self._store(kind, inner, recv_ts)
        except nz.ParseError as e:
            self.q.bump("invalid")
            log.debug("Thông điệp lỗi: %s", e)
            return "invalid"
        self._since_commit += 1
        if self._since_commit >= 200:
            self.db.commit()
            self._since_commit = 0
        return outcome

    def _latency(self, ts_ex, recv_ts) -> float | None:
        return None if ts_ex is None else (recv_ts - ts_ex).total_seconds() * 1000.0

    def _store(self, kind: str, d: dict, recv_ts: datetime) -> str:
        if kind == "index":
            t = nz.parse_index(d)
            if t.index_id != self.s.index_code.upper():
                self.q.bump("ignored")
                return "ignored"
            if t.index_value is None:
                self.q.bump("missing_field")
            late = self.q.check_late("index", t.index_id, t.ts_exchange)
            ok = self.db.insert_index(self.source, recv_ts, self._latency(t.ts_exchange, recv_ts), late, t)
            return self._count(ok, t.ts_exchange is None)
        if kind == "trade":
            t = nz.parse_trade(d, self.s.price_scale)
            if t.symbol not in self.watch:
                self.q.bump("ignored")
                return "ignored"
            if t.last_price is None or t.last_vol is None:
                self.q.bump("missing_field")
            late = self.q.check_late("trade", t.symbol, t.ts_exchange)
            ok = self.db.insert_trade(self.source, recv_ts, self._latency(t.ts_exchange, recv_ts), late, t)
            return self._count(ok, t.ts_exchange is None)
        # quote
        sym = str(d.get("Symbol") or d.get("symbol") or d.get("s") or "").upper()
        if sym and sym not in self.watch:
            self.q.bump("ignored")
            return "ignored"
        qs = nz.parse_quote(d, self._prev_quote.get(sym), self.s.price_scale)
        if qs.partial:
            self.q.bump("partial")
        if qs.book_state != "ok":
            self.q.bump(f"book_{qs.book_state}")
        late = self.q.check_late("quote", qs.symbol, qs.ts_exchange)
        self._prev_quote[qs.symbol] = qs
        ok = self.db.insert_quote(self.source, recv_ts, self._latency(qs.ts_exchange, recv_ts), late, qs)
        return self._count(ok, qs.ts_exchange is None)

    def _count(self, inserted: bool, ts_missing: bool) -> str:
        if ts_missing:
            self.q.bump("missing_ts")
        if inserted:
            self.q.bump("valid")
            return "stored"
        self.q.bump("duplicate")
        return "duplicate"

    def flush(self) -> None:
        self.db.commit()
        self._since_commit = 0
