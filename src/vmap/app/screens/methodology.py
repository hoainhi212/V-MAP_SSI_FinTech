"""Trang Phương pháp và giới hạn."""
import streamlit as st


def render():
    st.header("PHƯƠNG PHÁP VÀ GIỚI HẠN")
    st.caption("Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.")

    st.subheader("Công thức")
    st.latex(r"MBI=\frac{A-D}{A+D+U}\qquad R_t=\frac{V_t}{V_{ref}}-1")
    st.latex(r"OBI_n=\frac{\sum_{i\le n}Q^{bid}_i-\sum_{i\le n}Q^{ask}_i}{\sum_{i\le n}Q^{bid}_i+\sum_{i\le n}Q^{ask}_i}"
             r"\qquad WOBI=\frac{\sum_i Q^{bid}_i/i-\sum_i Q^{ask}_i/i}{\sum_i Q^{bid}_i/i+\sum_i Q^{ask}_i/i}")
    st.latex(r"Spread_{bps}=\frac{P^{ask}_1-P^{bid}_1}{(P^{ask}_1+P^{bid}_1)/2}\times10^4\qquad "
             r"Depth=\sum_{i\le 5}P_iQ_i\qquad DR=\frac{Depth_{bid}}{Depth_{ask}}")
    st.latex(r"z_t=\frac{x_t-\bar x_{t-W..t-1}}{\max(s_{t-W..t-1},\,0{,}1\,|\bar x_{t-W..t-1}|)},\quad W=30")
    st.markdown(
        "- **A, D, U**: số mã tăng, giảm, đứng giá so với giá tham chiếu; chỉ số tham chiếu của VN30 suy ra bằng giá trị hiện tại trừ thay đổi điểm.\n"
        "- **OBI** tính trên 3 mức giá tốt nhất mỗi phía; **WOBI** dùng tới 10 mức với trọng số 1/i; **độ sâu** tính trên 5 mức, quy ra đồng.\n"
        "- Chỉ báo sổ lệnh chỉ tính trong phiên khớp lệnh liên tục (09:15-11:30 và 13:00-14:30), gộp theo phút.")

    st.subheader("Quy tắc cảnh báo")
    st.markdown(
        "Mỗi điều kiện dùng **ngưỡng phân vị riêng của từng mã**, tính từ các phiên *trước* phiên đang xét (walk-forward):\n\n"
        "1. **Spread mở rộng**: spread từ max(P95, 1,5 lần trung vị) trở lên và z từ ngưỡng z (mặc định 2) trở lên.\n"
        "2. **Độ sâu mỏng**: độ sâu không quá P5 và z từ -2 trở xuống.\n"
        "3. **Áp lực bán**: WOBI không lớn hơn số nhỏ hơn trong hai giá trị P5 của mã và -0,20.\n\n"
        "Mức độ theo số điều kiện đồng thời: 1 = WATCH, 2 = WARNING, 3 = CRITICAL. Cảnh báo mở khi tín hiệu kéo dài "
        "từ 2 phút liên tiếp và đóng khi hết tín hiệu 3 phút liên tiếp. Cần tối thiểu 3 phiên trước đó để hiệu chỉnh "
        "ngưỡng; chưa đủ thì hệ thống không phát cảnh báo thay vì đặt ngưỡng tùy ý.")

    st.subheader("Giới hạn")
    st.markdown(
        "- Sổ lệnh chỉ phản ánh các mức giá đang hiển thị, không thấy cung cầu tiềm ẩn; lệnh có thể bị hủy ngay.\n"
        "- OBI không phải xác suất giá tăng hay giảm; spread không phải toàn bộ chi phí giao dịch; độ sâu không bảo đảm khả năng khớp.\n"
        "- Mẫu quan sát ngắn; ngưỡng chưa chỉnh theo mùa vụ trong ngày; các tham số là lựa chọn có lý giải nhưng chưa tối ưu hóa.\n"
        "- Mốc thời gian của sàn có độ phân giải 1 giây nên độ trễ chỉ có ý nghĩa ở mức giây.\n"
        "- Chưa chứng minh quan hệ nhân quả giữa mất cân bằng sổ lệnh và biến động giá.\n"
        "- **Không phải khuyến nghị mua hoặc bán.**")
