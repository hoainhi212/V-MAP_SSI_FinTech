"""Công thức tài chính thuần (không phụ thuộc pandas) để dễ kiểm thử và đối chiếu tính tay.

Quy ước: sổ lệnh là list[(giá, khối lượng)], mức 1 = tốt nhất. Đầu vào không hợp lệ => None.
"""
from __future__ import annotations

Level = tuple[float, float]


# ---------- Độ rộng thị trường ----------
def market_breadth(advances: int | None, declines: int | None, unchanged: int | None) -> float | None:
    """MBI = (A - D) / (A + D + U) ∈ [-1, 1]. Mẫu số gồm cả mã đứng giá để phản ánh đúng tỷ lệ cả rổ."""
    if advances is None or declines is None:
        return None
    total = advances + declines + (unchanged or 0)
    return None if total <= 0 else (advances - declines) / total


def index_return(value: float | None, prior: float | None) -> float | None:
    """Lợi suất trong phiên so với tham chiếu: V_t / V_ref - 1."""
    if value is None or not prior or prior <= 0:
        return None
    return value / prior - 1.0


def classify_regime(ret: float | None, mbi: float | None, eps: float = 0.001, mbi_th: float = 0.2) -> str:
    """Phân loại trạng thái dựa trên dấu của lợi suất chỉ số và MBI (ngưỡng eps/mbi_th để loại nhiễu)."""
    if ret is None or mbi is None:
        return "Chưa đủ dữ liệu"
    up, down = ret > eps, ret < -eps
    broad_up, broad_down = mbi >= mbi_th, mbi <= -mbi_th
    if up and broad_up:
        return "Tăng đồng thuận"
    if down and broad_down:
        return "Giảm đồng thuận"
    if up and broad_down:
        return "Phân kỳ: chỉ số tăng, độ rộng yếu"
    if down and broad_up:
        return "Phân kỳ: chỉ số giảm, độ rộng tốt"
    return "Trung tính / giằng co"


def is_divergence(regime: str) -> bool:
    return regime.startswith("Phân kỳ")


# ---------- Sổ lệnh ----------
def _qty(levels: list[Level], n: int) -> float:
    return sum(q for _, q in levels[:n])


def obi(bids: list[Level], asks: list[Level], levels: int = 3) -> float | None:
    """OBI_n = (ΣQbid - ΣQask) / (ΣQbid + ΣQask) ∈ [-1, 1] trên n mức tốt nhất."""
    if not bids or not asks:
        return None
    b, a = _qty(bids, levels), _qty(asks, levels)
    return None if (b + a) <= 0 else (b - a) / (b + a)


def wobi(bids: list[Level], asks: list[Level], levels: int = 10) -> float | None:
    """OBI có trọng số điều hoà w_i = 1/i: mức gần giá khớp có ảnh hưởng lớn hơn mức xa."""
    if not bids or not asks:
        return None
    b = sum(q / i for i, (_, q) in enumerate(bids[:levels], 1))
    a = sum(q / i for i, (_, q) in enumerate(asks[:levels], 1))
    return None if (b + a) <= 0 else (b - a) / (b + a)


def tick_size_hose(price: float) -> float:
    """Bước giá HOSE cổ phiếu: <10.000: 10 | 10.000-49.950: 50 | >=50.000: 100 (đồng)."""
    if price < 10_000:
        return 10.0
    return 50.0 if price < 50_000 else 100.0


def spread_abs(bids: list[Level], asks: list[Level]) -> float | None:
    if not bids or not asks:
        return None
    s = asks[0][0] - bids[0][0]
    return None if s < 0 else s  # s < 0 là sổ lệnh đảo (crossed) -> không hợp lệ


def spread_bps(bids: list[Level], asks: list[Level]) -> float | None:
    """Spread tương đối (điểm cơ bản) = (ask1 - bid1) / mid * 10^4."""
    s = spread_abs(bids, asks)
    if s is None:
        return None
    mid = (asks[0][0] + bids[0][0]) / 2.0
    return None if mid <= 0 else s / mid * 1e4


def spread_ticks(bids: list[Level], asks: list[Level]) -> float | None:
    s = spread_abs(bids, asks)
    return None if s is None else s / tick_size_hose(bids[0][0])


def depth_notional(levels: list[Level], n: int = 5) -> float:
    """Độ sâu theo giá trị (VND) = Σ giá_i × KL_i trên n mức."""
    return sum(p * q for p, q in levels[:n])


def depth_ratio(bid_depth: float | None, ask_depth: float | None) -> float | None:
    """DR = Depth_bid / Depth_ask. >1: bên mua dày hơn."""
    if bid_depth is None or not ask_depth:
        return None
    return bid_depth / ask_depth


def book_metrics(bids: list[Level], asks: list[Level], obi_levels: int = 3, depth_levels: int = 5) -> dict:
    """Gói toàn bộ chỉ báo của một snapshot sổ lệnh (dùng cho cả dashboard lẫn kiểm chứng)."""
    ok = bool(bids) and bool(asks) and asks[0][0] >= bids[0][0]
    if not ok:
        return dict(obi=None, wobi=None, spread_abs=None, spread_bps=None, spread_ticks=None,
                    depth_bid=None, depth_ask=None, depth_total=None, depth_ratio=None)
    db, da = depth_notional(bids, depth_levels), depth_notional(asks, depth_levels)
    return dict(obi=obi(bids, asks, obi_levels), wobi=wobi(bids, asks), spread_abs=spread_abs(bids, asks),
                spread_bps=spread_bps(bids, asks), spread_ticks=spread_ticks(bids, asks),
                depth_bid=db, depth_ask=da, depth_total=db + da, depth_ratio=depth_ratio(db, da))
