"""Phân tích thông điệp SSI thô -> bản ghi chuẩn hoá. Không bịa dữ liệu: trường lỗi => None."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from . import models as m
from ..config import VN_TZ
from ..ssi import schema as sc


class ParseError(ValueError):
    pass


_HMS = re.compile(r"^\d{2}:\d{2}:\d{2}$")


_TS_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S")


def _stamp(legacy: dict, payload: dict) -> None:
    """V3 gửi trading_time dạng '2026/11/25 10:04:21' (có ngày) hoặc chỉ 'HH:MM:SS'.
    Không đọc được thì dùng giờ nhận (xấp xỉ) và đánh dấu _ts_estimated."""
    now = datetime.now(VN_TZ)
    t = sc.pick(payload, ["t", "trading_time", "Time", "time"])
    if isinstance(t, str):
        t = t.strip()
        if _HMS.match(t):
            legacy["TradingDate"], legacy["Time"] = now.strftime("%d/%m/%Y"), t
            return
        for fmt in _TS_FORMATS:
            try:
                dt = datetime.strptime(t, fmt)
            except ValueError:
                continue
            legacy["TradingDate"], legacy["Time"] = dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S")
            return
    legacy["TradingDate"], legacy["Time"] = now.strftime("%d/%m/%Y"), now.strftime("%H:%M:%S")
    legacy["_ts_estimated"] = True


def _levels_v3(payload: dict, side: str) -> list[tuple[float | None, float | None]]:
    """side = 'bid' | 'ask'. Hỗ trợ dạng dây [[giá, KL], ...] và dạng dataclass (prices/volumes song song)."""
    pairs = payload.get(f"{side}s")
    if isinstance(pairs, list):
        out = []
        for lv in pairs:
            if isinstance(lv, (list, tuple)) and len(lv) >= 2:
                out.append((sc.to_float(lv[0]), sc.to_float(lv[1])))
            elif isinstance(lv, dict):
                out.append((sc.to_float(sc.pick(lv, ["p", "price"])), sc.to_float(sc.pick(lv, ["q", "v", "volume"]))))
        return out
    prices, vols = payload.get(f"{side}_prices") or [], payload.get(f"{side}_volumes") or []
    return [(sc.to_float(p), sc.to_float(v)) for p, v in zip(prices, vols)]


def _from_v3(obj: dict) -> tuple[dict, str] | None:
    """Nhận diện tin FastConnect V3 (khung {topic, data} hoặc dataclass đã serialize) và đổi về tên trường nội bộ.
    Trả None nếu không phải V3 để đi tiếp đường cũ."""
    topic = str(obj.get("topic") or "").lower()
    has_data = isinstance(obj.get("data"), dict)
    payload = obj["data"] if has_data else obj
    legacy: dict = {}
    if topic.startswith("indexsummary") or (has_data and "index" in obj):
        code = topic.split(".", 1)[1] if "." in topic else str(obj.get("index") or "")
        if not code:
            return None
        legacy.update(payload)
        legacy["RType"], legacy["IndexId"] = "MI", code.upper()
        v, c = sc.to_float(payload.get("v")), sc.to_float(payload.get("c"))
        if v is not None and c is not None and "PriorIndexValue" not in legacy:
            legacy["PriorIndexValue"] = round(v - c, 4)  # chỉ số tham chiếu = giá trị hiện tại - thay đổi (điểm)
        if not sc.parse_exchange_ts(legacy):
            _stamp(legacy, payload)
        return legacy, "MI"
    if topic.startswith("quote") or any(k in payload for k in ("bids", "asks", "bid_prices", "ask_prices")):
        sym = sc.pick(payload, ["s", "symbol", "Symbol"]) or (topic.split(".", 1)[1] if "." in topic else "")
        if not sym:
            return None
        legacy.update({"RType": "X-QUOTE", "Symbol": str(sym).upper()})
        for side, name in (("bid", "Bid"), ("ask", "Ask")):
            lv = _levels_v3(payload, side)
            for i in range(1, sc.MAX_LEVELS + 1):  # bản tin là snapshot đầy đủ: mức vắng = trống (0), không điền từ snapshot cũ
                p, q = lv[i - 1] if i <= len(lv) else (0, 0)
                legacy[f"{name}Price{i}"], legacy[f"{name}Vol{i}"] = (p if p is not None else "x"), (q if q is not None else 0)
        _stamp(legacy, payload)
        return legacy, "X-QUOTE"
    if topic.startswith("trade") or {"total_volume", "quantity"} & payload.keys() or {"s", "p", "q"} <= payload.keys():
        sym = sc.pick(payload, ["s", "symbol", "Symbol"]) or (topic.split(".", 1)[1] if "." in topic else "")
        if not sym:
            return None
        legacy.update({"RType": "X-TRADE", "Symbol": str(sym).upper(),
                       "LastPrice": sc.pick(payload, ["p", "price"]), "LastVol": sc.pick(payload, ["q", "quantity"]),
                       "TotalVol": sc.pick(payload, ["v", "total_volume"])})
        _stamp(legacy, payload)
        return legacy, "X-TRADE"
    return None


def unwrap(raw: Any) -> tuple[dict, str]:
    """Bóc lớp vỏ {MessageType, Content} (Content thường là chuỗi JSON) -> (nội dung, loại)."""
    try:
        obj = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON hỏng: {e.msg}") from None
    if not isinstance(obj, dict):
        raise ParseError("Thông điệp không phải đối tượng JSON")
    v3 = _from_v3(obj)
    if v3 is not None:
        return v3
    inner = obj.get("Content", obj)
    if isinstance(inner, (str, bytes)):
        try:
            inner = json.loads(inner)
        except json.JSONDecodeError:
            raise ParseError("Content không phải JSON hợp lệ") from None
    if not isinstance(inner, dict):
        raise ParseError("Content không phải đối tượng")
    rtype = str(inner.get("RType") or obj.get("MessageType") or obj.get("RType") or "").upper()
    return inner, rtype


def classify(rtype: str) -> str:
    if "QUOTE" in rtype:
        return "quote"
    if "TRADE" in rtype:
        return "trade"
    if rtype.startswith("MI") or "INDEX" in rtype:
        return "index"
    return "other"


def parse_index(d: dict) -> m.IndexTick:
    f = sc.INDEX_FIELDS
    iid = sc.pick(d, f["index_id"])
    if iid is None:
        raise ParseError("Thiếu IndexId")
    return m.IndexTick(
        ts_exchange=sc.parse_exchange_ts(d), index_id=str(iid).upper(),
        index_value=sc.to_float(sc.pick(d, f["index_value"])),
        prior_value=sc.to_float(sc.pick(d, f["prior_value"])),
        change_pct=sc.to_float(sc.pick(d, f["change_pct"])),
        advances=sc.to_int(sc.pick(d, f["advances"])),
        declines=sc.to_int(sc.pick(d, f["declines"])),
        unchanged=sc.to_int(sc.pick(d, f["unchanged"])),
        total_value=sc.to_float(sc.pick(d, f["total_value"])),
        total_volume=sc.to_float(sc.pick(d, f["total_volume"])),
        session=sc.pick(d, f["session"]),
    )


def parse_trade(d: dict, price_scale: float = 1.0) -> m.TradeTick:
    f = sc.TRADE_FIELDS
    sym = sc.pick(d, f["symbol"])
    if not sym:
        raise ParseError("Thiếu Symbol")

    def px(key):
        v = sc.to_float(sc.pick(d, f[key]))
        return None if v is None else v * price_scale

    return m.TradeTick(
        ts_exchange=sc.parse_exchange_ts(d), symbol=str(sym).upper(),
        last_price=px("last_price"), last_vol=sc.to_float(sc.pick(d, f["last_vol"])),
        total_vol=sc.to_float(sc.pick(d, f["total_vol"])), total_val=sc.to_float(sc.pick(d, f["total_val"])),
        ref_price=px("ref_price"), ratio_change=sc.to_float(sc.pick(d, f["ratio_change"])),
        session=sc.pick(d, f["session"]),
    )


def _side_map(d: dict, side: str, price_scale: float) -> tuple[dict[int, m.Level], int]:
    """Trả (mức -> (giá, KL)) cho các mức CÓ KHOÁ trong thông điệp, và số mức không hợp lệ.
    Giá/KL = 0 hoặc chuỗi (ATO/ATC) nghĩa là mức trống."""
    out: dict[int, m.Level] = {}
    names = sc.SIDE_KEYS[side]
    for i in range(1, sc.MAX_LEVELS + 1):
        pk = [f"{n}Price{i}" for n in names]
        vk = [f"{n}Vol{i}" for n in names] + [f"{n}Qty{i}" for n in names]
        if not (sc.has_key(d, pk) or sc.has_key(d, vk)):
            continue
        p, q = sc.to_float(sc.pick(d, pk)), sc.to_float(sc.pick(d, vk))
        out[i] = (p * price_scale, q) if (p is not None and q is not None and p > 0 and q > 0) else (0.0, 0.0)
    return out, 0


def _contiguous(levels: dict[int, m.Level]) -> list[m.Level]:
    res: list[m.Level] = []
    for i in range(1, sc.MAX_LEVELS + 1):
        lv = levels.get(i)
        if not lv or lv[0] <= 0:
            break
        res.append(lv)
    return res


def parse_quote(d: dict, prev: m.QuoteSnap | None = None, price_scale: float = 1.0) -> m.QuoteSnap:
    sym = sc.pick(d, sc.QUOTE_FIELDS["symbol"])
    if not sym:
        raise ParseError("Thiếu Symbol")
    bid_map, _ = _side_map(d, "bid", price_scale)
    ask_map, _ = _side_map(d, "ask", price_scale)
    if not bid_map and not ask_map:  # dạng danh sách bids/asks: [[giá, KL], ...] hoặc [{p,q}]
        for key, target in (("bids", bid_map), ("asks", ask_map)):
            for i, lv in enumerate(d.get(key) or [], start=1):
                p, q = (lv if isinstance(lv, (list, tuple)) else (lv.get("p"), lv.get("q")))
                p, q = sc.to_float(p), sc.to_float(q)
                target[i] = (p * price_scale, q) if (p and q and p > 0 and q > 0) else (0.0, 0.0)
    partial = False
    if prev is not None:  # thông điệp cập nhật một phần: điền mức vắng khoá từ snapshot trước
        for i in range(1, sc.MAX_LEVELS + 1):
            for cur, old in ((bid_map, prev.bid_map), (ask_map, prev.ask_map)):
                if i not in cur and i in old and (bid_map or ask_map):
                    cur[i] = old[i]
                    partial = True
    bids, asks = _contiguous(bid_map), _contiguous(ask_map)
    session = sc.pick(d, sc.QUOTE_FIELDS["session"])
    if session and any(x in str(session).upper() for x in ("ATO", "ATC")):
        state = "auction"
    elif not bids or not asks:
        state = "incomplete"
    elif asks[0][0] < bids[0][0]:
        state = "crossed"
    else:
        state = "ok"
    return m.QuoteSnap(ts_exchange=sc.parse_exchange_ts(d), symbol=str(sym).upper(), bids=bids, asks=asks,
                       book_state=state, partial=partial, session=session, bid_map=bid_map, ask_map=ask_map)
