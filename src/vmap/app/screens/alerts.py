import pandas as pd
import streamlit as st


def render(bundle, day, selected_symbol="Tất cả mã"):
    st.header("TRUNG TÂM CẢNH BÁO")
    alerts=bundle["alerts"]
    if alerts.empty:
        st.info("Chưa có cảnh báo phù hợp. Hệ thống chỉ hiệu chỉnh ngưỡng sau tối thiểu số phiên huấn luyện theo cấu hình.")
        return
    a=alerts.copy()
    a["_date"]=pd.to_datetime(a.start_ts,errors="coerce").dt.strftime("%Y-%m-%d")
    a=a[a["_date"]==str(day)].drop(columns="_date")
    if selected_symbol != "Tất cả mã":
        a=a[a.symbol.astype(str)==selected_symbol]
    severity=st.multiselect("Mức độ",["WATCH","WARNING","CRITICAL"],default=["WATCH","WARNING","CRITICAL"])
    a=a[a.severity.isin(severity)]
    if a.empty:
        st.success("Không ghi nhận cảnh báo phù hợp bộ lọc trong phiên này.")
        return
    show=a.rename(columns={"symbol":"Mã","severity":"Mức độ","start_ts":"Bắt đầu","end_ts":"Kết thúc","reason":"Nguyên nhân","closed_reason":"Cách kết thúc"})
    st.dataframe(show[[c for c in ["Mã","Mức độ","Bắt đầu","Kết thúc","Nguyên nhân","Cách kết thúc"] if c in show]],use_container_width=True,hide_index=True)
    st.download_button("Xuất danh sách cảnh báo CSV",a.to_csv(index=False).encode("utf-8-sig"),f"vmap_alerts_{day}.csv","text/csv")
    thr=bundle.get("thr")
    if thr is not None and not thr.empty:
        with st.expander("Ngưỡng hiệu chỉnh gần nhất"):
            st.dataframe(thr.round(3),use_container_width=True)
