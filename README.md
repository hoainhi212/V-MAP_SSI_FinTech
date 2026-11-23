# V-MAP - Vietnam Market Alert & Pulse

Hệ thống giám sát trạng thái thị trường VN30 và nhận diện rủi ro thanh khoản cổ phiếu, dùng **SSI FastConnect Data API**
(REST + WebSocket). Đồ án cá nhân cuối kỳ - môn Công nghệ tài chính.

> **Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.** Dự án chỉ dùng quyền *Market Data*,
> **không có bất kỳ chức năng gửi/sửa/hủy lệnh nào**.

## Luồng xử lý

```
SSI FastConnect (REST + WebSocket)
  -> ssi/        xác thực, REST có giới hạn tần suất, WebSocket + tự kết nối lại
  -> data/       chuẩn hoá, kiểm tra chất lượng (thiếu/trùng/sai kiểu/muộn/sổ lệnh lỗi), lưu SQLite
  -> finance/    MBI, OBI, WOBI, Spread, Depth, Depth Ratio (hàm thuần, có test tính tay)
  -> analytics/  gộp 1 phút, z-score cuộn, ngưỡng phân vị walk-forward, máy trạng thái cảnh báo
  -> app/        dashboard Streamlit + Plotly
```

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # điền SSI_CONSUMER_ID / SSI_CONSUMER_SECRET
```

Đăng ký consumerID/secret của FastConnect **Data** tại https://developers.ssi.com.vn/ . Không commit `.env`.

## Chạy

| Mục đích | Lệnh |
|---|---|
| Thu thập dữ liệu thật (để chạy suốt phiên) | `python scripts/collect.py` |
| Lấy rổ VN30 từ REST rồi thu thập | `python scripts/collect.py --refresh-components` |
| Dashboard | `streamlit run src/vmap/app/streamlit_app.py` |
| Số liệu cho Chương 6 | `python scripts/evaluate.py --source live` |
| Bảng đối chiếu công thức (6.2) | `python scripts/validate_formulas.py --source live --n 5` |
| Kiểm thử | `pytest -q` (hoặc `python scripts/run_tests.py`) |
| Demo khi chưa có dữ liệu thật | `python scripts/simulate.py` (gắn `source='simulated'`) |

Cần **tối thiểu 10 phiên** dữ liệu thật (mục tiêu 20) trước khi viết kết quả; 3 phiên đầu dùng để hiệu chỉnh ngưỡng nên không có cảnh báo.

## Cấu trúc dữ liệu (SQLite)

`raw_messages` (tin thô) · `index_ticks` · `trades` · `quotes` (chuẩn hoá, lưu cả `ts_exchange` và `ts_recv`,
`latency_ms`, `is_late`, `source`) · `alerts` · `events` (connect/disconnect/reconnected).
Chống trùng bằng `dedup_key UNIQUE`. Mọi mốc thời gian theo Asia/Ho_Chi_Minh (UTC+7). Từ điển: `docs/data_dictionary.md`.

## Tính tái lập

Chạy lại toàn bộ chỉ báo từ DB: `build_book_1m` / `build_index_1m` (analytics/aggregate.py) chỉ đọc bảng chuẩn hoá.
Dữ liệu thật và mô phỏng luôn tách bằng cột `source`; dashboard hiển thị biểu ngữ khi đang xem dữ liệu mô phỏng.

## ⚠️ Cần đối chiếu với tài liệu SSI trước khi nộp

Mã được viết theo mô hình dữ liệu SSI FastConnect đã biết nhưng **chưa chạy với khoá thật** trong môi trường dựng mã. Kiểm tra:

1. **Tên kênh streaming** (`X-QUOTE:...`, `X-TRADE:...`, `MI:VN30`) và cách SDK nhận nhiều mã: `config.py` / `VMAP_STREAM_CHANNELS` (phân tách bằng `;`).
2. **Tên trường**: sửa duy nhất tại `src/vmap/ssi/schema.py` (đã có alias `adv/dec/nc/v/cr/p/q` theo dàn ý). Chạy `collect.py` vài phút rồi xem `raw_messages` để so khớp.
3. **Tên tham số REST** (`indexCode`, `indexId`, `fromDate`...) trong `ssi/rest.py`.
4. **Đơn vị giá**: nếu SSI trả giá theo nghìn đồng, đặt `price_scale=1000` (Settings) - ảnh hưởng spread theo bước giá và độ sâu.
5. **Hạn mức gọi API**: chỉnh `VMAP_REST_MIN_INTERVAL` theo gói của bạn. Rổ VN30 mặc định trong `config.py` có thể đã đổi.

## Giới hạn đã biết

- Dashboard Streamlit chưa được chạy thử giao diện trong môi trường dựng (không có Streamlit/mạng); phần nạp dữ liệu và tính toán dưới nó đã có test.
- Bộ giám sát kết nối bỏ luồng cũ và dựng luồng mới khi mất tin (SDK chạy chặn nên không hủy sạch luồng được); nếu thấy rò luồng khi chạy dài, chạy `collect.py` dưới supervisor (systemd/Task Scheduler) tự khởi động lại.
- Ngưỡng chưa chỉnh theo mùa vụ trong ngày; mốc thời gian sàn có độ phân giải 1 giây.
- Kết quả trên dữ liệu mô phỏng chỉ kiểm tra quy trình, **không** phải bằng chứng thị trường.
