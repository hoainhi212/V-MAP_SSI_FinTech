"""Trung tâm báo cáo: chỉ tạo PDF khi người dùng chủ động yêu cầu."""
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st

from vmap.config import ROOT
from vmap.reports.market_report import build_market_report
from vmap.reports.stock_report import build_stock_report
from vmap.reports.report_history import save_report, list_reports, get_report


def render_reports(bundle: dict, source: str):
    st.header("Trung tâm báo cáo")
    st.caption("Xuất PDF theo yêu cầu. Mỗi báo cáo tự động bao gồm toàn bộ nội dung phù hợp với loại báo cáo; không có lịch xuất tự động.")
    idx=bundle.get("idx",pd.DataFrame())
    book=bundle.get("book",pd.DataFrame())
    all_dates=[]
    for frame in (idx,book):
        if not frame.empty and "session_date" in frame:
            all_dates.extend(frame["session_date"].dropna().astype(str).tolist())
    if all_dates:
        min_date=pd.to_datetime(min(all_dates)).date()
        max_date=pd.to_datetime(max(all_dates)).date()
    else:
        min_date=max_date=date.today()
    history_db=ROOT/"data"/"report_history.sqlite"

    with st.form("vmap_report_form"):
        report_type=st.radio("Loại báo cáo",["Báo cáo tổng hợp thị trường","Báo cáo phân tích cổ phiếu"],horizontal=True)
        c1,c2=st.columns(2)
        start=c1.date_input("Từ ngày",value=min_date,min_value=min_date,max_value=max_date)
        end=c2.date_input("Đến ngày",value=max_date,min_value=min_date,max_value=max_date)
        symbol_options=sorted(book["symbol"].dropna().astype(str).unique()) if not book.empty and "symbol" in book else []
        symbol=None
        if report_type=="Báo cáo phân tích cổ phiếu":
            if symbol_options:
                symbol=st.selectbox("Mã cổ phiếu",symbol_options)
            else:
                symbol=st.text_input("Mã cổ phiếu",placeholder="Ví dụ: FPT").strip().upper()
        submitted=st.form_submit_button("Tạo báo cáo PDF",type="primary",use_container_width=True)

    if submitted:
        if start>end:
            st.error("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
        elif report_type=="Báo cáo phân tích cổ phiếu" and not symbol:
            st.error("Nhập mã cổ phiếu để tạo báo cáo.")
        else:
            try:
                with st.spinner("Đang tổng hợp dữ liệu và tạo PDF..."):
                    if report_type=="Báo cáo tổng hợp thị trường":
                        pdf=build_market_report(bundle,start,end,source)
                        slug="thi-truong"
                        sym=None
                    else:
                        pdf=build_stock_report(bundle,symbol,start,end,source)
                        slug=f"co-phieu-{symbol.lower()}"
                        sym=symbol.upper()
                    filename=f"V-MAP_{slug}_{start}_{end}.pdf"
                    report_id=save_report(history_db,report_type,sym,start,end,filename,pdf)
                st.success("Đã tạo báo cáo PDF.")
                st.download_button("Tải PDF vừa tạo",data=pdf,file_name=filename,mime="application/pdf",type="primary",key=f"new_pdf_{report_id}")
            except Exception as exc:
                st.error(f"Không thể tạo báo cáo: {exc}")

    st.divider()
    st.subheader("Lịch sử báo cáo đã tạo")
    rows=list_reports(history_db,limit=25)
    if not rows:
        st.info("Chưa có báo cáo nào. Lịch sử chỉ phát sinh sau khi người dùng bấm “Tạo báo cáo PDF”.")
    else:
        hist=pd.DataFrame(rows,columns=["ID","Loại báo cáo","Mã","Từ ngày","Đến ngày","Thời điểm tạo","Tên tệp"])
        st.dataframe(hist.drop(columns=["ID"]),use_container_width=True,hide_index=True)
        selected=st.selectbox("Chọn báo cáo trong lịch sử",hist["ID"].tolist(),format_func=lambda x: f"#{x} · {hist.loc[hist.ID==x,'Tên tệp'].iloc[0]}")
        saved=get_report(history_db,selected)
        if saved:
            st.download_button("Tải lại PDF từ lịch sử",data=saved[1],file_name=saved[0],mime="application/pdf",key=f"history_pdf_{selected}")
