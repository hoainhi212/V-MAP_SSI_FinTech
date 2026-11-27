"""Bộ mô phỏng thông điệp theo định dạng SSI -- CHỈ để kiểm thử và demo khi chưa có dữ liệu thật.

Mọi bản ghi sinh ra đều đi qua đúng Collector như dữ liệu thật nhưng được gắn source='simulated'.
Không được dùng kết quả mô phỏng như bằng chứng về thị trường thật (đề bài yêu cầu công bố rõ).
Có chủ đích chèn lỗi (trùng, thiếu, hỏng JSON, đến muộn, quote cập nhật một phần, mất kết nối)
để kiểm thử lớp chất lượng dữ liệu, và chèn các "giai đoạn căng thẳng thanh khoản" có nhãn làm sự thật nền.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

import numpy as np

from ..config import CONTINUOUS_SESSIONS, VN_TZ, Settings
from ..finance.indicators import tick_size_hose
from .collector import Collector


def _weekdays_before(end: date, n: int) -> list[date]:
    out, d = [], end
    while len(out) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return sorted(out)


def _times(d: date, step: int) -> list[datetime]:
    res = []
    for a, b in CONTINUOUS_SESSIONS:
        t = datetime.combine(d, a, tzinfo=VN_TZ)
        end = datetime.combine(d, b, tzinfo=VN_TZ)
        while t <= end:
            res.append(t)
            t += timedelta(seconds=step)
    return res


def _quote_msg(sym, ts, ref, bid1, ask1, tick, vol_b, vol_a, session="LO"):
    c = {"RType": "X-QUOTE", "TradingDate": ts.strftime("%d/%m/%Y"), "Time": ts.strftime("%H:%M:%S"),
         "Symbol": sym, "RefPrice": ref, "TradingSession": session}
    for i in range(1, 11):
        c[f"BidPrice{i}"], c[f"BidVol{i}"] = bid1 - (i - 1) * tick, int(vol_b[i - 1])
        c[f"AskPrice{i}"], c[f"AskVol{i}"] = ask1 + (i - 1) * tick, int(vol_a[i - 1])
    return c


def simulate(collector: Collector, settings: Settings, days: int = 10, step_sec: int = 30, seed: int = 7,
             end_date: date | None = None, defects: bool = True, truth_path: str | None = None) -> dict:
    assert collector.source == "simulated", "Chỉ cho phép mô phỏng vào Collector có source='simulated'"
    rng = np.random.default_rng(seed)
    syms = settings.symbols
    end_date = end_date or datetime.now(VN_TZ).date()
    price = {s: float(rng.choice([18, 25, 32, 45, 60, 85, 110]) * 1000) for s in syms}
    beta = {s: float(rng.uniform(0.6, 1.4)) for s in syms}
    base_vol = {s: float(rng.lognormal(10.3, 0.4)) for s in syms}  # ~30k cp/mức
    truth, stats = [], dict(messages=0, days=0)

    def send(content: dict, wrapper="Trade", recv=None, corrupt=False):
        raw = json.dumps({"MessageType": wrapper, "Content": json.dumps(content)})
        if corrupt:
            raw = raw[:-7]
        stats["messages"] += 1
        return collector.handle_message(raw, recv), raw

    for d in _weekdays_before(end_date + timedelta(days=1), days):
        ts_list = _times(d, step_sec)
        n = len(ts_list)
        refs = dict(price)
        mkt = np.cumsum(rng.normal(rng.normal(0, 0.005) / n, 0.0005, n))
        idio = {s: np.cumsum(rng.normal(0, 0.0006, n)) for s in syms}
        stress = {}
        for s in syms:
            if rng.random() < 0.2:
                st = int(rng.integers(20, n - 60))
                ln = int(rng.integers(8, 20) * 60 / step_sec)
                stress[s] = (st, st + ln, int(rng.integers(3, 6)), float(rng.uniform(0.25, 0.4)))
                truth.append(dict(symbol=s, date=d.isoformat(), start=ts_list[st].isoformat(),
                                  end=ts_list[min(st + ln, n - 1)].isoformat()))
        cum_vol, cum_val = {s: 0.0 for s in syms}, {s: 0.0 for s in syms}
        gap_until, gaps = None, sorted(rng.integers(30, n - 30, 2).tolist()) if defects else []
        for k, ts in enumerate(ts_list):
            recv_base = ts + timedelta(seconds=float(rng.lognormal(-1.2, 0.8)))
            if gaps and k == gaps[0]:
                glen = int(rng.integers(30, 90))
                gap_until = ts + timedelta(seconds=glen)
                collector.event("disconnect", "simulated", ts)
                collector.event("reconnected", f"duration_sec={glen + 2:.1f}", gap_until)
                gaps.pop(0)
            if gap_until and ts < gap_until:
                continue  # mất tin trong lúc mất kết nối
            adv = dec = unch = 0
            for s in syms:
                px = refs[s] * (1 + beta[s] * mkt[k] + idio[s][k])
                px = min(max(px, refs[s] * 0.93), refs[s] * 1.07)
                tick = tick_size_hose(px)
                px = round(px / tick) * tick
                price[s] = px
                adv, dec = adv + (px > refs[s]), dec + (px < refs[s])
                unch += px == refs[s]
                k_ticks, depth_f, sell_f = 1, 1.0, 1.0
                if s in stress and stress[s][0] <= k <= stress[s][1]:
                    _, _, k_ticks, depth_f = stress[s]
                    sell_f = 2.5
                bid1 = np.floor(px / tick) * tick
                ask1 = bid1 + k_ticks * tick
                vb = base_vol[s] * depth_f * rng.lognormal(0, 0.35, 10) * np.linspace(1, 1.6, 10)
                va = base_vol[s] * depth_f * sell_f * rng.lognormal(0, 0.35, 10) * np.linspace(1, 1.6, 10)
                vb, va = np.round(vb, -2), np.round(va, -2)
                q = _quote_msg(s, ts, refs[s], bid1, ask1, tick, vb, va)
                recv, corrupt = recv_base, False
                if defects:
                    r = rng.random()
                    if r < 0.003:
                        q["BidPrice1"] = "ATO"           # giá không hợp lệ
                    elif r < 0.006:
                        corrupt = True                   # JSON hỏng
                    elif r < 0.011:                      # quote cập nhật một phần
                        for i in range(4, 11):
                            for key in ("BidPrice", "BidVol", "AskPrice", "AskVol"):
                                q.pop(f"{key}{i}", None)
                    elif r < 0.016:                      # đến muộn: mốc thời gian lùi hơn một chu kỳ
                        late = ts - timedelta(seconds=step_sec + 10)
                        q["Time"] = late.strftime("%H:%M:%S")
                out, raw = send(q, "Quote", recv, corrupt)
                if defects and rng.random() < 0.005:     # gửi trùng
                    collector.handle_message(raw, recv)
                    stats["messages"] += 1
                if rng.random() < 0.8:
                    lv = int(rng.integers(1, 30) * 100)
                    cum_vol[s] += lv
                    cum_val[s] += lv * px
                    send({"RType": "X-TRADE", "TradingDate": ts.strftime("%d/%m/%Y"),
                          "Time": ts.strftime("%H:%M:%S"), "Symbol": s, "LastPrice": px, "LastVol": lv,
                          "TotalVol": cum_vol[s], "TotalVal": cum_val[s], "RefPrice": refs[s],
                          "RatioChange": round((px / refs[s] - 1) * 100, 2), "TradingSession": "LO"},
                         "Trade", recv_base)
            idx_ret = float(np.mean([price[s] / refs[s] - 1 for s in syms]))
            send({"RType": "MI", "IndexId": settings.index_code, "TradingDate": ts.strftime("%d/%m/%Y"),
                  "Time": ts.strftime("%H:%M:%S"), "IndexValue": round(1800 * (1 + idx_ret), 2),
                  "PriorIndexValue": 1800.0, "RatioChange": round(idx_ret * 100, 3),
                  "Advances": int(adv), "Declines": int(dec), "NoChanges": int(unch),
                  "TotalValue": sum(cum_val.values()), "TotalQtty": sum(cum_vol.values()),
                  "TradingSession": "LO"}, "Index", recv_base)
        stats["days"] += 1
        collector.flush()
    if truth_path:
        json.dump(truth, open(truth_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    stats["stress_episodes"] = len(truth)
    return stats
