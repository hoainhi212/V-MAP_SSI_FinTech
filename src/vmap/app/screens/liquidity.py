import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def render(bundle, day):
    st.header("Giám sát thanh khoản")
    book=bundle["book"]
    if book.empty:
        st.info("Không có dữ liệu sổ lệnh hợp lệ.")
        return
    d=book[book.session_date==day]
    if d.empty:
        st.info("Không có dữ liệu sổ lệnh cho phiên đã chọn.")
        return
    symbols=sorted(d.symbol.unique())
    sym=st.selectbox("Mã cổ phiếu",symbols,key="liquidity_symbol")
    s=d[d.symbol==sym].sort_values("minute")
    latest=s.iloc[-1]
    k=st.columns(5)
    for col,label,key,fmt in [
        (k[0],"OBI","obi","{:+.3f}"),(k[1],"WOBI","wobi","{:+.3f}"),
        (k[2],"Spread (bps)","spread_bps","{:.2f}"),(k[3],"Độ sâu (tỷ đồng)","depth_total","{:.3f}"),
        (k[4],"Depth ratio","depth_ratio","{:.3f}")]:
        value=latest.get(key)
        col.metric(label,fmt.format(value/1e9 if key=="depth_total" and pd.notna(value) else value) if pd.notna(value) else "—")
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,subplot_titles=("Spread (bps)","Độ sâu sổ lệnh (tỷ đồng)","OBI và WOBI"))
    fig.add_trace(go.Scatter(x=s.minute,y=s.spread_bps,name="Spread"),row=1,col=1)
    fig.add_trace(go.Scatter(x=s.minute,y=s.depth_total/1e9,name="Depth"),row=2,col=1)
    fig.add_trace(go.Scatter(x=s.minute,y=s.obi,name="OBI"),row=3,col=1)
    fig.add_trace(go.Scatter(x=s.minute,y=s.wobi,name="WOBI"),row=3,col=1)
    fig.update_layout(height=650,hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)
    cols=[c for c in ["minute","obi","wobi","spread_bps","spread_ticks","depth_bid","depth_ask","depth_total","depth_ratio","n_snap"] if c in s]
    st.subheader("Bảng dữ liệu theo phút")
    st.dataframe(s[cols],use_container_width=True,hide_index=True)
    st.download_button("Xuất dữ liệu CSV",s.to_csv(index=False).encode("utf-8-sig"),f"vmap_{sym}_{day}.csv","text/csv")
