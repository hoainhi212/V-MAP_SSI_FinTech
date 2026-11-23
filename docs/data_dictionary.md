# Từ điển dữ liệu

## Biến SSI -> biến chuẩn hoá (khai báo trong `src/vmap/ssi/schema.py`)

| Biến gốc (alias) | Biến chuẩn hoá | Ý nghĩa | Kiểu |
|---|---|---|---|
| Advances / adv | advances | Số mã tăng | int |
| Declines / dec | declines | Số mã giảm | int |
| NoChanges / nc | unchanged | Số mã đứng giá | int |
| IndexValue / v | index_value | Giá trị chỉ số | float |
| PriorIndexValue | prior_value | Chỉ số tham chiếu | float |
| RatioChange / cr | change_pct / ratio_change | % thay đổi | float |
| TotalValue / TotalQtty | total_value / total_volume | Giá trị / khối lượng lũy kế | float |
| BidPrice1..10, BidVol1..10 | bid_levels (JSON [[giá, KL],...]) | Các mức giá mua | list |
| AskPrice1..10, AskVol1..10 | ask_levels | Các mức giá bán | list |
| LastPrice / p | last_price | Giá khớp gần nhất | float |
| LastVol / q | last_vol | Khối lượng khớp gần nhất | float |
| TradingDate + Time | ts_exchange (UTC+7) | Thời điểm theo sàn | ISO-8601 |
| (hệ thống) | ts_recv, latency_ms | Thời điểm nhận, độ trễ = ts_recv - ts_exchange | ISO / float |

Giá trị không phải số (`ATO`, `ATC`, rỗng) -> `NULL`, không bao giờ quy về 0.

## Cột kiểm soát chất lượng

`source` (live | simulated) · `is_late` (mốc thời gian lùi > `late_tolerance` giây so với tin mới nhất cùng mã) ·
`book_state` (ok | incomplete | crossed | auction) · `partial` (có mức giá điền từ snapshot trước) · `dedup_key`.

## Chỉ báo 1 phút (`build_book_1m`)

`obi`, `wobi`, `spread_bps`, `spread_ticks`, `depth_bid`, `depth_ask`, `depth_total` (VND), `depth_ratio`, `n_snap`:
trung bình các snapshot hợp lệ (`book_state='ok'`) trong phút, chỉ trong phiên khớp lệnh liên tục.
