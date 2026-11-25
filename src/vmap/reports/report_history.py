"""Lưu lịch sử PDF được người dùng chủ động tạo."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime


def _connect(db_path: str | Path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS report_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_type TEXT NOT NULL,
        symbol TEXT,
        date_from TEXT NOT NULL,
        date_to TEXT NOT NULL,
        created_at TEXT NOT NULL,
        filename TEXT NOT NULL,
        pdf BLOB NOT NULL
    )""")
    con.commit()
    return con


def save_report(db_path, report_type, symbol, date_from, date_to, filename, pdf):
    with _connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO report_history(report_type,symbol,date_from,date_to,created_at,filename,pdf) VALUES(?,?,?,?,?,?,?)",
            (report_type, symbol, str(date_from), str(date_to),
             datetime.now().astimezone().isoformat(timespec="seconds"), filename, sqlite3.Binary(pdf))
        )
        return cur.lastrowid


def list_reports(db_path, limit=30):
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT id,report_type,symbol,date_from,date_to,created_at,filename FROM report_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return rows


def get_report(db_path, report_id):
    with _connect(db_path) as con:
        row = con.execute("SELECT filename,pdf FROM report_history WHERE id=?", (report_id,)).fetchone()
    return row
