"""V-MAP - Vietnam Market Alert & Pulse.
Chạy: streamlit run src/vmap/app/streamlit_app.py
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vmap.app.styles import apply_styles
from vmap.app.pages.overview import render as render_overview
from vmap.app.pages.market import render as render_market
from vmap.app.pages.liquidity import render as render_liquidity
from vmap.app.pages.alerts import render as render_alerts
from vmap.app.pages.reports import render_reports
from vmap.config import ROOT, load_settings

try:
    from vmap.app.data_access import load_bundle
    from vmap.data.db import Database
except ModuleNotFoundError as exc:
    st.set_page_config(page_title="V-MAP", page_icon="📊", layout="wide")
    apply_styles()
    st.title("V-MAP")
    st.error("Bộ mã nguồn được cung cấp đang thiếu package `src/vmap/data/` (bao gồm Database và các module chuẩn hóa/thu thập). Không thể nạp dữ liệu cho dashboard cho đến khi khôi phục package này.")
    st.code(str(exc))
    st.stop()

st.set_page_config(page_title="V-MAP | Market Alert & Pulse", page_icon="📊", layout="wide")
apply_styles()
S = load_settings()

@st.cache_data(ttl=20, show_spinner="Đang tải và tổng hợp dữ liệu...")
def cached_bundle(db_path: str, source: str):
    return load_bundle(db_path, source, S)

st.sidebar.title("V-MAP")
st.sidebar.caption("Vietnam Market Alert & Pulse")
db_candidates = [p for p in (S.db_path, str(ROOT / "data" / "vmap_sim.db")) if Path(p).exists()]
if not db_candidates:
    st.title("V-MAP")
    st.warning("Chưa có cơ sở dữ liệu. Chạy bộ thu thập SSI hoặc script mô phỏng trước khi mở dashboard.")
    st.stop()

db_path = st.sidebar.selectbox("Cơ sở dữ liệu", db_candidates)
db = Database(db_path)
sources = db.sources()
db.close()
if not sources:
    st.title("V-MAP")
    st.info("Cơ sở dữ liệu chưa có bản ghi.")
    st.stop()
source = st.sidebar.radio("Nguồn dữ liệu", sources, help="Dữ liệu simulated chỉ dùng để kiểm thử quy trình.")
if source == "simulated":
    st.sidebar.warning("Đang xem dữ liệu mô phỏng, không phải dữ liệu thị trường thật.")
if st.sidebar.button("Làm mới dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

bundle = cached_bundle(db_path, source)
status = bundle.get("status", {})
st.title("V-MAP")
st.caption("Giám sát trạng thái VN30 và nhận diện rủi ro thanh khoản cổ phiếu · Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.")
state = status.get("state")
if state == "stale":
    st.error(status.get("label", "Dữ liệu có thể đã cũ."))
elif source == "simulated":
    st.warning(status.get("label", "Dữ liệu mô phỏng."))
else:
    st.info(status.get("label", "Trạng thái dữ liệu chưa xác định."))

idx, book = bundle.get("idx", pd.DataFrame()), bundle.get("book", pd.DataFrame())
available_dates = []
for frame in (idx, book):
    if not frame.empty and "session_date" in frame:
        available_dates.extend(frame.session_date.dropna().astype(str).tolist())
if available_dates:
    dates = sorted(set(available_dates), reverse=True)
    day = st.sidebar.selectbox("Phiên giao dịch", dates)
else:
    day = None
    st.warning("Chưa có dữ liệu chỉ số/sổ lệnh đủ điều kiện để hiển thị. Có thể mở trang Báo cáo để xem trạng thái dữ liệu trống.")

tabs = st.tabs(["Tổng quan", "Phân tích thị trường", "Giám sát thanh khoản", "Trung tâm cảnh báo", "Báo cáo"])
with tabs[0]:
    if day:
        render_overview(bundle, source, status, day)
    else:
        st.info("Không có dữ liệu cho trang Tổng quan.")
with tabs[1]:
    if day:
        render_market(bundle, day)
    else:
        st.info("Không có dữ liệu chỉ số.")
with tabs[2]:
    if day:
        render_liquidity(bundle, day)
    else:
        st.info("Không có dữ liệu sổ lệnh.")
with tabs[3]:
    render_alerts(bundle, day)
with tabs[4]:
    render_reports(bundle, source)
