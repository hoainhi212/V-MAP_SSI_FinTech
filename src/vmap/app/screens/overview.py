import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render(bundle, source, status, day=None):
    st.header("TỔNG QUAN")
    idx,book,alerts=bundle["idx"],bundle["book"],bundle["alerts"]
    if idx.empty:
        st.info("Chưa có dữ liệu chỉ số để hiển thị.")
        return
    dates=sorted(idx["session_date"].dropna().unique())
    day=day or dates[-1]
    di=idx[idx.session_date==day]
    db=book[book.session_date==day] if not book.empty else book
    last=di.sort_values("minute").iloc[-1]
    da=alerts[pd.to_datetime(alerts["start_ts"],errors="coerce").dt.strftime("%Y-%m-%d")==str(day)] if not alerts.empty else alerts
    cols=st.columns(5)
    cols[0].metric("VN30",f"{last['index_value']:,.2f}",f"{last['ret']*100:+.2f}%" if pd.notna(last.get("ret")) else None)
    cols[1].metric("MBI",f"{last['mbi']:+.3f}" if pd.notna(last.get("mbi")) else "—")
    cols[2].metric("Giá trị GD / TB cùng giờ",f"{last['value_ratio']:.2f}x" if pd.notna(last.get("value_ratio")) else "Chưa đủ LS")
    cols[3].metric("Mã có dữ liệu",str(db.symbol.nunique()) if not db.empty else "—")
    cols[4].metric("Cảnh báo",str(len(da)))
    st.caption(f"Phiên {day} · Nguồn: {source} · {status.get('label','')}")
    st.subheader(f"TRẠNG THÁI THỊ TRƯỜNG: {last.get('regime','—')}")
    if bool(last.get("divergence",False)):
        st.warning("Chỉ số và độ rộng thị trường đang phân kỳ. Diễn biến chỉ số có thể chưa phản ánh đồng đều toàn bộ rổ.")
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=di.minute,y=di.index_value,name="VN30",line=dict(width=2)))
    fig.update_layout(height=330,margin=dict(l=10,r=10,t=25,b=10),yaxis_title="Điểm")
    st.plotly_chart(fig,use_container_width=True)
    if not db.empty:
        latest=db.sort_values("minute").groupby("symbol").tail(1)
        heat=go.Figure(go.Heatmap(z=[latest.sort_values("symbol").obi],x=latest.sort_values("symbol").symbol,y=["OBI"],zmin=-1,zmax=1,colorscale="RdYlGn"))
        heat.update_layout(height=190,margin=dict(l=10,r=10,t=25,b=10),title="Mất cân bằng sổ lệnh theo mã")
        st.plotly_chart(heat,use_container_width=True)
