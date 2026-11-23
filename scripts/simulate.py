"""Sinh dữ liệu MÔ PHỎNG (source='simulated') vào DB riêng để demo/kiểm thử khi chưa có dữ liệu thật."""
import argparse
from datetime import datetime

import _common  # noqa: F401
from vmap.config import ROOT, VN_TZ, load_settings
from vmap.data.collector import Collector
from vmap.data.db import Database
from vmap.data.simulator import simulate
from vmap.logging_setup import setup_logging


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--step", type=int, default=30, help="chu kỳ snapshot (giây)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--db", default=str(ROOT / "data" / "vmap_sim.db"))
    ap.add_argument("--truth", default=str(ROOT / "data" / "stress_truth.json"))
    ap.add_argument("--no-defects", action="store_true")
    a = ap.parse_args()
    setup_logging()
    s = load_settings()
    s.store_raw = False
    db = Database(a.db)
    c = Collector(db, s, "simulated")
    st = simulate(c, s, a.days, a.step, a.seed, datetime.now(VN_TZ).date(), not a.no_defects, a.truth)
    print("Xong:", st)
    print("Chất lượng:", dict(c.q.counts))
    print(f"DB: {a.db}  (mọi bản ghi gắn source='simulated')")


if __name__ == "__main__":
    main()
