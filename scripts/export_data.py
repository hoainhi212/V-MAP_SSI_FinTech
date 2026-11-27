"""Xuất DỮ LIỆU THẬT ra CSV để nộp kèm báo cáo (đề yêu cầu có 'file dữ liệu').
Chạy ở thư mục gốc dự án:
    /opt/anaconda3/envs/vmap/bin/python scripts/export_data.py
Không chứa khóa hay token. Mặc định chỉ xuất bản ghi source='live'.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from vmap.analytics import aggregate as ag  # noqa: E402
from vmap.analytics.alerts import AlertConfig, walk_forward  # noqa: E402
from vmap.config import load_settings  # noqa: E402
from vmap.data.db import Database  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--source", default="live", choices=["live", "simulated"])
    ap.add_argument("--out", default="data_export")
    ap.add_argument("--sample", type=int, default=20000, help="số dòng sổ lệnh/giao dịch chuẩn hóa xuất kèm (lấy cách đều)")
    ap.add_argument("--min-train", type=int, default=3, help="số phiên tối thiểu để hiệu chỉnh ngưỡng cảnh báo")
    a = ap.parse_args()
    s = load_settings()
    db = Database(a.db or s.db_path)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    src = a.source
    enc = "utf-8-sig"  # mở thẳng bằng Excel không lỗi tiếng Việt

    book = ag.build_book_1m(db, src, s)
    idx = ag.build_index_1m(db, src, s.index_code)
    book.round(6).to_csv(out / f"book_1m_{src}.csv", index=False, encoding=enc)
    idx.round(6).to_csv(out / f"index_1m_{src}.csv", index=False, encoding=enc)
    _, alerts, _ = walk_forward(book, AlertConfig(min_train_sessions=a.min_train), src)
    alerts.to_csv(out / f"alerts_{src}.csv", index=False, encoding=enc)

    q = db.read("SELECT ts_exchange, symbol, bid_levels, ask_levels FROM quotes WHERE source=? AND book_state='ok' ORDER BY id", (src,))
    if len(q) > a.sample:
        q = q.iloc[:: max(1, len(q) // a.sample)]
    rows = []
    for r in q.itertuples(index=False):
        b, k = json.loads(r.bid_levels), json.loads(r.ask_levels)
        row = {"ts_exchange": r.ts_exchange, "symbol": r.symbol}
        for i in range(3):
            row[f"bid{i+1}_price"], row[f"bid{i+1}_vol"] = (b[i] if i < len(b) else (None, None))
            row[f"ask{i+1}_price"], row[f"ask{i+1}_vol"] = (k[i] if i < len(k) else (None, None))
        rows.append(row)
    pd.DataFrame(rows).to_csv(out / f"quotes_sample_{src}.csv", index=False, encoding=enc)
    t = db.read("SELECT ts_exchange, symbol, last_price, last_vol, total_vol FROM trades WHERE source=? ORDER BY id", (src,))
    if len(t) > a.sample:
        t = t.iloc[:: max(1, len(t) // a.sample)]
    t.to_csv(out / f"trades_sample_{src}.csv", index=False, encoding=enc)

    sessions = book["session_date"].nunique() if len(book) else 0
    (out / "README.txt").write_text(
        f"Dữ liệu xuất từ V-MAP (nguồn: {src}). Không chứa khóa truy cập.\n"
        f"Số phiên có chỉ báo: {sessions}. Múi giờ: Asia/Ho_Chi_Minh (UTC+7).\n"
        "book_1m: chỉ báo sổ lệnh theo phút (obi, wobi, spread_bps, depth_*) trong phiên khớp lệnh liên tục.\n"
        "index_1m: VN30 theo phút (index_value, ret, mbi, regime, value_ratio).\n"
        "alerts: danh sách cảnh báo (walk-forward). quotes/trades_sample: mẫu cách đều từ dữ liệu chuẩn hóa.\n",
        encoding="utf-8")
    print(f"Đã xuất vào {out}/ ({sessions} phiên):")
    for f in sorted(out.iterdir()):
        print(f"  {f.name:32s} {f.stat().st_size/1024:8.1f} KB")


if __name__ == "__main__":
    main()
