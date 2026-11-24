"""Tin FastConnect V3: khung {topic, data} (khoá ngắn t/s/p/q/si/v, bids/asks là cặp [giá, KL]) và dạng dataclass."""
import json

from vmap.config import Settings
from vmap.data import normalize as nz
from vmap.data.collector import Collector
from vmap.data.db import Database


def parse(msg):
    inner, rtype = nz.unwrap(json.dumps(msg))
    return inner, nz.classify(rtype)


def test_v3_trade_wire():
    inner, kind = parse({"topic": "trade.FPT", "data": {"t": "09:30:01", "s": "FPT", "p": 135500, "q": "1000.0", "si": "B", "v": 250000}})
    t = nz.parse_trade(inner)
    assert kind == "trade" and t.symbol == "FPT" and t.last_price == 135500 and t.last_vol == 1000 and t.total_vol == 250000
    assert t.ts_exchange is not None and t.ts_exchange.utcoffset().total_seconds() == 7 * 3600


def test_v3_trade_ato_price_is_none():
    inner, _ = parse({"topic": "trade.FPT", "data": {"t": "09:05:00", "s": "FPT", "p": "ATO", "q": "2000"}})
    assert nz.parse_trade(inner).last_price is None


def test_v3_quote_wire_and_dataclass_forms():
    wire = {"topic": "quote.FPT", "data": {"t": "09:30:02", "s": "FPT", "bids": [[135500, 500], [135400, 1200]], "asks": [[135600, 800]]}}
    dc = {"trading_time": "09:30:02", "symbol": "FPT", "bid_prices": [135500, 135400], "bid_volumes": [500, 1200],
          "ask_prices": [135600], "ask_volumes": [800]}
    for msg in (wire, dc):
        inner, kind = parse(msg)
        q = nz.parse_quote(inner)
        assert kind == "quote" and q.book_state == "ok"
        assert q.bids == [(135500.0, 500.0), (135400.0, 1200.0)] and q.asks == [(135600.0, 800.0)]


def test_v3_quote_missing_levels_are_empty_not_carried_over():
    full, _ = parse({"topic": "quote.FPT", "data": {"t": "09:30:02", "s": "FPT", "bids": [[100, 1], [99, 1], [98, 1]], "asks": [[101, 1]]}})
    first = nz.parse_quote(full)
    shorter, _ = parse({"topic": "quote.FPT", "data": {"t": "09:30:03", "s": "FPT", "bids": [[100, 1]], "asks": [[101, 1]]}})
    second = nz.parse_quote(shorter, prev=first)
    assert len(second.bids) == 1 and not second.partial


def test_v3_index_and_empty_side_incomplete():
    inner, kind = parse({"topic": "indexsummary.VN30", "data": {"indexValue": 1786.84, "advances": 18, "declines": 9}})
    t = nz.parse_index(inner)
    assert kind == "index" and t.index_id == "VN30" and t.index_value == 1786.84 and (t.advances, t.declines) == (18, 9)
    inner, _ = parse({"topic": "quote.FPT", "data": {"t": "09:30:02", "s": "FPT", "bids": [[100, 1]], "asks": []}})
    assert nz.parse_quote(inner).book_state == "incomplete"


def test_v3_ack_and_legacy_still_work_through_collector():
    s = Settings(symbols=["FPT"], store_raw=False)
    col = Collector(Database(":memory:"), s, "live")
    assert col.handle_message(json.dumps({"topic": "trade.FPT", "data": {"t": "09:30:01", "s": "FPT", "p": 1, "q": 1, "v": 1}})) == "stored"
    assert col.handle_message(json.dumps({"topic": "quote.FPT", "data": {"t": "09:30:01", "s": "FPT", "bids": [[1, 1]], "asks": [[2, 1]]}})) == "stored"
    assert col.handle_message(json.dumps({"method": "subscribe", "result": "ok"})) == "ignored"
    legacy = json.dumps({"MessageType": "Trade", "Content": json.dumps({"RType": "X-TRADE", "Symbol": "FPT", "LastPrice": 1, "LastVol": 1,
                                                                         "TradingDate": "20/11/2026", "Time": "10:00:00"})})
    assert col.handle_message(legacy) == "stored"
