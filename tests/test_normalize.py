import json

import pytest

from vmap.data import normalize as nz


def wrap(content, mt="Quote"):
    return json.dumps({"MessageType": mt, "Content": json.dumps(content)})


def quote(**kw):
    c = {"RType": "X-QUOTE", "TradingDate": "20/11/2026", "Time": "10:15:30", "Symbol": "acb", "RefPrice": 25000}
    for i in range(1, 4):
        c.update({f"BidPrice{i}": 25000 - 50 * (i - 1), f"BidVol{i}": 1000 * i,
                  f"AskPrice{i}": 25050 + 50 * (i - 1), f"AskVol{i}": 500 * i})
    c.update(kw)
    return c


def test_unwrap_nested_content_and_classify():
    inner, rtype = nz.unwrap(wrap(quote()))
    assert nz.classify(rtype) == "quote" and inner["Symbol"] == "acb"


def test_corrupt_json_raises():
    with pytest.raises(nz.ParseError):
        nz.unwrap('{"Content": "{bad')
    with pytest.raises(nz.ParseError):
        nz.unwrap("[1,2]")


def test_quote_ok_and_timezone():
    inner, _ = nz.unwrap(wrap(quote()))
    q = nz.parse_quote(inner)
    assert q.symbol == "ACB" and q.book_state == "ok" and len(q.bids) == 3 and q.asks[0] == (25050.0, 500.0)
    assert q.ts_exchange.utcoffset().total_seconds() == 7 * 3600  # Asia/Ho_Chi_Minh


def test_quote_invalid_price_string_is_incomplete_not_zero():
    inner, _ = nz.unwrap(wrap(quote(BidPrice1="ATO")))
    q = nz.parse_quote(inner)
    assert q.bids == [] and q.book_state == "incomplete"  # không được biến 'ATO' thành 0 rồi tính tiếp


def test_quote_crossed_and_auction():
    inner, _ = nz.unwrap(wrap(quote(AskPrice1=24000)))
    assert nz.parse_quote(inner).book_state == "crossed"
    inner, _ = nz.unwrap(wrap(quote(TradingSession="ATC")))
    assert nz.parse_quote(inner).book_state == "auction"


def test_quote_partial_update_carries_previous_levels():
    inner, _ = nz.unwrap(wrap(quote()))
    first = nz.parse_quote(inner)
    d = quote()
    for k in ("BidPrice3", "BidVol3", "AskPrice3", "AskVol3"):
        d.pop(k)
    second = nz.parse_quote(d, prev=first)
    assert second.partial and len(second.bids) == 3 and len(second.asks) == 3


def test_index_alias_short_names():
    t = nz.parse_index({"RType": "MI", "IndexId": "VN30", "v": 1800.5, "cr": 0.5, "adv": 20, "dec": 8, "nc": 2,
                        "TradingDate": "20/11/2026", "Time": "10:00:00"})
    assert (t.index_value, t.advances, t.declines, t.unchanged) == (1800.5, 20, 8, 2)


def test_trade_missing_price_gives_none():
    t = nz.parse_trade({"Symbol": "VCB", "LastPrice": "", "LastVol": 100, "TradingDate": "20/11/2026", "Time": "09:20:00"})
    assert t.last_price is None and t.last_vol == 100
