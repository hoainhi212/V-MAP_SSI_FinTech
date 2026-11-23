"""Tạo số liệu cho Chương 6 của báo cáo (mục 6.2-6.4) trực tiếp từ DB. Số liệu điền báo cáo lấy từ đây."""
import argparse
import json

import _common  # noqa: F401
import numpy as np
import pandas as pd

from vmap.analytics import aggregate as ag
from vmap.analytics.alerts import AlertConfig, walk_forward
from vmap.config import load_settings
from vmap.data.db import Database


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--source", default="live", choices=["live", "simulated"])
    ap.add_argument("--truth", default=None, help="JSON nhãn giai đoạn căng thẳng (chỉ có ở dữ liệu mô phỏng)")
    ap.add_argument("--out", default="report/metrics.json")
    a = ap.parse_args()
    s = load_settings()
    db = Database(a.db or s.db_path)
    src = a.source
    out: dict = {"source": src}
    if src == "simulated":
        out["WARNING"] = "DỮ LIỆU MÔ PHỎNG - chỉ kiểm tra quy trình, không phải bằng chứng thị trường thật"

    # 6.3 hoạt động thực tế
    tab = {t: int(db.read(f"SELECT COUNT(*) n FROM {t} WHERE source=?", (src,)).n[0])
           for t in ("quotes", "trades", "index_ticks")}
    ev = db.read("SELECT event_type, detail FROM events WHERE source=?", (src,))
    lat = pd.concat([db.read(f"SELECT latency_ms FROM {t} WHERE source=? AND latency_ms IS NOT NULL", (src,))
                     for t in ("quotes", "trades", "index_ticks")])["latency_ms"]
    late = int(sum(db.read(f"SELECT COUNT(*) n FROM {t} WHERE source=? AND is_late=1", (src,)).n[0]
                   for t in ("quotes", "trades", "index_ticks")))
    rec = ev[ev.event_type == "reconnected"]["detail"].str.extract(r"duration_sec=([\d.]+)")[0].astype(float)
    book = ag.build_book_1m(db, src, s)
    out["records_stored"] = tab
    out["sessions"] = int(book["session_date"].nunique()) if not book.empty else 0
    out["disconnects"] = int((ev.event_type == "disconnect").sum())
    out["reconnect_sec_median"] = None if rec.empty else float(rec.median())
    out["latency_ms_median"] = None if lat.empty else float(lat.median())
    out["latency_ms_p95"] = None if lat.empty else float(lat.quantile(0.95))
    out["late_records"] = late
    q = db.read("SELECT book_state, COUNT(*) n FROM quotes WHERE source=? GROUP BY book_state", (src,))
    out["quote_book_states"] = dict(zip(q.book_state, q.n.astype(int)))
    out["note_latency"] = "Mốc thời gian sàn có độ phân giải 1 giây nên độ trễ chỉ có ý nghĩa ở mức ~giây."

    # RQ1: đồng thuận giữa lợi suất chỉ số và MBI
    idx = ag.build_index_1m(db, src, s.index_code)
    if not idx.empty:
        d = idx.dropna(subset=["ret", "mbi"])
        same = (np.sign(d["ret"]) == np.sign(d["mbi"]))[(d["ret"].abs() > 0.001) & (d["mbi"].abs() >= 0.2)]
        out["RQ1"] = {"minutes": int(len(d)), "concordance_rate": float(same.mean()) if len(same) else None,
                      "divergence_minutes": int(d["divergence"].sum()),
                      "spearman_ret_mbi": float(d["ret"].corr(d["mbi"], method="spearman")),
                      "regime_counts": d["regime"].value_counts().to_dict()}
        bt = ag.breadth_from_trades(db, src, s.symbols)
        if not bt.empty:
            m = d.merge(bt, on="minute").dropna(subset=["mbi", "mbi_calc"])
            out["breadth_crosscheck"] = {"n": int(len(m)),
                                         "mean_abs_diff": float((m["mbi"] - m["mbi_calc"]).abs().mean()),
                                         "corr": float(m["mbi"].corr(m["mbi_calc"]))}
    # RQ2: tương quan giữa OBI, spread, depth
    if not book.empty:
        c = book[["obi", "wobi", "spread_bps", "depth_total"]].corr(method="spearman")
        out["RQ2_spearman"] = c.round(3).to_dict()
        flags, alerts, _ = walk_forward(book, AlertConfig(), src)
        out["alerts"] = {"total": int(len(alerts)),
                         "by_severity": alerts["severity"].value_counts().to_dict() if len(alerts) else {},
                         "evaluated_sessions": int(flags["session_date"].nunique()) if len(flags) else 0}
        if a.truth and len(alerts):
            truth = json.load(open(a.truth, encoding="utf-8"))
            tr_eval = [t for t in truth if t["date"] in set(flags["session_date"])]
            out["synthetic_truth"] = {"episodes_in_evaluated_sessions": len(tr_eval),
                                      "note": "Chỉ là kiểm tra quy trình trên dữ liệu có nhãn nhân tạo."}
            hits = 0
            for t in tr_eval:
                st, en = pd.Timestamp(t["start"]), pd.Timestamp(t["end"])
                sub = alerts[(alerts.symbol == t["symbol"]) & (pd.to_datetime(alerts.end_ts) >= st)
                             & (pd.to_datetime(alerts.start_ts) <= en)]
                hits += len(sub) > 0
            out["synthetic_truth"]["detected"] = int(hits)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
