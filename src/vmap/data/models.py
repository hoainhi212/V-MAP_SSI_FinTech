from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

Level = tuple[float, float]  # (giá VND, khối lượng cổ phiếu)


@dataclass
class IndexTick:
    ts_exchange: datetime | None
    index_id: str
    index_value: float | None
    prior_value: float | None
    change_pct: float | None
    advances: int | None
    declines: int | None
    unchanged: int | None
    total_value: float | None
    total_volume: float | None
    session: str | None = None


@dataclass
class TradeTick:
    ts_exchange: datetime | None
    symbol: str
    last_price: float | None
    last_vol: float | None
    total_vol: float | None
    total_val: float | None
    ref_price: float | None
    ratio_change: float | None
    session: str | None = None


@dataclass
class QuoteSnap:
    ts_exchange: datetime | None
    symbol: str
    bids: list[Level] = field(default_factory=list)   # mức 1 = tốt nhất, chỉ gồm mức hợp lệ liên tục
    asks: list[Level] = field(default_factory=list)
    book_state: str = "ok"      # ok | incomplete | crossed | auction
    partial: bool = False       # có mức giá bị thiếu khoá và được điền từ snapshot trước
    session: str | None = None
    # dạng thô theo mức (để gộp thông điệp cập nhật một phần)
    bid_map: dict[int, Level] = field(default_factory=dict)
    ask_map: dict[int, Level] = field(default_factory=dict)
