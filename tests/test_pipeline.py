import json
import tempfile
from datetime import date

import pandas as pd

from vmap.analytics import aggregate as ag
from vmap.analytics.alerts import AlertConfig, build_alerts, walk_forward
from vmap.analytics.anomaly import rolling_z
from vmap.config import Settings
from vmap.data.collector import Collector
from vmap.data.db import Database
from vmap.data.simulator import simulate

S = Settings(symbols=["ACB", "VCB", "HPG", "FPT"], store_raw=False)


def msg(**kw):
    c = {"RType": "X-QUOTE", "TradingDate": "20/11/2026", "Time": "10:15:30", "Symbol": "ACB", "RefPrice": 25000}
    for i in range(1, 4):
        c.update({f"BidPrice{i}": 25000 - 50 * (i - 1), f"BidVol{i}": 1000, f"AskPrice{i}": 25050 + 50 * (i - 1), f"AskVol{i}": 1000})
    c.update(kw)
    return json.dumps({"MessageType": "Quote", "Content": json.dumps(c)})


def test_duplicate_invalid_ignored_and_source_guard():
    col = Collector(Database(":memory:"), S, "live")
    assert col.handle_message(msg()) == "stored"
    assert col.handle_message(msg()) == "duplicate"
    assert col.handle_message("{not json") == "invalid"
    assert col.handle_message(msg(Symbol="ZZZ")) == "ignored"        # ngoài rổ theo dõi
    assert col.q.counts["valid"] == 1 and col.q.counts["duplicate"] == 1 and col.q.counts["invalid"] == 1
    try:
        Collector(Database(":memory:"), S, "demo")
        assert False, "phải từ chối source lạ"
    except ValueError:
        pass


def test_late_message_flagged():
    db = Database(":memory:")
    col = Collector(db, S, "live")
    col.handle_message(msg(Time="10:15:30"))
    col.handle_message(msg(Time="10:14:00", BidVol1=2000))           # lùi 90s => đến muộn
    assert col.q.counts["late"] == 1
    assert db.read("SELECT SUM(is_late) n FROM quotes").n[0] == 1


def test_rolling_z_has_no_lookahead():
    s = pd.Series([10.0, 10.5, 9.5, 10.2, 9.8] * 4 + [100.0] + [10.0] * 5)
    z = rolling_z(s, window=10, min_periods=5)
    assert z.iloc[20] > 5                        # cú nhảy được phát hiện ngay tại thời điểm xảy ra
    s2 = s.copy()
    s2.iloc[25] = 9999.0                         # sửa dữ liệu TƯƠNG LAI ...
    pd.testing.assert_series_equal(z.iloc[:25], rolling_z(s2, 10, 5).iloc[:25])  # ... không được đổi z quá khứ


def test_rolling_z_constant_series_does_not_explode():
    s = pd.Series([11.76] * 30 + [12.0])         # spread rời rạc gần như hằng số, nhích nhẹ 2%
    assert abs(rolling_z(s, 30, 10).iloc[-1]) < 2.0


def test_alert_hysteresis_and_persistence():
    m = pd.date_range("2026-11-16 09:15", periods=12, freq="min", tz="Asia/Ho_Chi_Minh")
    n = [0, 1, 0, 1, 2, 1, 0, 0, 0, 0, 1, 0]
    df = pd.DataFrame({"symbol": "ACB", "session_date": "2026-11-16", "minute": m, "n_flags": n,
                       "c_spread": True, "c_depth": False, "c_sell": False, "spread_bps": 30., "spread_p95": 20.,
                       "z_spread_bps": 3., "depth_total": 1e9, "depth_p05": 1e9, "z_depth_total": 0., "wobi": 0.})
    a = build_alerts(df, AlertConfig())
    assert len(a) == 1                          # tín hiệu lẻ 1 phút bị lọc, chỉ còn 1 cảnh báo
    r = a.iloc[0]
    assert r.severity == "WARNING" and r.start_ts == m[3] and r.end_ts == m[5] and r.closed_reason == "cleared"
    assert "Spread" in r.reason


def test_end_to_end_simulated_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(f"{tmp}/t.db")
        col = Collector(db, S, "simulated")
        st = simulate(col, S, days=6, step_sec=60, seed=11, end_date=date(2026, 11, 20))
        assert st["days"] == 6 and col.q.counts["valid"] > 5000
        assert set(db.sources()) == {"simulated"}
        book = ag.build_book_1m(db, "simulated", S)
        assert not book.empty and book["spread_bps"].min() > 0
        assert book["obi"].between(-1, 1).all()
        idx = ag.build_index_1m(db, "simulated", "VN30")
        assert idx["mbi"].between(-1, 1).all()
        flags, alerts, thr = walk_forward(book, AlertConfig(min_obs=30), "simulated")
        # phiên đầu chưa đủ dữ liệu hiệu chỉnh nên KHÔNG được có đánh giá
        assert flags["session_date"].min() > book["session_date"].min()
        db.close()


def test_walk_forward_without_enough_sessions_returns_no_alerts():
    book = pd.DataFrame({"symbol": ["ACB"] * 3, "minute": pd.date_range("2026-11-16 09:15", periods=3, freq="min", tz="Asia/Ho_Chi_Minh"),
                         "session_date": "2026-11-16", "spread_bps": [10., 11., 12.], "depth_total": [1e9] * 3,
                         "wobi": [0., 0., 0.]})
    flags, alerts, _ = walk_forward(book)
    assert flags.empty and alerts.empty
