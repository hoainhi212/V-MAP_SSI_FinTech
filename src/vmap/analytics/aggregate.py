"""Tầng tổng hợp: dữ liệu chuẩn hoá trong SQLite -> chuỗi 1 phút. Chạy lại được 100% từ dữ liệu đã lưu."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..config import CONTINUOUS_SESSIONS, VN_TZ, Settings
from ..finance import indicators as fi


def _to_vn(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="ISO8601").dt.tz_convert(VN_TZ)


def in_continuous(ts: pd.Series) -> pd.Series:
    t = ts.dt.time
    mask = pd.Series(False, index=ts.index)
    for a, b in CONTINUOUS_SESSIONS:
        mask |= (t >= a) & (t <= b)
    return mask


# ---------------------------------------------------------------- sổ lệnh
def build_book_1m(db, source: str, s: Settings) -> pd.DataFrame:
    q = db.read("SELECT ts_exchange, symbol, bid_levels, ask_levels, is_late FROM quotes "
                "WHERE source=? AND book_state='ok' AND ts_exchange IS NOT NULL", (source,))
    if q.empty:
        return pd.DataFrame()
    q["ts"] = _to_vn(q["ts_exchange"])
    q = q[in_continuous(q["ts"])].copy()
    if q.empty:
        return pd.DataFrame()
    rows = [fi.book_metrics(json.loads(b), json.loads(a), s.obi_levels, s.depth_levels)
            for b, a in zip(q["bid_levels"], q["ask_levels"])]
    m = pd.DataFrame(rows, index=q.index)
    m["symbol"], m["minute"] = q["symbol"], q["ts"].dt.floor("min")
    m = m.dropna(subset=["spread_bps"])
    g = m.groupby(["symbol", "minute"], as_index=False).agg(
        obi=("obi", "mean"), wobi=("wobi", "mean"), spread_bps=("spread_bps", "mean"),
        spread_ticks=("spread_ticks", "mean"), depth_bid=("depth_bid", "mean"),
        depth_ask=("depth_ask", "mean"), depth_total=("depth_total", "mean"),
        depth_ratio=("depth_ratio", "mean"), n_snap=("obi", "size"))
    g["session_date"] = g["minute"].dt.strftime("%Y-%m-%d")
    return g.sort_values(["symbol", "minute"]).reset_index(drop=True)


# ---------------------------------------------------------------- chỉ số / độ rộng
def build_index_1m(db, source: str, index_code: str) -> pd.DataFrame:
    t = db.read("SELECT ts_exchange, index_value, prior_value, advances, declines, unchanged, total_value "
                "FROM index_ticks WHERE source=? AND index_id=? AND ts_exchange IS NOT NULL",
                (source, index_code.upper()))
    if t.empty:
        return pd.DataFrame()
    t["ts"] = _to_vn(t["ts_exchange"])
    t = t[in_continuous(t["ts"])].sort_values("ts")
    if t.empty:
        return pd.DataFrame()
    t["minute"] = t["ts"].dt.floor("min")
    g = t.groupby("minute", as_index=False).last()
    g["ret"] = [fi.index_return(v, p) for v, p in zip(g["index_value"], g["prior_value"])]
    g["mbi"] = [fi.market_breadth(*(None if pd.isna(x) else int(x) for x in r))
                for r in g[["advances", "declines", "unchanged"]].itertuples(index=False)]
    g["regime"] = [fi.classify_regime(r, b) for r, b in zip(g["ret"], g["mbi"])]
    g["divergence"] = g["regime"].map(fi.is_divergence)
    g["session_date"] = g["minute"].dt.strftime("%Y-%m-%d")
    g["tod"] = g["minute"].dt.hour * 60 + g["minute"].dt.minute
    # So sánh giá trị giao dịch lũy kế cùng khung giờ với trung bình các phiên TRƯỚC (không nhìn trước)
    piv = g.pivot_table(index="session_date", columns="tod", values="total_value", aggfunc="last")
    piv = piv.ffill(axis=1)
    base = piv.expanding().mean().shift(1)
    ratio = (piv / base).stack().rename("value_ratio").reset_index()
    g = g.merge(ratio, on=["session_date", "tod"], how="left")
    return g.drop(columns=["tod"]).reset_index(drop=True)


def breadth_from_trades(db, source: str, symbols: list[str]) -> pd.DataFrame:
    """Tự tính độ rộng từ giá khớp cuối vs giá tham chiếu từng mã -> đối chiếu chéo với số liệu MI của SSI."""
    t = db.read("SELECT ts_exchange, symbol, last_price, ref_price FROM trades "
                "WHERE source=? AND ts_exchange IS NOT NULL AND last_price IS NOT NULL", (source,))
    if t.empty:
        return pd.DataFrame()
    t["ts"] = _to_vn(t["ts_exchange"])
    t = t[in_continuous(t["ts"])].sort_values("ts")
    t["minute"] = t["ts"].dt.floor("min")
    t["session_date"] = t["minute"].dt.strftime("%Y-%m-%d")
    last = t.groupby(["session_date", "minute", "symbol"], as_index=False).last()
    out = []
    for d, day in last.groupby("session_date"):
        px = day.pivot(index="minute", columns="symbol", values="last_price").ffill()
        rf = day.pivot(index="minute", columns="symbol", values="ref_price").ffill().bfill()
        rf = rf.reindex(columns=px.columns)
        valid = px.notna() & rf.notna()
        adv, dec = ((px > rf) & valid).sum(axis=1), ((px < rf) & valid).sum(axis=1)
        unch = (valid.sum(axis=1) - adv - dec)
        res = pd.DataFrame({"minute": px.index, "adv_calc": adv.values, "dec_calc": dec.values,
                            "unch_calc": unch.values, "n_symbols": valid.sum(axis=1).values})
        res["mbi_calc"] = [fi.market_breadth(a, b, c) for a, b, c in
                           zip(res["adv_calc"], res["dec_calc"], res["unch_calc"])]
        out.append(res)
    return pd.concat(out, ignore_index=True)
