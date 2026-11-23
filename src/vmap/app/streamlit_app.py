"""V-MAP - Vietnam Market Alert & Pulse. Chạy: streamlit run src/vmap/app/streamlit_app.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vmap.app.data_access import latest_book, load_bundle
from vmap.config import ROOT, load_settings
from vmap.data.db import Database

st.set_page_config(page_title="V-MAP", page_icon="📊", layout="wide")
S = load_settings()


@st.cache_data(ttl=20, show_spinner="Đang tính chỉ báo...")
def cached_bundle(db_path: str, source: str):
    return load_bundle(db_path, source, S)


# ------------------------------------------------------------------ thanh bên
st.sidebar.title("V-MAP")
db_candidates = [p for p in (S.db_path, str(ROOT / "data" / "vmap_sim.db")) if Path(p).exists()]
if not db_candidates:
    st.title("V-MAP - Vietnam Market Alert & Pulse")
    st.warning("Chưa có cơ sở dữ liệu. Chạy `python scripts/collect.py` (dữ liệu SSI thật) hoặc "
               "`python scripts/simulate.py` (dữ liệu MÔ PHỎNG để demo).")
    st.stop()
db_path = st.sidebar.selectbox("Cơ sở dữ liệu", db_candidates)
_db = Database(db_path)
sources = _db.sources()
_db.close()
if not sources:
    st.title("V-MAP - Vietnam Market Alert & Pulse")
    st.info("Cơ sở dữ liệu còn trống - chờ bộ thu thập ghi dữ liệu.")
    st.stop()
source = st.sidebar.radio("Nguồn dữ liệu", sources, help="'simulated' là dữ liệu giả lập để kiểm thử.")
auto = st.sidebar.checkbox("Tự động làm mới (20 giây)", value=False)
if st.sidebar.button("Làm mới ngay"):
    st.cache_data.clear()

B = cached_bundle(db_path, source)
book, idx, flags, alerts, thr, status = B["book"], B["idx"], B["flags"], B["alerts"], B["thr"], B["status"]

# ------------------------------------------------------------------ tiêu đề + trạng thái
st.title("V-MAP - Vietnam Market Alert & Pulse")
st.caption("Giám sát trạng thái thị trường VN30 và nhận diện rủi ro thanh khoản cho nhà đầu tư cá nhân. "
           "Nguồn: SSI FastConnect API. **Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.**")
(st.error if status["state"] == "stale" else st.warning if source == "simulated" else st.info)(status["label"])
c1, c2, c3 = st.columns(3)
c1.metric("Tin nhận gần nhất", "-" if status["last_recv"] is None else status["last_recv"].strftime("%d/%m %H:%M:%S"))
c2.metric("Sự kiện kết nối cuối", status["last_event"] or "-")
c3.metric("Bản ghi (quote / trade / chỉ số)", f"{B['counts']['q']:,} / {B['counts']['t']:,} / {B['counts']['i']:,}")

if book.empty or idx.empty:
    st.info("Chưa đủ dữ liệu trong phiên khớp lệnh liên tục (09:15-11:30, 13:00-14:30) để tính chỉ báo.")
    st.stop()

dates = sorted(idx["session_date"].unique(), reverse=True)
day = st.sidebar.selectbox("Phiên giao dịch", dates)
symbols = sorted(book["symbol"].unique())
sym = st.sidebar.selectbox("Mã cổ phiếu", symbols)
sev_filter = st.sidebar.multiselect("Mức cảnh báo", ["WATCH", "WARNING", "CRITICAL"],
                                    default=["WATCH", "WARNING", "CRITICAL"])
d_idx, d_book = idx[idx.session_date == day], book[book.session_date == day]
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Tổng quan", "Trạng thái thị trường", "Thanh khoản cổ phiếu",
                                        "Cảnh báo", "Phương pháp & giới hạn"])

# ------------------------------------------------------------------ 1. tổng quan
with tab1:
    last = d_idx.iloc[-1]
    day_alerts = alerts[alerts.start_ts.astype(str).str.startswith(day)] if len(alerts) else alerts
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("VN30", f"{last.index_value:,.2f}", None if pd.isna(last.ret) else f"{last.ret * 100:+.2f}%")
    k2.metric("Độ rộng (MBI)", "-" if pd.isna(last.mbi) else f"{last.mbi:+.2f}")
    k3.metric("Giá trị GD / TB cùng giờ", "chưa đủ lịch sử" if pd.isna(last.value_ratio) else f"{last.value_ratio:.2f}x")
    k4.metric("Mã đang theo dõi", len(symbols))
    k5.metric("Cảnh báo trong phiên", len(day_alerts))
    st.subheader(f"Trạng thái: {last.regime}")
    if last.divergence:
        st.warning("Chỉ số và độ rộng đang đi ngược chiều - biến động chỉ số có thể do một số ít mã trụ dẫn dắt.")
    latest = d_book.sort_values("minute").groupby("symbol").tail(1)
    fig = go.Figure(go.Heatmap(z=latest.sort_values("symbol")[["obi"]].T.values, x=latest.sort_values("symbol")["symbol"],
                               y=["OBI"], zmin=-1, zmax=1, colorscale="RdYlGn", colorbar=dict(title="OBI")))
    fig.update_layout(height=170, margin=dict(t=30, b=10), title="Mất cân bằng sổ lệnh (OBI) theo mã, phút gần nhất")
    st.plotly_chart(fig)

# ------------------------------------------------------------------ 2. thị trường
with tab2:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=d_idx.minute, y=d_idx.ret * 100, name="Lợi suất VN30 (%)"), secondary_y=False)
    fig.add_trace(go.Bar(x=d_idx.minute, y=d_idx.mbi, name="MBI", opacity=0.35), secondary_y=True)
    dv = d_idx[d_idx.divergence]
    fig.add_trace(go.Scatter(x=dv.minute, y=dv.ret * 100, mode="markers", name="Phân kỳ",
                             marker=dict(color="red", size=7)), secondary_y=False)
    fig.update_yaxes(title_text="Lợi suất (%)", secondary_y=False)
    fig.update_yaxes(title_text="MBI", range=[-1, 1], secondary_y=True)
    fig.update_layout(height=420, title="Lợi suất chỉ số vs độ rộng thị trường")
    st.plotly_chart(fig)
    st.dataframe(d_idx.regime.value_counts().rename("Số phút").reset_index().rename(columns={"regime": "Trạng thái"}),
                 hide_index=True)

# ------------------------------------------------------------------ 3. thanh khoản
with tab3:
    snap = d_book.sort_values("minute").groupby("symbol").tail(1).set_index("symbol")
    fl = flags[flags.session_date == day] if len(flags) else flags
    n_f = fl.sort_values("minute").groupby("symbol").tail(1).set_index("symbol")["n_flags"] if len(fl) else pd.Series(dtype=int)
    tbl = pd.DataFrame({"OBI": snap.obi, "WOBI": snap.wobi, "Spread (bps)": snap.spread_bps,
                        "Độ sâu (tỷ đ)": snap.depth_total / 1e9, "Depth ratio": snap.depth_ratio,
                        "Số điều kiện cảnh báo": n_f.reindex(snap.index)}).round(3).reset_index()
    st.dataframe(tbl.sort_values("Spread (bps)", ascending=False), hide_index=True)
    st.markdown(f"#### {sym}")
    s_df = d_book[d_book.symbol == sym]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Spread (bps)", "Độ sâu 5 mức (tỷ đ)", "OBI / WOBI"))
    fig.add_trace(go.Scatter(x=s_df.minute, y=s_df.spread_bps, name="Spread"), row=1, col=1)
    fig.add_trace(go.Scatter(x=s_df.minute, y=s_df.depth_total / 1e9, name="Độ sâu"), row=2, col=1)
    fig.add_trace(go.Scatter(x=s_df.minute, y=s_df.obi, name="OBI"), row=3, col=1)
    fig.add_trace(go.Scatter(x=s_df.minute, y=s_df.wobi, name="WOBI"), row=3, col=1)
    fig.update_layout(height=620, showlegend=True)
    st.plotly_chart(fig)
    lb = latest_book(db_path, source, sym)
    if lb:
        bids, asks = lb["bids"], lb["asks"]
        ob = go.Figure()
        ob.add_trace(go.Bar(y=[f"{p:,.0f}" for p, _ in bids], x=[q for _, q in bids], orientation="h", name="Mua"))
        ob.add_trace(go.Bar(y=[f"{p:,.0f}" for p, _ in asks], x=[q for _, q in asks], orientation="h", name="Bán"))
        ob.update_layout(height=380, title=f"Sổ lệnh gần nhất ({lb['ts'][11:19]})")
        st.plotly_chart(ob)
    st.download_button("Tải dữ liệu 1 phút của mã (CSV)", s_df.to_csv(index=False).encode("utf-8"),
                       f"vmap_{sym}_{day}.csv", "text/csv")

# ------------------------------------------------------------------ 4. cảnh báo
with tab4:
    if thr is None or thr.empty:
        st.info("Chưa đủ số phiên để hiệu chỉnh ngưỡng (cần tối thiểu 3 phiên trước đó). "
                "Hệ thống không phát cảnh báo khi chưa có ngưỡng - tránh đặt ngưỡng tùy ý.")
    else:
        a = alerts[alerts.severity.isin(sev_filter)] if len(alerts) else alerts
        a = a[a.start_ts.astype(str).str.startswith(day)] if len(a) else a
        if a.empty:
            st.success("Không có cảnh báo trong phiên đã chọn - đây cũng là kết quả hợp lệ.")
        else:
            show = a.rename(columns={"symbol": "Mã", "severity": "Mức", "start_ts": "Bắt đầu", "end_ts": "Hết hiệu lực",
                                     "reason": "Nguyên nhân", "closed_reason": "Cách kết thúc"})
            st.dataframe(show[["Mã", "Mức", "Bắt đầu", "Hết hiệu lực", "Nguyên nhân", "Cách kết thúc"]], hide_index=True)
            st.download_button("Tải danh sách cảnh báo (CSV)", a.to_csv(index=False).encode("utf-8"),
                               f"vmap_alerts_{day}.csv", "text/csv")
        with st.expander("Ngưỡng đang dùng cho từng mã (hiệu chỉnh từ các phiên trước)"):
            st.dataframe(thr.round(2).reset_index())

# ------------------------------------------------------------------ 5. phương pháp
with tab5:
    st.markdown("### Công thức")
    st.latex(r"MBI=\frac{A-D}{A+D+U}\qquad OBI_n=\frac{\sum_{i\le n}Q^{bid}_i-\sum_{i\le n}Q^{ask}_i}{\sum_{i\le n}Q^{bid}_i+\sum_{i\le n}Q^{ask}_i}")
    st.latex(r"WOBI=\frac{\sum_i Q^{bid}_i/i-\sum_i Q^{ask}_i/i}{\sum_i Q^{bid}_i/i+\sum_i Q^{ask}_i/i}\qquad "
             r"Spread_{bps}=\frac{P^{ask}_1-P^{bid}_1}{(P^{ask}_1+P^{bid}_1)/2}\times10^4")
    st.latex(r"Depth=\sum_{i\le 5}P_iQ_i\qquad z_t=\frac{x_t-\bar x_{t-W..t-1}}{\max(s_{t-W..t-1},0{,}1\,|\bar x|)}")
    st.markdown("""
**Quy tắc cảnh báo** (mỗi điều kiện đều cần *ngưỡng phân vị của chính mã đó* và *z-score cuộn* cùng thỏa):
1. *Spread mở rộng*: spread ≥ max(P95, 1,5×trung vị) và z ≥ 2.
2. *Độ sâu mỏng*: độ sâu ≤ P5 và z ≤ -2.
3. *Áp lực bán*: WOBI ≤ min(P5, -0,20).

Mức độ = số điều kiện đồng thời (1 = WATCH, 2 = WARNING, 3 = CRITICAL). Mở cảnh báo khi duy trì ≥ 2 phút; đóng khi hết tín hiệu 3 phút.
Ngưỡng được hiệu chỉnh walk-forward: chỉ dùng các phiên **trước** phiên đang xét.

### Giới hạn
- Sổ lệnh chỉ phản ánh các mức giá đang hiển thị; không thấy cung cầu tiềm ẩn. Lệnh có thể bị hủy ngay.
- OBI không phải xác suất giá tăng/giảm; spread không phải toàn bộ chi phí giao dịch; độ sâu không bảo đảm khớp lệnh.
- Mốc thời gian sàn có độ phân giải 1 giây; độ trễ chỉ đáng tin ở mức giây. Ngưỡng phụ thuộc mẫu quan sát (chưa chỉnh theo mùa vụ trong ngày).
- Chưa chứng minh quan hệ nhân quả giữa mất cân bằng sổ lệnh và biến động giá. **Không phải khuyến nghị mua/bán.**
""")

if auto:
    time.sleep(20)
    st.cache_data.clear()
    st.rerun()
