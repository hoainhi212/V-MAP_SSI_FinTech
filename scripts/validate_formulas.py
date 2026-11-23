"""Sinh bảng đối chiếu 6.2: giá trị Python (pipeline) vs giá trị tính độc lập từng bước.

In kèm biểu thức số học để bạn TỰ tính tay/Excel các bản ghi đã chọn rồi dán vào báo cáo.
"""
import argparse
import json
import math

import _common  # noqa: F401
from vmap.config import load_settings
from vmap.data.db import Database
from vmap.finance import indicators as fi


def independent(bids, asks, n_obi, n_depth):
    """Cài đặt lần hai, viết rời bằng vòng lặp thuần (không dùng hàm trong indicators)."""
    b = sum(bids[i][1] for i in range(min(n_obi, len(bids))))
    a = sum(asks[i][1] for i in range(min(n_obi, len(asks))))
    sp = asks[0][0] - bids[0][0]
    mid = (asks[0][0] + bids[0][0]) / 2
    db = sum(bids[i][0] * bids[i][1] for i in range(min(n_depth, len(bids))))
    da = sum(asks[i][0] * asks[i][1] for i in range(min(n_depth, len(asks))))
    return {"obi": (b - a) / (b + a), "spread_bps": sp / mid * 1e4, "depth_total": db + da,
            "expr_obi": f"({b:,.0f} - {a:,.0f}) / ({b:,.0f} + {a:,.0f})",
            "expr_spread": f"({asks[0][0]:,.0f} - {bids[0][0]:,.0f}) / (({asks[0][0]:,.0f} + {bids[0][0]:,.0f})/2) * 10000"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--source", default="live")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    s = load_settings()
    db = Database(a.db or s.db_path)
    q = db.read("SELECT id, ts_exchange, symbol, bid_levels, ask_levels FROM quotes WHERE source=? AND book_state='ok' "
                "ORDER BY RANDOM() LIMIT ?", (a.source, a.n))
    print(f"{'Bản ghi':<20}{'Chỉ báo':<12}{'Python':>22}{'Độc lập':>22}{'Sai lệch':>12}")
    worst = 0.0
    for r in q.itertuples():
        bids, asks = json.loads(r.bid_levels), json.loads(r.ask_levels)
        m = fi.book_metrics(bids, asks, s.obi_levels, s.depth_levels)
        ind = independent(bids, asks, s.obi_levels, s.depth_levels)
        tag = f"{r.symbol} {r.ts_exchange[11:19]}"
        for k in ("obi", "spread_bps", "depth_total"):
            diff = abs(m[k] - ind[k])
            worst = max(worst, diff / (abs(ind[k]) or 1))
            print(f"{tag:<20}{k:<12}{m[k]:>22,.6f}{ind[k]:>22,.6f}{diff:>12.2e}")
        print(f"   tính tay OBI    = {ind['expr_obi']}")
        print(f"   tính tay Spread = {ind['expr_spread']}")
    print(f"\nSai lệch tương đối lớn nhất: {worst:.2e}", "(đạt)" if worst < 1e-9 else "(KIỂM TRA LẠI)")


if __name__ == "__main__":
    main()
