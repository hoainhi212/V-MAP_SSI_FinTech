# Đối chiếu dàn ý báo cáo <-> mã nguồn

| Mục dàn ý | Nơi trong dự án |
|---|---|
| 2.2 Kiến trúc | Sơ đồ trong README; các gói `ssi/ data/ finance/ analytics/ app/` |
| 2.5 Bảo mật | `.env.example`, `.gitignore`, `ssi/auth.py` (token chỉ ở RAM, không log) |
| 3.1 Nguồn dữ liệu | `ssi/auth.py`, `ssi/rest.py`, `ssi/stream.py` |
| 3.2 Từ điển dữ liệu | `ssi/schema.py`, `docs/data_dictionary.md` |
| 3.3 Quy trình thu thập | `scripts/collect.py` -> `data/collector.py` |
| 3.4 Chất lượng dữ liệu | `data/normalize.py` (thiếu/sai kiểu/sổ lệnh lỗi/một phần), `data/quality.py` (muộn), `data/db.py` (trùng), `ssi/stream.py` (mất kết nối) |
| 3.5 Lưu trữ, tái lập | `data/db.py`, `analytics/aggregate.py` |
| 4.1 Độ rộng | `finance/indicators.py::market_breadth, classify_regime` |
| 4.2 OBI | `finance/indicators.py::obi, wobi` |
| 4.3 Thanh khoản | `finance/indicators.py::spread_*, depth_*` |
| 4.4 Bất thường | `analytics/anomaly.py` |
| 4.5 Cảnh báo | `analytics/alerts.py` |
| 5.x Giao diện | `app/streamlit_app.py` |
| 6.1 Kiểm thử | `tests/` (23+ ca; công thức tính tay, trùng, muộn, no-lookahead, hysteresis, end-to-end) |
| 6.2 Python vs tính tay | `scripts/validate_formulas.py` |
| 6.3-6.4 Số liệu thực tế | `scripts/evaluate.py` -> `report/metrics.json` (RQ1, RQ2, độ trễ, kết nối lại) |
