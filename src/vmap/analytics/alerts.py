"""Cảnh báo rủi ro thanh khoản: điều kiện -> mức độ -> duy trì/kết thúc (hysteresis) -> giải thích."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .anomaly import add_rolling_z, calibrate_thresholds

SEVERITY = {1: "WATCH", 2: "WARNING", 3: "CRITICAL"}


@dataclass
class AlertConfig:
    z_th: float = 2.0            # |z| tối thiểu (xấp xỉ top ~2,3% một phía nếu phân phối gần chuẩn)
    wobi_floor: float = -0.20    # sàn tuyệt đối để WOBI âm nhẹ không bị coi là áp lực bán
    persist_open: int = 2        # số phút liên tiếp có tín hiệu để mở cảnh báo (lọc nhiễu)
    persist_close: int = 3       # số phút liên tiếp hết tín hiệu để đóng cảnh báo (tránh nhấp nháy)
    min_train_sessions: int = 3  # số phiên tối thiểu để hiệu chỉnh ngưỡng
    min_obs: int = 100
    window: int = 30
    min_periods: int = 10


def _flags(df: pd.DataFrame, thr: pd.DataFrame, cfg: AlertConfig) -> pd.DataFrame:
    d = df.merge(thr[["spread_p95", "depth_p05", "wobi_p05"]], left_on="symbol", right_index=True, how="left")
    d["c_spread"] = (d["spread_bps"] >= d["spread_p95"]) & (d["z_spread_bps"] >= cfg.z_th)
    d["c_depth"] = (d["depth_total"] <= d["depth_p05"]) & (d["z_depth_total"] <= -cfg.z_th)
    d["c_sell"] = d["wobi"] <= np.minimum(d["wobi_p05"], cfg.wobi_floor)
    for c in ("c_spread", "c_depth", "c_sell"):
        d[c] = d[c].fillna(False).astype(bool)
    d["n_flags"] = d[["c_spread", "c_depth", "c_sell"]].sum(axis=1)
    return d


def explain(r) -> str:
    parts = []
    if r.c_spread:
        parts.append(f"Spread {r.spread_bps:.1f} bps (≥ P95 của mã = {r.spread_p95:.1f}; z = {r.z_spread_bps:.1f})")
    if r.c_depth:
        parts.append(f"Độ sâu {r.depth_total / 1e6:,.0f} triệu đ (≤ P5 = {r.depth_p05 / 1e6:,.0f}; z = {r.z_depth_total:.1f})")
    if r.c_sell:
        parts.append(f"WOBI = {r.wobi:.2f}: bên bán dày hơn bên mua")
    return "; ".join(parts) or "Không có điều kiện nào được kích hoạt"


def build_alerts(flags: pd.DataFrame, cfg: AlertConfig, source: str = "") -> pd.DataFrame:
    """Máy trạng thái theo từng (mã, phiên):
    - Mở cảnh báo khi có >=1 điều kiện liên tục `persist_open` phút (lọc nhiễu 1 điểm).
    - Đóng khi hết điều kiện liên tục `persist_close` phút (hysteresis, tránh nhấp nháy).
    - Mức độ = số điều kiện đồng thời lớn nhất trong thời gian cảnh báo; hết phiên thì đóng bắt buộc."""
    out = []
    for (sym, _), g in flags.sort_values("minute").groupby(["symbol", "session_date"]):
        pending, active, off = None, None, 0
        for r in g.itertuples(index=False):
            n = int(r.n_flags)
            if active is None:
                if n >= 1:
                    if pending is None:
                        pending = dict(start=r.minute, count=0, peak=0, reason="")
                    pending["count"] += 1
                    if n > pending["peak"]:
                        pending.update(peak=n, reason=explain(r))
                    if pending["count"] >= cfg.persist_open:
                        active = dict(start=pending["start"], last_on=r.minute,
                                      peak=pending["peak"], reason=pending["reason"])
                        pending, off = None, 0
                else:
                    pending = None
            elif n >= 1:
                off = 0
                active["last_on"] = r.minute
                if n > active["peak"]:
                    active.update(peak=n, reason=explain(r))
            else:
                off += 1
                if off >= cfg.persist_close:
                    out.append(_row(sym, active, active["last_on"], "cleared", source))
                    active, off = None, 0
        if active is not None:
            out.append(_row(sym, active, g["minute"].iloc[-1], "end_of_session", source))
    cols = ["source", "symbol", "severity", "start_ts", "end_ts", "peak_level", "reason", "closed_reason"]
    return pd.DataFrame(out, columns=cols)


def _row(sym, cur, end, closed, source):
    return dict(source=source, symbol=sym, severity=SEVERITY[cur["peak"]], start_ts=cur["start"],
                end_ts=end, peak_level=cur["peak"], reason=cur["reason"], closed_reason=closed)


def walk_forward(book: pd.DataFrame, cfg: AlertConfig | None = None, source: str = ""):
    """Với mỗi phiên d: hiệu chỉnh ngưỡng CHỈ từ các phiên trước d, rồi đánh giá phiên d.
    Trả (flags, alerts, thresholds_mới_nhất). Các phiên đầu chưa đủ dữ liệu hiệu chỉnh thì không phát cảnh báo."""
    cfg = cfg or AlertConfig()
    if book.empty:
        return pd.DataFrame(), build_alerts(pd.DataFrame(columns=["symbol", "session_date", "minute", "n_flags"]), cfg), pd.DataFrame()
    book = add_rolling_z(book, ["spread_bps", "depth_total"], cfg.window, cfg.min_periods)
    dates = sorted(book["session_date"].unique())
    parts, last_thr = [], pd.DataFrame()
    for k, d in enumerate(dates):
        if k < cfg.min_train_sessions:
            continue
        thr = calibrate_thresholds(book[book["session_date"].isin(dates[:k])], cfg.min_obs)
        parts.append(_flags(book[book["session_date"] == d], thr, cfg))
        last_thr = thr
    if not parts:
        return pd.DataFrame(), build_alerts(pd.DataFrame(columns=["symbol", "session_date", "minute", "n_flags"]), cfg), last_thr
    flags = pd.concat(parts, ignore_index=True)
    return flags, build_alerts(flags, cfg, source), last_thr
