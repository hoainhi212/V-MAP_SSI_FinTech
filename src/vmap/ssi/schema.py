"""Ánh xạ tên trường SSI -> tên chuẩn hoá của V-MAP (tương thích FastConnect V3 & legacy).

Mỗi trường có danh sách tên thay thế (alias): nếu SSI đổi tên trường hoặc dùng ký hiệu rút gọn
(adv, dec, nc, v, cr, p, q, bids, asks, ce, fl, ref...), chỉ cần sửa tại ĐÂY, không phải sửa logic xử lý.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from ssi_sdk.models.streaming import (
    IndexSummaryMessage,
    MarketDataMessage,
    QuoteMessage,
    TradeMessage,
)

from ..config import VN_TZ

INDEX_FIELDS = {
    "index_id": ["IndexId", "IndexCode", "indexId", "index"],
    "index_value": ["IndexValue", "indexValue", "v", "Value", "value"],
    "prior_value": ["PriorIndexValue", "PriorValue", "pv"],
    "change_pct": ["RatioChange", "cr", "ChangePct"],
    "advances": ["Advances", "advances", "adv"],
    "declines": ["Declines", "declines", "dec"],
    "unchanged": ["NoChanges", "NoChange", "Unchanged", "nc"],
    "total_value": ["TotalValue", "TotalVal", "tv"],
    "total_volume": ["TotalQtty", "TotalVol", "TotalQty", "tq"],
    "session": ["TradingSession", "Session"],
}
TRADE_FIELDS = {
    "symbol": ["Symbol", "symbol", "s"],
    "last_price": ["LastPrice", "MatchPrice", "price", "p"],
    "last_vol": ["LastVol", "MatchVol", "quantity", "q"],
    "total_vol": ["TotalVol", "TotalQtty", "TotalQty", "total_volume", "v"],
    "total_val": ["TotalVal", "TotalValue"],
    "ref_price": ["RefPrice", "Reference", "ref_price", "ref"],
    "ceiling": ["Ceiling", "ceiling", "ce"],
    "floor": ["Floor", "floor", "fl"],
    "ratio_change": ["RatioChange", "cr"],
    "session": ["TradingSession", "Session"],
}
QUOTE_FIELDS = {
    "symbol": ["Symbol", "symbol", "s"],
    "ref_price": ["RefPrice", "Reference", "ref_price", "ref"],
    "session": ["TradingSession", "Session"],
}
DATE_KEYS = ["TradingDate", "Date", "date"]
TIME_KEYS = ["Time", "time", "trading_time", "t"]
SIDE_KEYS = {"bid": ["Bid", "bid", "bids", "bid_prices"], "ask": ["Ask", "ask", "Offer", "asks", "ask_prices"]}
MAX_LEVELS = 10


def pick(d: dict, keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None and d[k] != "":
            return d[k]
    return default


def has_key(d: dict, keys: list[str]) -> bool:
    return any(k in d for k in keys)


def to_float(x: Any) -> float | None:
    """Chuyển về float; chuỗi như 'ATO', 'ATC', '' hoặc NaN => None (không bịa số)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(str(x).replace(",", "")) if isinstance(x, str) else float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(v) or math.isinf(v)) else v


def to_int(x: Any) -> int | None:
    v = to_float(x)
    return None if v is None else int(v)


def parse_exchange_ts(d: dict) -> datetime | None:
    """Gộp TradingDate (dd/MM/yyyy) + Time (HH:mm:ss) thành datetime múi giờ Việt Nam."""
    ds, ts = pick(d, DATE_KEYS), pick(d, TIME_KEYS)
    if ds is None or ts is None:
        return None
    ds, ts = str(ds).strip(), str(ts).strip()
    for dfmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        for tfmt in ("%H:%M:%S", "%H%M%S", "%H:%M:%S.%f"):
            try:
                return datetime.strptime(f"{ds} {ts}", f"{dfmt} {tfmt}").replace(tzinfo=VN_TZ)
            except ValueError:
                continue
    return None


def unwrap_v3_message(raw: str | dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Tách `(topic, payload_dict)` từ chuỗi JSON hoặc dict của FastConnect V3.

    Trả về `("", {})` nếu là bản tin điều khiển/ACK (ví dụ `{"method": "subscribe", ...}`).
    """
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return "", {}
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return "", {}
    elif isinstance(raw, dict):
        obj = raw
    else:
        return "", {}

    if not isinstance(obj, dict):
        return "", {}

    # Bỏ qua frame xác nhận subscribe / ping / control không mang dữ liệu thị trường
    if obj.get("method") == "subscribe" and "data" not in obj and "content" not in obj:
        return "", {}

    topic = str(obj.get("topic") or obj.get("rType") or obj.get("channel") or "").strip()
    for container_key in ("data", "content", "payload"):
        inner = obj.get(container_key)
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                inner = None
        if isinstance(inner, dict):
            merged = dict(inner)
            if topic and "topic" not in merged:
                merged["_topic"] = topic
            return topic, merged

    return topic, obj


def parse_trade_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa bản tin khớp lệnh (Trade) từ V3 (rút gọn hoặc đầy đủ)."""
    msg = TradeMessage.from_dict(payload)
    raw_price = pick(payload, TRADE_FIELDS["last_price"], msg.price)
    last_price = to_float(raw_price)
    price_tag = str(raw_price).strip() if last_price is None and raw_price not in (None, "") else None

    return {
        "symbol": str(msg.symbol or pick(payload, TRADE_FIELDS["symbol"], "")).strip().upper(),
        "trading_time": msg.trading_time or str(pick(payload, TIME_KEYS, "") or ""),
        "last_price": last_price,
        "price_tag": price_tag,
        "last_vol": to_int(msg.quantity) if msg.quantity else to_int(pick(payload, TRADE_FIELDS["last_vol"])),
        "side": msg.side or "U",
        "total_vol": to_int(msg.total_volume) if msg.total_volume else to_int(pick(payload, TRADE_FIELDS["total_vol"])),
        "total_val": to_float(pick(payload, TRADE_FIELDS["total_val"])),
        "open": to_float(msg.open),
        "high": to_float(msg.high),
        "low": to_float(msg.low),
        "avg": to_float(msg.avg),
    }


def parse_quote_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa bản tin dư mua/dư bán (Quote) từ V3."""
    msg = QuoteMessage.from_dict(payload)
    bids: list[tuple[float | None, int | None]] = [
        (to_float(p), to_int(v))
        for p, v in zip(msg.bid_prices[:MAX_LEVELS], msg.bid_volumes[:MAX_LEVELS])
    ]
    asks: list[tuple[float | None, int | None]] = [
        (to_float(p), to_int(v))
        for p, v in zip(msg.ask_prices[:MAX_LEVELS], msg.ask_volumes[:MAX_LEVELS])
    ]

    return {
        "symbol": str(msg.symbol or pick(payload, QUOTE_FIELDS["symbol"], "")).strip().upper(),
        "trading_time": msg.trading_time or str(pick(payload, TIME_KEYS, "") or ""),
        "bids": bids,
        "asks": asks,
        "ref_price": to_float(pick(payload, QUOTE_FIELDS["ref_price"])),
        "session": pick(payload, QUOTE_FIELDS["session"]),
    }


def parse_index_message(payload: dict[str, Any], topic: str = "") -> dict[str, Any]:
    """Chuẩn hóa bản tin chỉ số (IndexSummaryMessage) từ V3."""
    idx_msg = IndexSummaryMessage.from_dict(payload, topic=topic)
    index_id = (
        idx_msg.index
        or str(pick(payload, INDEX_FIELDS["index_id"], "")).strip().upper()
    )
    index_value = to_float(
        idx_msg.get("indexValue", "IndexValue", "index_value", "v", "Value")
    )
    return {
        "index_id": index_id,
        "index_value": index_value,
        "prior_value": to_float(pick(payload, INDEX_FIELDS["prior_value"])),
        "change_pct": to_float(pick(payload, INDEX_FIELDS["change_pct"])),
        "advances": to_int(pick(payload, INDEX_FIELDS["advances"])),
        "declines": to_int(pick(payload, INDEX_FIELDS["declines"])),
        "unchanged": to_int(pick(payload, INDEX_FIELDS["unchanged"])),
        "total_value": to_float(pick(payload, INDEX_FIELDS["total_value"])),
        "total_volume": to_int(pick(payload, INDEX_FIELDS["total_volume"])),
        "session": pick(payload, INDEX_FIELDS["session"]),
        "raw": idx_msg.data,
    }


def parse_market_data_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa bản tin trần/sàn/tham chiếu (`MarketDataMessage`)."""
    md_msg = MarketDataMessage.from_dict(payload)
    return {
        "symbol": str(md_msg.symbol or pick(payload, TRADE_FIELDS["symbol"], "")).strip().upper(),
        "board": str(md_msg.board or ""),
        "trading_time": md_msg.trading_time or str(pick(payload, TIME_KEYS, "") or ""),
        "ceiling": to_float(md_msg.ceiling),
        "floor": to_float(md_msg.floor),
        "ref_price": to_float(md_msg.ref_price),
    }
def parse_stream_message(raw: str | dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Điều phối bản tin streaming V3 sang parser tương ứng.

    Trả về `(kind, record)` với `kind` thuộc `{"trade", "quote", "index", "market"}`,
    hoặc `None` nếu là bản tin điều khiển/không có dữ liệu.
    """
    topic, payload = unwrap_v3_message(raw)
    if not payload:
        return None

    t_low = topic.lower()

    if t_low.startswith("indexsummary.") or "index" in t_low or has_key(payload, INDEX_FIELDS["index_value"]):
        return "index", parse_index_message(payload, topic=topic)

    if t_low.startswith("quote.") or "quote" in t_low or ("bids" in payload or "asks" in payload):
        return "quote", parse_quote_message(payload)

    if t_low.startswith("market.") or ("ce" in payload or "fl" in payload or "ref" in payload):
        return "market", parse_market_data_message(payload)

    if t_low.startswith("trade.") or "trade" in t_low or has_key(payload, TRADE_FIELDS["last_price"]):
        return "trade", parse_trade_message(payload)

    return "raw", {"topic": topic, "payload": payload}