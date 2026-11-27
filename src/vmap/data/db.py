"""SQLite: dữ liệu thô -> dữ liệu chuẩn hoá -> chỉ báo dẫn xuất. Mốc thời gian lưu ISO-8601 +07:00."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config import VN_TZ

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_messages(
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, ts_recv TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS index_ticks(
  id INTEGER PRIMARY KEY, dedup_key TEXT UNIQUE, source TEXT NOT NULL,
  ts_exchange TEXT, ts_recv TEXT NOT NULL, latency_ms REAL, is_late INTEGER DEFAULT 0,
  index_id TEXT, index_value REAL, prior_value REAL, change_pct REAL,
  advances INTEGER, declines INTEGER, unchanged INTEGER, total_value REAL, total_volume REAL, session TEXT);
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY, dedup_key TEXT UNIQUE, source TEXT NOT NULL,
  ts_exchange TEXT, ts_recv TEXT NOT NULL, latency_ms REAL, is_late INTEGER DEFAULT 0,
  symbol TEXT, last_price REAL, last_vol REAL, total_vol REAL, total_val REAL,
  ref_price REAL, ratio_change REAL, session TEXT);
CREATE TABLE IF NOT EXISTS quotes(
  id INTEGER PRIMARY KEY, dedup_key TEXT UNIQUE, source TEXT NOT NULL,
  ts_exchange TEXT, ts_recv TEXT NOT NULL, latency_ms REAL, is_late INTEGER DEFAULT 0,
  symbol TEXT, book_state TEXT, partial INTEGER DEFAULT 0, session TEXT,
  bid_levels TEXT, ask_levels TEXT);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY, source TEXT, symbol TEXT, severity TEXT, start_ts TEXT, end_ts TEXT,
  peak_level INTEGER, reason TEXT, closed_reason TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, source TEXT, event_type TEXT NOT NULL, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_q_sym_ts ON quotes(symbol, ts_exchange);
CREATE INDEX IF NOT EXISTS ix_t_sym_ts ON trades(symbol, ts_exchange);
CREATE INDEX IF NOT EXISTS ix_i_ts ON index_ticks(ts_exchange);
"""


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(VN_TZ).isoformat(timespec="seconds")


def make_key(*parts) -> str:
    return hashlib.sha1("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _insert(self, sql: str, params: tuple) -> bool:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.rowcount == 1

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    # ---- ghi ----
    def insert_raw(self, source: str, ts_recv: datetime, payload: str) -> None:
        self._insert("INSERT INTO raw_messages(source,ts_recv,payload) VALUES(?,?,?)",
                     (source, iso(ts_recv), payload))

    def insert_index(self, source, ts_recv, latency_ms, late, t) -> bool:
        key = make_key("MI", t.index_id, iso(t.ts_exchange), t.index_value, t.total_value)
        return self._insert(
            "INSERT OR IGNORE INTO index_ticks(dedup_key,source,ts_exchange,ts_recv,latency_ms,is_late,index_id,"
            "index_value,prior_value,change_pct,advances,declines,unchanged,total_value,total_volume,session)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, source, iso(t.ts_exchange), iso(ts_recv), latency_ms, int(late), t.index_id, t.index_value,
             t.prior_value, t.change_pct, t.advances, t.declines, t.unchanged, t.total_value,
             t.total_volume, t.session))

    def insert_trade(self, source, ts_recv, latency_ms, late, t) -> bool:
        key = make_key("T", t.symbol, iso(t.ts_exchange), t.last_price, t.last_vol, t.total_vol)
        return self._insert(
            "INSERT OR IGNORE INTO trades(dedup_key,source,ts_exchange,ts_recv,latency_ms,is_late,symbol,"
            "last_price,last_vol,total_vol,total_val,ref_price,ratio_change,session) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, source, iso(t.ts_exchange), iso(ts_recv), latency_ms, int(late), t.symbol, t.last_price,
             t.last_vol, t.total_vol, t.total_val, t.ref_price, t.ratio_change, t.session))

    def insert_quote(self, source, ts_recv, latency_ms, late, q) -> bool:
        bl, al = json.dumps(q.bids), json.dumps(q.asks)
        key = make_key("Q", q.symbol, iso(q.ts_exchange), bl, al)
        return self._insert(
            "INSERT OR IGNORE INTO quotes(dedup_key,source,ts_exchange,ts_recv,latency_ms,is_late,symbol,"
            "book_state,partial,session,bid_levels,ask_levels) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, source, iso(q.ts_exchange), iso(ts_recv), latency_ms, int(late), q.symbol, q.book_state,
             int(q.partial), q.session, bl, al))

    def log_event(self, ts: datetime, source: str, event_type: str, detail: str = "") -> None:
        self._insert("INSERT INTO events(ts,source,event_type,detail) VALUES(?,?,?,?)",
                     (iso(ts), source, event_type, detail))
        self.commit()

    def replace_alerts(self, source: str, df: pd.DataFrame) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM alerts WHERE source=?", (source,))
            for r in df.itertuples(index=False):
                self._conn.execute(
                    "INSERT INTO alerts(source,symbol,severity,start_ts,end_ts,peak_level,reason,closed_reason)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (source, r.symbol, r.severity, str(r.start_ts), str(r.end_ts), int(r.peak_level),
                     r.reason, r.closed_reason))
            self._conn.commit()

    # ---- đọc ----
    def read(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._lock:
            return pd.read_sql_query(sql, self._conn, params=params)

    def sources(self) -> list[str]:
        return self.read("SELECT DISTINCT source FROM quotes UNION SELECT DISTINCT source FROM index_ticks")["source"].tolist()
