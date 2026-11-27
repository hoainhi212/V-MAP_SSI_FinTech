"""V-MAP - Vietnam Market Alert & Pulse."""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vmap.app.styles import apply_styles
from vmap.app.screens.overview import render as render_overview
from vmap.app.screens.market import render as render_market
from vmap.app.screens.liquidity import render as render_liquidity
from vmap.app.screens.alerts import render as render_alerts
from vmap.app.screens.reports import render_reports
from vmap.app.screens.methodology import render as render_methodology
from vmap.config import ROOT, load_settings
from vmap.analytics.alerts import AlertConfig, walk_forward

# Logo assets
LOGO_DIR = Path(__file__).resolve().parent / "assets"
LOGO_MARK = LOGO_DIR / "logo_mark.png"
LOGO_WORDMARK = LOGO_DIR / "logo_wordmark.png"

st.set_page_config(
    page_title="V-MAP | Market Alert & Pulse",
    page_icon=str(LOGO_WORDMARK) if LOGO_WORDMARK.exists() else "🌷",
    layout="wide"
)

apply_styles()
S = load_settings()

try:
    from vmap.app.data_access import load_bundle
    from vmap.data.db import Database
except ModuleNotFoundError as exc:
    st.title("🌷 V-MAP")
    st.error("Thiếu package dữ liệu `src/vmap/data/`. Cần khôi phục module Database và chuẩn hóa dữ liệu trước khi chạy dashboard.")
    st.code(str(exc))
    st.stop()

@st.cache_data(ttl=20, show_spinner="Đang tải dữ liệu...")
def cached_bundle(db_path: str, source: str):
    return load_bundle(db_path, source, S)

with st.sidebar:
    st.markdown("""
    <div class="vmap-wordmark">
        <span class="vmap-v">V</span><span class="vmap-hyphen">-</span><span class="vmap-m">M</span><span class="vmap-a">A</span><span class="vmap-p">P</span>
    </div>
    <div class="vmap-caption">
        Vietnam Market Alert & Pulse
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("KHÔNG GIAN LÀM VIỆC", [
        "Tổng quan", "Phân tích thị trường", "Giám sát thanh khoản",
        "Trung tâm cảnh báo", "Báo cáo", "Phương pháp & giới hạn"
    ], label_visibility="visible")
    st.divider()
    db_candidates = [p for p in (S.db_path, str(ROOT / "data" / "vmap_sim.db")) if Path(p).exists()]
    if not db_candidates:
        st.warning("Chưa có cơ sở dữ liệu. Hãy chạy collector SSI hoặc script mô phỏng.")
        st.stop()
    db_path = st.selectbox("Cơ sở dữ liệu", db_candidates)
    db = Database(db_path)
    sources = db.sources()
    db.close()
    if not sources:
        st.info("Cơ sở dữ liệu chưa có bản ghi.")
        st.stop()
    source = st.radio("Nguồn dữ liệu", sources, help="Dữ liệu simulated chỉ dùng để kiểm thử.")
    if source == "simulated":
        st.warning("Đang xem dữ liệu mô phỏng.")
    if st.button("↻ Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

bundle = cached_bundle(db_path, source)
status = bundle.get("status", {})
raw_idx = bundle.get("idx", pd.DataFrame())
raw_book = bundle.get("book", pd.DataFrame())

# ===== BỘ LỌC PHÂN TÍCH DÙNG CHUNG =====
all_dates = sorted(
    set(raw_idx.get("session_date", pd.Series(dtype=str)).dropna().astype(str))
    | set(raw_book.get("session_date", pd.Series(dtype=str)).dropna().astype(str))
)
if not all_dates:
    st.warning("Cơ sở dữ liệu chưa có phiên giao dịch để phân tích.")
    st.stop()

with st.sidebar:
    st.divider()
    st.markdown("**BỘ LỌC PHÂN TÍCH**")

    symbols = sorted(raw_book["symbol"].dropna().astype(str).unique()) if not raw_book.empty and "symbol" in raw_book else []
    symbol_options = ["Tất cả mã"] + symbols
    selected_symbol = st.selectbox("Mã cổ phiếu", symbol_options, index=0)

    period_label = st.selectbox(
        "Khung thời gian",
        ["1 phiên", "5 phiên", "10 phiên", "20 phiên", "Toàn bộ dữ liệu"],
        index=1,
        help="Giới hạn số phiên gần nhất được đưa vào các trang phân tích."
    )
    period_count = {"1 phiên": 1, "5 phiên": 5, "10 phiên": 10, "20 phiên": 20}.get(period_label)
    period_dates = all_dates[-period_count:] if period_count else all_dates

    sensitivity_label = st.select_slider(
        "Ngưỡng nhạy cảm cảnh báo",
        options=["Rất nhạy", "Nhạy", "Trung bình", "Ít nhạy", "Rất ít nhạy"],
        value="Trung bình",
        help="Mức nhạy hơn tương ứng z_th thấp hơn; thuật toán hiệu chỉnh P95/P5 và hysteresis được giữ nguyên."
    )
    z_threshold = {
        "Rất nhạy": 1.25,
        "Nhạy": 1.5,
        "Trung bình": 2.0,
        "Ít nhạy": 2.5,
        "Rất ít nhạy": 3.0,
    }[sensitivity_label]
    st.caption(f"Ngưỡng z hiện tại: {z_threshold:.2f}")

    available_dates = [d for d in period_dates if d in all_dates]
    day = st.selectbox(
        "Phiên giao dịch",
        sorted(available_dates, reverse=True),
        index=0
    )

# Tính lại cảnh báo trên toàn bộ lịch sử với z_th được chọn để không làm mất
# các phiên huấn luyện trước khoảng thời gian đang hiển thị.
alert_cfg = AlertConfig(z_th=z_threshold)
flags, recalculated_alerts, recalculated_thr = walk_forward(raw_book, alert_cfg, source)

# Tạo bundle theo bộ lọc toàn cục; dữ liệu gốc vẫn được giữ trong cache.
filtered_bundle = dict(bundle)
filtered_bundle["idx"] = raw_idx[raw_idx["session_date"].astype(str).isin(period_dates)].copy() if not raw_idx.empty else raw_idx.copy()
book_view = raw_book[raw_book["session_date"].astype(str).isin(period_dates)].copy() if not raw_book.empty else raw_book.copy()
if selected_symbol != "Tất cả mã" and not book_view.empty:
    book_view = book_view[book_view["symbol"].astype(str) == selected_symbol].copy()
filtered_bundle["book"] = book_view
filtered_bundle["flags"] = flags
filtered_bundle["alerts"] = recalculated_alerts
filtered_bundle["thr"] = recalculated_thr

# ===== PAGE TITLE =====

PAGE_TITLES = {
    "Tổng quan": "TỔNG QUAN",
    "Phân tích thị trường": "PHÂN TÍCH THỊ TRƯỜNG",
    "Giám sát thanh khoản": "GIÁM SÁT THANH KHOẢN",
    "Trung tâm cảnh báo": "TRUNG TÂM CẢNH BÁO",
    "Báo cáo": "TRUNG TÂM BÁO CÁO",
    "Phương pháp & giới hạn": "PHƯƠNG PHÁP VÀ GIỚI HẠN"
}

st.markdown(
    "<div style='font-size:12px;font-weight:800;"
    "letter-spacing:.12em;color:#9A8CB8'>"
    "MARKET INTELLIGENCE · FINTECH PROJECT</div>",
    unsafe_allow_html=True
)

st.title(PAGE_TITLES[page])

st.caption(
    "Theo dõi trạng thái VN30 và nhận diện rủi ro thanh khoản cổ phiếu "
    "· Công cụ phân tích học thuật, không phải khuyến nghị đầu tư."
)

# ===== DATA STATUS =====

if status.get("state") == "stale":
    st.error(status.get("label", "Dữ liệu có thể đã cũ."))
elif source == "simulated":
    st.warning(
        status.get("label", "Dữ liệu mô phỏng, không đại diện thị trường thực.")
    )
else:
    st.caption(status.get("label", "Trạng thái dữ liệu chưa xác định."))

# ===== PAGE ROUTING =====

if page == "Tổng quan":
    render_overview(filtered_bundle, source, status, day) if day else st.info(
        "Chưa có dữ liệu chỉ số."
    )

elif page == "Phân tích thị trường":
    render_market(filtered_bundle, day) if day else st.info(
        "Chưa có dữ liệu chỉ số."
    )

elif page == "Giám sát thanh khoản":
    render_liquidity(filtered_bundle, day, selected_symbol) if day else st.info(
        "Chưa có dữ liệu sổ lệnh."
    )

elif page == "Trung tâm cảnh báo":
    render_alerts(filtered_bundle, day, selected_symbol)

elif page == "Báo cáo":
    render_reports(filtered_bundle, source)

elif page == "Phương pháp & giới hạn":
    render_methodology()
