# Số liệu cho báo cáo (nguồn: live)

## 7.2 Hoạt động thực tế

- Số phiên có chỉ báo: **2** (2026-11-25, 2026-11-26). Ghi rõ phiên nào chỉ thu một phần (xem khoảng trống bên dưới).
- Bản ghi chuẩn hóa: sổ lệnh 407.844, giao dịch 241.092, chỉ số 5.552; tin thô lưu: 712.568.
- Tin đến muộn (is_late): sổ lệnh 0, giao dịch 0, chỉ số 0.
- Trạng thái sổ lệnh: incomplete 432, ok 407.412.
- Độ trễ nhận (giây, phân giải 1 giây): trung vị 0,57, P95 1,07, lớn nhất 64,21; 0,0% giá trị âm (đồng hồ máy và sàn lệch dưới 1 giây).
- Mất kết nối: 26 lần; thời gian phục hồi trung vị 12,60 giây, lớn nhất 61,20 giây (đã tính các lần ngắt chủ động để thử).
- Tỷ lệ thông điệp hợp lệ, trùng, không hợp lệ: chép từ dòng 'Chất lượng dữ liệu' in ra khi dừng collect.py (số đếm không lưu trong DB).

Số bản ghi sổ lệnh theo ngày:

| Ngày | Số bản ghi |
| --- | --- |
| 2026-11-25 | 132269 |
| 2026-11-26 | 275575 |

Khoảng trống dữ liệu trong phiên (quá 3 phút không có tin chỉ số), cần nêu ở mục 8:

| Phiên | Từ | Đến | Khoảng trống (phút) |
| --- | --- | --- | --- |
| 2026-11-25 | 10:14 | 10:20 | 6 |
| 2026-11-25 | 10:50 | 10:55 | 5 |

## RQ1: lợi suất VN30 và MBI

- Số phút phân tích: 390; hệ số tương quan hạng Spearman giữa lợi suất và MBI: **0,966**.
- Tỷ lệ phút đồng thuận về dấu (ε = 0,1%, ngưỡng MBI 0,2): **100,0%**; số phút phân kỳ: 0.
- Phân bố trạng thái (số phút): Giảm đồng thuận: 315, Trung tính / giằng co: 58, Tăng đồng thuận: 17.

Độ nhạy theo ngưỡng (tỷ lệ phút phân kỳ trên số phút có tín hiệu rõ / tỷ lệ đồng thuận về dấu):

| ε | Ngưỡng MBI | Phút phân kỳ | Đồng thuận về dấu |
| --- | --- | --- | --- |
| 0,05% | 0,1 | 0,0% | 100,0% |
| 0,05% | 0,2 | 0,0% | 100,0% |
| 0,05% | 0,3 | 0,0% | 100,0% |
| 0,10% | 0,1 | 0,0% | 100,0% |
| 0,10% | 0,2 | 0,0% | 100,0% |
| 0,10% | 0,3 | 0,0% | 100,0% |
| 0,20% | 0,1 | 0,0% | 100,0% |
| 0,20% | 0,2 | 0,0% | 100,0% |
| 0,20% | 0,3 | 0,0% | 100,0% |

## RQ2: tương quan hạng giữa OBI, WOBI, spread và độ sâu (toàn bộ mã, theo phút)

|  | obi | wobi | spread_bps | depth_total |
| --- | --- | --- | --- | --- |
| obi | 1,000 | 0,960 | 0,105 | 0,277 |
| wobi | 0,960 | 1,000 | 0,115 | 0,271 |
| spread_bps | 0,105 | 0,115 | 1,000 | 0,314 |
| depth_total | 0,277 | 0,271 | 0,314 | 1,000 |

- Tương quan spread và độ sâu theo từng mã: trung vị 0,000, từ -0,492 đến 0,681.

## RQ3: cảnh báo

Chưa có cảnh báo: cần ít nhất 3 phiên trước phiên được đánh giá (hiện có 2 phiên). Có thể chạy lại với --min-train 2 và ghi rõ trong báo cáo.

## 7.2 Đối chiếu công thức (5 bản ghi chọn ngẫu nhiên, seed cố định)

| Bản ghi | Chỉ báo | Python | Tính độc lập | Biểu thức để tự tính tay |
| --- | --- | --- | --- | --- |
| HPG 11-26 13:43:43 | OBI | 0,3839 | 0,3839 | (2,184,900 - 972,800) / (2,184,900 + 972,800) |
| HPG 11-26 13:43:43 | Spread (bps) | 25,0941 | 25,0941 | (19,950 - 19,900) / ((19,950 + 19,900)/2) * 10000 |
| HPG 11-26 13:43:43 | Độ sâu (đ) | 62.776.985.000 | 62.776.985.000 |  |
| VIC 11-25 13:24:05 | OBI | 0,4458 | 0,4458 | (18,000 - 6,900) / (18,000 + 6,900) |
| VIC 11-25 13:24:05 | Spread (bps) | 4,0692 | 4,0692 | (245,800 - 245,700) / ((245,800 + 245,700)/2) * 10000 |
| VIC 11-25 13:24:05 | Độ sâu (đ) | 6.117.230.000 | 6.117.230.000 |  |
| BVH 11-25 10:37:17 | OBI | -0,1676 | -0,1676 | (7,700 - 10,800) / (7,700 + 10,800) |
| BVH 11-25 10:37:17 | Spread (bps) | 34,4828 | 34,4828 | (58,100 - 57,900) / ((58,100 + 57,900)/2) * 10000 |
| BVH 11-25 10:37:17 | Độ sâu (đ) | 1.074.140.000 | 1.074.140.000 |  |
| SSI 11-26 14:26:35 | OBI | 0,7204 | 0,7204 | (2,832,100 - 460,300) / (2,832,100 + 460,300) |
| SSI 11-26 14:26:35 | Spread (bps) | 26,4201 | 26,4201 | (18,950 - 18,900) / ((18,950 + 18,900)/2) * 10000 |
| SSI 11-26 14:26:35 | Độ sâu (đ) | 62.081.725.000 | 62.081.725.000 |  |
| SSI 11-26 09:16:16 | OBI | 0,6428 | 0,6428 | (516,400 - 112,300) / (516,400 + 112,300) |
| SSI 11-26 09:16:16 | Spread (bps) | 26,1438 | 26,1438 | (19,150 - 19,100) / ((19,150 + 19,100)/2) * 10000 |
| SSI 11-26 09:16:16 | Độ sâu (đ) | 11.975.465.000 | 11.975.465.000 |  |

Sai lệch tương đối lớn nhất: 0.0e+00. LƯU Ý: bạn phải tự tính tay (Excel) vài dòng bằng biểu thức ở cột cuối rồi ghi vào cột 'Tính tay' của báo cáo; cột 'Tính độc lập' chỉ là cài đặt thứ hai bằng code, không thay thế tính tay.
