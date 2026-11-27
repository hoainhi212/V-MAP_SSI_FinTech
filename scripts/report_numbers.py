"""Sinh MỌI số liệu cần điền vào mục 7 của báo cáo từ dữ liệu thật trong SQLite, kèm phân tích độ nhạy tham số.

    /opt/anaconda3/envs/vmap/bin/python scripts/report_numbers.py
Kết quả: report/numbers.md (đọc rồi chép sang báo cáo). Không tự bịa số: thiếu dữ liệu thì ghi rõ.
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from validate_formulas import independent  # noqa: E402
from vmap.analytics import aggregate as ag  # noqa: E402
from vmap.analytics import alerts as al  # noqa: E402
from vmap.analytics.alerts import AlertConfig, build_alerts  # noqa: E402
from vmap.analytics.anomaly import add_rolling_z, calibrate_thresholds  # noqa: E402
from vmap.config import load_settings  # noqa: E402
from vmap.data.db import Database  # noqa: E402
from vmap.finance import indicators as fi  # noqa: E402


def vn(x, nd=2):
    """Số theo kiểu Việt Nam: dấu phẩy thập phân."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ni(x):
    """Số nguyên kiểu Việt Nam: dấu chấm phân cách hàng nghìn."""
    return f"{int(x):,}".replace(",", ".")


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in r) + " |")
    return "\n".join(lines)


def thresholds_by_date(book_z, cfg):
    dates = sorted(book_z["session_date"].unique())
    return dates, {k: calibrate_thresholds(book_z[book_z["session_date"].isin(dates[:k])], cfg.min_obs)
                   for k in range(cfg.min_train_sessions, len(dates))}


def run_alerts(book_z, cfg, dates, thr_cache):
    parts = [al._flags(book_z[book_z["session_date"] == dates[k]], thr, cfg) for k, thr in thr_cache.items()]
    if not parts:
        return pd.DataFrame(), build_alerts(pd.DataFrame(columns=["symbol", "session_date", "minute", "n_flags"]), cfg)
    flags = pd.concat(parts, ignore_index=True)
    return flags, build_alerts(flags, cfg)


def gaps(idx):
    out = []
    for d, g in idx.groupby("session_date"):
        m = pd.Series(sorted(g["minute"].unique()))
        for part in (m[m.dt.hour < 12], m[m.dt.hour >= 12]):
            part = part.reset_index(drop=True)
            for i in range(1, len(part)):
                if (part[i] - part[i - 1]).total_seconds() > 180:
                    out.append((d, part[i - 1].strftime("%H:%M"), part[i].strftime("%H:%M"),
                                int((part[i] - part[i - 1]).total_seconds() // 60)))
    return pd.DataFrame(out, columns=["Phiên", "Từ", "Đến", "Khoảng trống (phút)"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--source", default="live", choices=["live", "simulated"])
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--out", default="report/numbers.md")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    s = load_settings()
    db = Database(a.db or s.db_path)
    src = a.source
    L = [f"# Số liệu cho báo cáo (nguồn: {src})", ""]
    if src == "simulated":
        L += ["> DỮ LIỆU MÔ PHỎNG: chỉ để thử script, KHÔNG đưa vào báo cáo.", ""]

    book = ag.build_book_1m(db, src, s)
    idx = ag.build_index_1m(db, src, s.index_code)
    if book.empty or idx.empty:
        L.append("Chưa đủ dữ liệu trong phiên khớp lệnh liên tục để tính. Hãy thu thập thêm.")
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text("\n".join(L), encoding="utf-8")
        print("\n".join(L))
        return

    # ---------- 7.2a Hoạt động thực tế ----------
    sessions = sorted(book["session_date"].unique())
    cnt = {t: int(db.read(f"SELECT COUNT(*) n FROM {t} WHERE source=?", (src,)).n[0]) for t in ("quotes", "trades", "index_ticks")}
    raw = int(db.read("SELECT COUNT(*) n FROM raw_messages WHERE source=?", (src,)).n[0])
    late = {t: int(db.read(f"SELECT COALESCE(SUM(is_late),0) n FROM {t} WHERE source=?", (src,)).n[0]) for t in cnt}
    states = db.read("SELECT book_state, COUNT(*) n FROM quotes WHERE source=? GROUP BY 1", (src,))
    lat = pd.concat([db.read(f"SELECT latency_ms FROM {t} WHERE source=? AND latency_ms IS NOT NULL", (src,)) for t in cnt])["latency_ms"]
    ev = db.read("SELECT event_type, detail FROM events WHERE source=?", (src,))
    rec = ev[ev.event_type == "reconnected"]["detail"].str.extract(r"duration_sec=([\d.]+)")[0].astype(float)
    perday = db.read("SELECT substr(ts_exchange,1,10) d, COUNT(*) n FROM quotes WHERE source=? AND ts_exchange IS NOT NULL GROUP BY 1 ORDER BY 1", (src,))
    L += ["## 7.2 Hoạt động thực tế", "",
          f"- Số phiên có chỉ báo: **{len(sessions)}** ({', '.join(sessions)}). Ghi rõ phiên nào chỉ thu một phần (xem khoảng trống bên dưới).",
          f"- Bản ghi chuẩn hóa: sổ lệnh {ni(cnt['quotes'])}, giao dịch {ni(cnt['trades'])}, chỉ số {ni(cnt['index_ticks'])}; tin thô lưu: {ni(raw)}.",
          f"- Tin đến muộn (is_late): sổ lệnh {ni(late['quotes'])}, giao dịch {ni(late['trades'])}, chỉ số {ni(late['index_ticks'])}.",
          "- Trạng thái sổ lệnh: " + ", ".join(f"{r.book_state} {ni(r.n)}" for r in states.itertuples()) + ".",
          f"- Độ trễ nhận (giây, phân giải 1 giây): trung vị {vn(lat.median()/1000)}, P95 {vn(lat.quantile(0.95)/1000)}, "
          f"lớn nhất {vn(lat.max()/1000)}; {vn((lat < 0).mean()*100, 1)}% giá trị âm (đồng hồ máy và sàn lệch dưới 1 giây).",
          f"- Mất kết nối: {int((ev.event_type == 'disconnect').sum())} lần; thời gian phục hồi trung vị "
          f"{vn(rec.median()) if len(rec) else 'n/a'} giây, lớn nhất {vn(rec.max()) if len(rec) else 'n/a'} giây (đã tính các lần ngắt chủ động để thử).",
          "- Tỷ lệ thông điệp hợp lệ, trùng, không hợp lệ: chép từ dòng 'Chất lượng dữ liệu' in ra khi dừng collect.py (số đếm không lưu trong DB).", "",
          "Số bản ghi sổ lệnh theo ngày:", "", md_table(perday.rename(columns={"d": "Ngày", "n": "Số bản ghi"})), ""]
    g = gaps(idx)
    L += ["Khoảng trống dữ liệu trong phiên (quá 3 phút không có tin chỉ số), cần nêu ở mục 8:", "",
          md_table(g) if len(g) else "Không có khoảng trống nào.", ""]

    # ---------- 7.2b RQ1 ----------
    d = idx.dropna(subset=["ret", "mbi"])
    def conc(eps, th):
        m = (d["ret"].abs() > eps) & (d["mbi"].abs() >= th)
        return (np.sign(d["ret"]) == np.sign(d["mbi"]))[m].mean() if m.any() else np.nan
    L += ["## RQ1: lợi suất VN30 và MBI", "",
          f"- Số phút phân tích: {ni(len(d))}; hệ số tương quan hạng Spearman giữa lợi suất và MBI: **{vn(d['ret'].corr(d['mbi'], method='spearman'), 3)}**.",
          f"- Tỷ lệ phút đồng thuận về dấu (ε = 0,1%, ngưỡng MBI 0,2): **{vn(conc(0.001, 0.2)*100, 1)}%**; số phút phân kỳ: {ni(int(d['divergence'].sum()))}.",
          "- Phân bố trạng thái (số phút): " + ", ".join(f"{k}: {ni(v)}" for k, v in d["regime"].value_counts().items()) + ".", "",
          "Độ nhạy theo ngưỡng (tỷ lệ phút phân kỳ trên số phút có tín hiệu rõ / tỷ lệ đồng thuận về dấu):", ""]
    rows = []
    for eps in (0.0005, 0.001, 0.002):
        for th in (0.1, 0.2, 0.3):
            reg = [fi.classify_regime(r, b, eps, th) for r, b in zip(d["ret"], d["mbi"])]
            div = np.mean([fi.is_divergence(x) for x in reg])
            rows.append((f"{vn(eps*100,2)}%", vn(th, 1), f"{vn(div*100,1)}%", f"{vn(conc(eps, th)*100,1)}%"))
    L += [md_table(pd.DataFrame(rows, columns=["ε", "Ngưỡng MBI", "Phút phân kỳ", "Đồng thuận về dấu"])), ""]

    # ---------- 7.2c RQ2 ----------
    cols = ["obi", "wobi", "spread_bps", "depth_total"]
    c = book[cols].corr(method="spearman").round(3)
    per_sym = book.groupby("symbol").apply(lambda x: x["spread_bps"].corr(x["depth_total"], method="spearman"), include_groups=False)
    L += ["## RQ2: tương quan hạng giữa OBI, WOBI, spread và độ sâu (toàn bộ mã, theo phút)", "",
          md_table(c.reset_index().rename(columns={"index": ""}).map(lambda v: vn(v, 3) if isinstance(v, float) else v)), "",
          f"- Tương quan spread và độ sâu theo từng mã: trung vị {vn(per_sym.median(), 3)}, từ {vn(per_sym.min(), 3)} đến {vn(per_sym.max(), 3)}.", ""]

    # ---------- 7.2d RQ3 + độ nhạy ----------
    cfg0 = AlertConfig(min_train_sessions=a.min_train)
    bz = add_rolling_z(book, ["spread_bps", "depth_total"], cfg0.window, cfg0.min_periods)
    dates, thr_cache = thresholds_by_date(bz, cfg0)
    flags, alerts = run_alerts(bz, cfg0, dates, thr_cache)
    L += ["## RQ3: cảnh báo", ""]
    if flags.empty:
        L += [f"Chưa có cảnh báo: cần ít nhất {a.min_train} phiên trước phiên được đánh giá (hiện có {len(dates)} phiên). "
              "Có thể chạy lại với --min-train 2 và ghi rõ trong báo cáo.", ""]
    else:
        L += [f"- Phiên được đánh giá: {', '.join(sorted(flags['session_date'].unique()))}; số cảnh báo: **{len(alerts)}** "
              f"({', '.join(f'{k}: {v}' for k, v in alerts['severity'].value_counts().items()) or 'không có'}).",
              f"- Số mã có ít nhất một cảnh báo: {alerts['symbol'].nunique() if len(alerts) else 0} / {book['symbol'].nunique()}.", ""]
        if len(alerts):
            ex = alerts.sort_values(["peak_level", "start_ts"], ascending=[False, True]).head(3)
            L += ["Ví dụ cảnh báo (chọn 2 đến 3 để đưa vào báo cáo, kèm nguyên nhân):", ""]
            L += [f"- {r.symbol}, {r.severity}, {pd.Timestamp(r.start_ts).strftime('%d/%m %H:%M')}–{pd.Timestamp(r.end_ts).strftime('%H:%M')}: {r.reason}" for r in ex.itertuples()]
            L += [""]
        L += ["Độ nhạy: số cảnh báo khi đổi ngưỡng z và sàn WOBI (các tham số khác giữ nguyên):", ""]
        rows = []
        for z in (1.5, 2.0, 2.5):
            for fl in (-0.1, -0.2, -0.3):
                cfg = AlertConfig(min_train_sessions=a.min_train, z_th=z, wobi_floor=fl)
                _, aa = run_alerts(bz, cfg, dates, thr_cache)
                rows.append((vn(z, 1), vn(fl, 2), len(aa)))
        L += [md_table(pd.DataFrame(rows, columns=["Ngưỡng z", "Sàn WOBI", "Số cảnh báo"])), ""]

    # ---------- 7.2e Đối chiếu công thức ----------
    q = db.read("SELECT ts_exchange, symbol, bid_levels, ask_levels FROM quotes WHERE source=? AND book_state='ok'", (src,))
    random.seed(a.seed)
    pick = q.iloc[random.sample(range(len(q)), min(5, len(q)))]
    rows, worst = [], 0.0
    for r in pick.itertuples():
        b, k = json.loads(r.bid_levels), json.loads(r.ask_levels)
        m = fi.book_metrics(b, k, s.obi_levels, s.depth_levels)
        ind = independent(b, k, s.obi_levels, s.depth_levels)
        for key, nd, lab in (("obi", 4, "OBI"), ("spread_bps", 4, "Spread (bps)"), ("depth_total", 0, "Độ sâu (đ)")):
            worst = max(worst, abs(m[key] - ind[key]) / (abs(ind[key]) or 1))
            rows.append((f"{r.symbol} {r.ts_exchange[5:10]} {r.ts_exchange[11:19]}", lab, vn(m[key], nd), vn(ind[key], nd),
                         ind["expr_obi"] if key == "obi" else (ind["expr_spread"] if key == "spread_bps" else "")))
    L += ["## 7.2 Đối chiếu công thức (5 bản ghi chọn ngẫu nhiên, seed cố định)", "",
          md_table(pd.DataFrame(rows, columns=["Bản ghi", "Chỉ báo", "Python", "Tính độc lập", "Biểu thức để tự tính tay"])), "",
          f"Sai lệch tương đối lớn nhất: {worst:.1e}. LƯU Ý: bạn phải tự tính tay (Excel) vài dòng bằng biểu thức ở cột cuối rồi ghi vào cột 'Tính tay' của báo cáo; "
          "cột 'Tính độc lập' chỉ là cài đặt thứ hai bằng code, không thay thế tính tay.", ""]

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\n>>> Đã ghi {a.out}")


if __name__ == "__main__":
    main()
