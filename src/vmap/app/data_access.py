"""Nạp dữ liệu cho dashboard (không phụ thuộc Streamlit -> kiểm thử được)."""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from ..analytics import aggregate as ag
from ..analytics.alerts import AlertConfig, walk_forward
from ..config import MARKET_HOURS, VN_TZ, Settings, in_hours
from ..data.db import Database


def connection_status(db: Database, source: str, s: Settings, now: datetime | None = None) -> dict:
    now = now or datetime.now(VN_TZ)
    r = db.read("SELECT MAX(ts_recv) t FROM (SELECT ts_recv FROM quotes WHERE source=? UNION ALL "
                "SELECT ts_recv FROM index_ticks WHERE source=?)", (source, source))
    last = r["t"][0]
    ev = db.read("SELECT ts, event_type, detail FROM events WHERE source=? ORDER BY id DESC LIMIT 1", (source,))
    if last is None:
        return dict(state="no_data", label="Chưa có dữ liệu", last_recv=None, age_sec=None, last_event=None)
    last_dt = pd.Timestamp(last).tz_convert(VN_TZ)
    age = (now - last_dt).total_seconds()
    live_hours = now.weekday() < 5 and in_hours(now.time(), MARKET_HOURS)
    if source == "simulated":
        state, label = "simulated", "Dữ liệu MÔ PHỎNG (không phải thị trường thật)"
    elif not live_hours:
        state, label = "closed", "Ngoài giờ giao dịch - hiển thị dữ liệu phiên gần nhất"
    elif age <= s.stale_after:
        state, label = "ok", "Đang nhận dữ liệu"
    else:
        state, label = "stale", f"MẤT KẾT NỐI / dữ liệu cũ {int(age)} giây - số liệu có thể không còn đúng"
    last_event = None if ev.empty else f"{ev.event_type[0]} ({ev.ts[0][11:19]})"
    return dict(state=state, label=label, last_recv=last_dt, age_sec=age, last_event=last_event)


def load_bundle(db_path: str, source: str, s: Settings, cfg: AlertConfig | None = None) -> dict:
    db = Database(db_path)
    try:
        book = ag.build_book_1m(db, source, s)
        idx = ag.build_index_1m(db, source, s.index_code)
        flags, alerts, thr = walk_forward(book, cfg or AlertConfig(), source)
        status = connection_status(db, source, s)
        counts = db.read("SELECT (SELECT COUNT(*) FROM quotes WHERE source=?) q, "
                         "(SELECT COUNT(*) FROM trades WHERE source=?) t, "
                         "(SELECT COUNT(*) FROM index_ticks WHERE source=?) i", (source, source, source))
    finally:
        db.close()
    return dict(book=book, idx=idx, flags=flags, alerts=alerts, thr=thr, status=status,
                counts=counts.iloc[0].to_dict())


def latest_book(db_path: str, source: str, symbol: str) -> dict | None:
    db = Database(db_path)
    try:
        r = db.read("SELECT ts_exchange, bid_levels, ask_levels FROM quotes WHERE source=? AND symbol=? "
                    "AND book_state='ok' ORDER BY ts_exchange DESC LIMIT 1", (source, symbol))
    finally:
        db.close()
    if r.empty:
        return None
    return dict(ts=r.ts_exchange[0], bids=json.loads(r.bid_levels[0]), asks=json.loads(r.ask_levels[0]))
