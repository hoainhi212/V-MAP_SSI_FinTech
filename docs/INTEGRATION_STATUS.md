# Trạng thái tích hợp giao diện và báo cáo

## Đã hoàn thiện trong bản cập nhật

- Chuẩn hóa điều hướng thành 5 trang: Tổng quan, Phân tích thị trường, Giám sát thanh khoản, Trung tâm cảnh báo và Báo cáo.
- Loại bỏ tab HTML iframe tham chiếu tới `templates/vmap_dashboard.html` (tệp này không có trong gói mã nguồn được gửi).
- Tạo hai loại PDF: báo cáo tổng hợp thị trường và báo cáo phân tích cổ phiếu.
- Báo cáo chỉ được tạo khi người dùng bấm nút; không có lịch chạy hoặc xuất tự động.
- Người dùng chọn khoảng ngày; báo cáo cổ phiếu có thêm lựa chọn mã.
- Nội dung báo cáo tự động bao gồm các phần dữ liệu phù hợp, biểu đồ, bảng và giới hạn dữ liệu. Chỉ tiêu không có dữ liệu được ghi là không khả dụng.
- Lưu lịch sử báo cáo cùng nội dung PDF trong `data/report_history.sqlite`.
- Nhúng font DejaVu Sans để hỗ trợ tiếng Việt trong PDF.

## Phần còn thiếu trong ZIP đầu vào

Gói ZIP không chứa thư mục `src/vmap/data/`, trong khi các module hiện có đang import:
- `vmap.data.db.Database`
- `vmap.data.normalize`
- `vmap.data.collector`
- các module dữ liệu được dùng bởi scripts và tests.

Vì vậy, không thể chạy end-to-end dashboard, collector hoặc toàn bộ test suite từ ZIP này. Đây là phần mã nguồn lõi bị thiếu trong gói đầu vào, không phải lỗi được tạo ra bởi phần giao diện/báo cáo. Cần bổ sung lại nguyên thư mục `src/vmap/data/` từ bản dự án gốc trước khi kiểm thử tích hợp.

## Kiểm tra đã thực hiện

- Biên dịch cú pháp toàn bộ Python trong `src/`: đạt.
- Tạo thử PDF tổng hợp và PDF cổ phiếu bằng bundle dữ liệu kiểm thử: đạt, file đầu ra có chữ ký PDF hợp lệ.
- Kiểm tra lưu và đọc lịch sử PDF: đạt.
- `tests/test_indicators.py`: 9/9 test đạt.
- `pytest -q` toàn bộ: chưa thể thu thập test vì thiếu `vmap.data` trong ZIP.
