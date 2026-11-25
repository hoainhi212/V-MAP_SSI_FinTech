"""Chuẩn bị nội dung báo cáo phân tích một cổ phiếu từ bundle dashboard."""
import pandas as pd
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .pdf_generator import generate_pdf
from .market_report import _period


def _stock_chart(book):
    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    x=pd.to_datetime(book["minute"])
    axes[0].plot(x,book["spread_bps"],label="Spread (bps)")
    axes[0].set_ylabel("bps")
    axes[0].set_title("Diễn biến spread")
    axes[1].plot(x,book["obi"],label="OBI")
    axes[1].plot(x,book["wobi"],label="WOBI")
    axes[1].axhline(0,linewidth=.7)
    axes[1].set_ylim(-1,1)
    axes[1].set_title("Mất cân bằng sổ lệnh")
    axes[1].legend()
    for ax in axes: ax.grid(True,alpha=.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    out=BytesIO()
    fig.savefig(out,format="png",dpi=140)
    plt.close(fig)
    return out.getvalue()


def build_stock_report(bundle: dict, symbol: str, start, end, source: str) -> bytes:
    sym = symbol.upper().strip()
    book = _period(bundle.get("book"), "session_date", start, end)
    book = book[book["symbol"].astype(str).str.upper() == sym] if not book.empty and "symbol" in book else pd.DataFrame()
    alerts = bundle.get("alerts", pd.DataFrame())
    if not alerts.empty and "start_ts" in alerts:
        d = pd.to_datetime(alerts["start_ts"], errors="coerce").dt.strftime("%Y-%m-%d")
        alerts = alerts[d.between(str(start), str(end))]
        alerts = alerts[alerts["symbol"].astype(str).str.upper() == sym] if "symbol" in alerts else pd.DataFrame()
    sections=[]
    if not book.empty:
        latest=book.sort_values("minute").iloc[-1]
        sections.append({"heading":"Tóm tắt chỉ báo trong kỳ","items":[
            f"Số phút có dữ liệu hợp lệ: {len(book):,}.",
            f"OBI trung bình: {book['obi'].mean():.3f}." if book["obi"].notna().any() else "OBI: không khả dụng.",
            f"WOBI trung bình: {book['wobi'].mean():.3f}." if book["wobi"].notna().any() else "WOBI: không khả dụng.",
            f"Spread trung bình: {book['spread_bps'].mean():.2f} bps." if book["spread_bps"].notna().any() else "Spread: không khả dụng.",
            f"Độ sâu trung bình: {book['depth_total'].mean()/1e9:.3f} tỷ đồng." if book["depth_total"].notna().any() else "Độ sâu: không khả dụng.",
            f"Depth ratio cuối kỳ: {latest['depth_ratio']:.3f}." if pd.notna(latest.get("depth_ratio")) else "Depth ratio cuối kỳ: không khả dụng."
        ]})
        cols=[c for c in ["minute","obi","wobi","spread_bps","spread_ticks","depth_bid","depth_ask","depth_total","depth_ratio","n_snap"] if c in book]
        sections.append({"heading":"Biểu đồ chỉ báo thanh khoản", "image":_stock_chart(book)})
        sections.append({"heading":"Diễn biến chỉ báo theo phút","text":"Độ sâu bid/ask/tổng được tính theo giá trị VND; bảng trình bày tối đa 80 mốc gần nhất.", "table":book[cols].tail(80)})
        abnormal=book.sort_values("spread_bps",ascending=False).head(10)
        sections.append({"heading":"Các thời điểm spread cao nhất","table":abnormal[[c for c in ["minute","spread_bps","depth_total","obi","wobi"] if c in abnormal]].round(4)})
    else:
        sections.append({"heading":"Chỉ báo thanh khoản","text":f"Không khả dụng: không có dữ liệu sổ lệnh hợp lệ cho {sym} trong khoảng thời gian đã chọn."})
    if not alerts.empty:
        sections.append({"heading":"Lịch sử cảnh báo của cổ phiếu","table":alerts[[c for c in ["severity","start_ts","end_ts","reason","closed_reason"] if c in alerts]].tail(100)})
    else:
        sections.append({"heading":"Lịch sử cảnh báo","text":"Không ghi nhận cảnh báo cho mã trong kỳ hoặc dữ liệu cảnh báo không khả dụng. Không đồng nghĩa rủi ro bằng 0."})
    sections.append({"heading":"Phạm vi và giới hạn diễn giải","items":[
        f"Mã cổ phiếu: {sym}. Nguồn dữ liệu: {source}.",
        "Bộ dữ liệu hiện có trong dự án hỗ trợ phân tích sổ lệnh và các chỉ báo thanh khoản. Không tự suy diễn giá lịch sử/khối lượng khớp nếu dữ liệu đó không có trong bundle.",
        "OBI/WOBI phản ánh mất cân bằng khối lượng hiển thị; không phải xác suất giá tăng hoặc giảm.",
        "Spread không đại diện toàn bộ chi phí giao dịch; độ sâu không bảo đảm lệnh sẽ được khớp.",
        "Dữ liệu mô phỏng chỉ phục vụ kiểm thử, không đại diện thị trường thực."
    ]})
    metadata={"Loại báo cáo":"Báo cáo phân tích cổ phiếu","Mã cổ phiếu":sym,"Từ ngày":str(start),"Đến ngày":str(end),"Nguồn":source}
    return generate_pdf(f"BÁO CÁO PHÂN TÍCH CỔ PHIẾU {sym}", "Giám sát thanh khoản và cảnh báo rủi ro", metadata, sections)
