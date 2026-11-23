"""Lưu bản tin streaming V3 chuẩn hóa (và raw nếu bật VMAP_STORE_RAW) vào SQLite."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import VN_TZ, Settings
from .schema import parse_stream_message


class SQLiteStreamSink:
    def __init__(self, settings: Settings):
        self.db_path = Path(settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_raw = bool(settings.store_raw)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stream_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                trading_time TEXT,
                last_price REAL,
                price_tag TEXT,
                last_vol INTEGER,
                side TEXT,
                total_vol INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stream_indices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                index_id TEXT NOT NULL,
                index_value REAL,
                advances INTEGER,
                declines INTEGER,
                unchanged INTEGER,
                total_volume INTEGER
            )
            """
        )
        if self.store_raw:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stream_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        self._conn.commit()

    def handle(self, message: str | dict[str, Any]) -> None:
        parsed = parse_stream_message(message)
        if parsed is None:
            return
        kind, rec = parsed
        now_iso = datetime.now(VN_TZ).isoformat()
        cur = self._conn.cursor()

        if kind == "trade":
            cur.execute(
                """
                INSERT INTO stream_trades (
                    received_at, symbol, trading_time, last_price, price_tag, last_vol, side, total_vol
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    rec.get("symbol", ""),
                    rec.get("trading_time", ""),
                    rec.get("last_price"),
                    rec.get("price_tag"),
                    rec.get("last_vol"),
                    rec.get("side"),
                    rec.get("total_vol"),
                ),
            )
        elif kind == "index":
            cur.execute(
                """
                INSERT INTO stream_indices (
                    received_at, index_id, index_value, advances, declines, unchanged, total_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    rec.get("index_id", ""),
                    rec.get("index_value"),
                    rec.get("advances"),
                    rec.get("declines"),
                    rec.get("unchanged"),
                    rec.get("total_volume"),
                ),
            )

        if self.store_raw:
            cur.execute(
                "INSERT INTO stream_raw (received_at, kind, payload_json) VALUES (?, ?, ?)",
                (now_iso, kind, json.dumps(rec, ensure_ascii=False, default=str)),
            )

        self._conn.commit()

    def close(self) -> None:
        self._conn.close()