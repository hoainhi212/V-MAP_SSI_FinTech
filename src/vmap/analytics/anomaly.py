"""Phát hiện bất thường: z-score cuộn (không nhìn trước) + ngưỡng phân vị hiệu chỉnh theo từng mã."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_z(s: pd.Series, window: int = 30, min_periods: int = 10, sd_floor: float = 0.10) -> pd.Series:
    """z_t = (x_t - mean(x_{t-W..t-1})) / max(std(x_{t-W..t-1}), sd_floor*|mean|).
    - shift(1): điểm hiện tại không nằm trong mẫu ước lượng => không có look-ahead.
    - sd_floor: spread rời rạc theo bước giá nên có thể gần như hằng số (std ~ 0) làm z nổ vô nghĩa;
      sàn 10% của trung bình giúp chỉ những thay đổi có ý nghĩa kinh tế mới cho z lớn."""
    mu = s.rolling(window, min_periods=min_periods).mean().shift(1)
    sd = s.rolling(window, min_periods=min_periods).std().shift(1)
    sd = np.maximum(sd, sd_floor * mu.abs())
    return (s - mu) / sd.replace(0, np.nan)


def add_rolling_z(book: pd.DataFrame, cols: list[str], window: int = 30, min_periods: int = 10) -> pd.DataFrame:
    """Tính z-score theo từng (mã, phiên): không để dữ liệu qua đêm làm méo cửa sổ."""
    out = book.sort_values(["symbol", "minute"]).copy()
    for c in cols:
        out[f"z_{c}"] = out.groupby(["symbol", "session_date"])[c].transform(
            lambda x: rolling_z(x, window, min_periods))
    return out


def calibrate_thresholds(train: pd.DataFrame, min_obs: int = 100) -> pd.DataFrame:
    """Ngưỡng theo từng mã từ các phiên huấn luyện: spread = max(P95, 1,5 x trung vị), P5 độ sâu, P5 WOBI.
    Điều kiện 1,5 x trung vị tránh báo động khi spread vốn rời rạc/ổn định và P95 gần bằng mức bình thường."""
    g = train.groupby("symbol")
    thr = pd.DataFrame({
        "spread_p95": np.maximum(g["spread_bps"].quantile(0.95), 1.5 * g["spread_bps"].median()),
        "depth_p05": g["depth_total"].quantile(0.05),
        "wobi_p05": g["wobi"].quantile(0.05),
        "n_obs": g.size(),
    })
    thr.loc[thr["n_obs"] < min_obs, ["spread_p95", "depth_p05", "wobi_p05"]] = np.nan
    return thr


def percentile_rank(history: pd.Series, value: float) -> float | None:
    h = history.dropna()
    return None if h.empty or pd.isna(value) else float((h <= value).mean())
