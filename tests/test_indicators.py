"""Kiểm thử công thức bằng số liệu tính tay (xem chú thích từng ca)."""
import math

import pytest

from vmap.finance import indicators as fi

BIDS = [(100.0, 10), (99.0, 20), (98.0, 30)]
ASKS = [(101.0, 5), (102.0, 5), (103.0, 10)]


def test_mbi_by_hand():
    # (18 - 9) / (18 + 9 + 3) = 0,3
    assert fi.market_breadth(18, 9, 3) == pytest.approx(0.3)
    assert fi.market_breadth(0, 0, 0) is None
    assert fi.market_breadth(None, 5, 1) is None
    assert fi.market_breadth(30, 0, 0) == 1.0 and fi.market_breadth(0, 30, 0) == -1.0


def test_index_return():
    assert fi.index_return(1818.0, 1800.0) == pytest.approx(0.01)
    assert fi.index_return(None, 1800.0) is None and fi.index_return(1800.0, 0) is None


def test_obi_by_hand():
    # Bid 3 mức = 60, Ask 3 mức = 20 -> (60-20)/80 = 0,5 ; chỉ 1 mức: (10-5)/15
    assert fi.obi(BIDS, ASKS, 3) == pytest.approx(0.5)
    assert fi.obi(BIDS, ASKS, 1) == pytest.approx(5 / 15)
    assert fi.obi([], ASKS) is None


def test_wobi_by_hand():
    # w=1/i: bid = 10 + 20/2 + 30/3 = 30 ; ask = 5 + 5/2 + 10/3 = 10,8333 ; (30-10,8333)/(40,8333)
    assert fi.wobi(BIDS, ASKS) == pytest.approx((30 - 65 / 6) / (30 + 65 / 6))


def test_spread():
    assert fi.spread_abs(BIDS, ASKS) == 1.0
    assert fi.spread_bps(BIDS, ASKS) == pytest.approx(1 / 100.5 * 1e4)
    assert fi.spread_abs([(101, 1)], [(100, 1)]) is None  # sổ lệnh đảo => không hợp lệ


def test_tick_size_and_ticks():
    assert fi.tick_size_hose(9_990) == 10 and fi.tick_size_hose(25_000) == 50 and fi.tick_size_hose(60_000) == 100
    assert fi.spread_ticks([(25_000, 1)], [(25_100, 1)]) == pytest.approx(2.0)


def test_depth_and_ratio():
    # Bid: 100*10 + 99*20 + 98*30 = 5920 ; Ask: 101*5 + 102*5 + 103*10 = 2045
    assert fi.depth_notional(BIDS, 3) == 5920 and fi.depth_notional(ASKS, 3) == 2045
    assert fi.depth_ratio(5920, 2045) == pytest.approx(5920 / 2045)
    assert fi.depth_ratio(5920, 0) is None


def test_book_metrics_bundle_and_invalid():
    m = fi.book_metrics(BIDS, ASKS, 3, 3)
    assert m["depth_total"] == 7965 and m["obi"] == pytest.approx(0.5)
    bad = fi.book_metrics([], ASKS)
    assert all(v is None for v in bad.values())


def test_regime_classification():
    assert fi.classify_regime(0.01, 0.5) == "Tăng đồng thuận"
    assert fi.classify_regime(-0.01, -0.5) == "Giảm đồng thuận"
    assert fi.is_divergence(fi.classify_regime(0.01, -0.4))   # chỉ số tăng nhưng độ rộng âm
    assert fi.is_divergence(fi.classify_regime(-0.01, 0.4))
    assert fi.classify_regime(0.0002, 0.05) == "Trung tính / giằng co"
    assert fi.classify_regime(None, 0.1) == "Chưa đủ dữ liệu"
