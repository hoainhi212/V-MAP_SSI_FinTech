import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def render(bundle, day):
    st.header("Phân tích thị trường")
    idx=bundle["idx"]
    if idx.empty:
        st.info("Không có dữ liệu VN30 trong cơ sở dữ liệu.")
        return
    d=idx[idx.session_date==day].sort_values("minute")
    if d.empty:
        st.info("Không có dữ liệu cho phiên đã chọn.")
        return
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Scatter(x=d.minute,y=d.ret*100,name="Lợi suất VN30 (%)"),secondary_y=False)
    fig.add_trace(go.Scatter(x=d.minute,y=d.mbi,name="MBI",line=dict(color="#0C8C91")),secondary_y=True)
    div=d[d.divergence.fillna(False)]
    if not div.empty:
        fig.add_trace(go.Scatter(x=div.minute,y=div.ret*100,mode="markers",name="Phân kỳ",marker=dict(color="#D94B4B",size=8)),secondary_y=False)
    fig.update_yaxes(title_text="Lợi suất (%)",secondary_y=False)
    fig.update_yaxes(title_text="MBI",range=[-1,1],secondary_y=True)
    fig.update_layout(height=430,title="Lợi suất VN30 và độ rộng thị trường",hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)
    st.subheader("Phân bổ trạng thái")
    st.dataframe(d.regime.value_counts().rename_axis("Trạng thái").reset_index(name="Số phút"),use_container_width=True,hide_index=True)
    cols=[c for c in ["minute","index_value","ret","advances","declines","unchanged","mbi","regime","total_value","value_ratio","divergence"] if c in d]
    st.subheader("Dữ liệu chỉ số theo phút")
    st.dataframe(d[cols],use_container_width=True,hide_index=True)
