"""Chuẩn bị nội dung báo cáo tổng hợp từ bundle đã tính cho dashboard."""
import pandas as pd
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .pdf_generator import generate_pdf


def _period(df, date_col, start, end):
    if df is None or df.empty or date_col not in df:
        return pd.DataFrame()
    s = df.copy()
    s["_date"] = pd.to_datetime(s[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    return s[s["_date"].between(str(start), str(end))].drop(columns="_date")


def _market_chart(idx):
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(pd.to_datetime(idx["minute"]), idx["index_value"], label="VN30")
    ax.set_title("Diễn biến VN30 trong kỳ")
    ax.set_ylabel("Điểm chỉ số")
    ax.grid(True, alpha=.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    out=BytesIO()
    fig.savefig(out,format="png",dpi=140)
    plt.close(fig)
    return out.getvalue()


def build_market_report(bundle: dict, start, end, source: str) -> bytes:
    idx = _period(bundle.get("idx"), "session_date", start, end)
    book = _period(bundle.get("book"), "session_date", start, end)
    alerts = bundle.get("alerts", pd.DataFrame())
    if not alerts.empty and "start_ts" in alerts:
        dates = pd.to_datetime(alerts["start_ts"], errors="coerce").dt.strftime("%Y-%m-%d")
        alerts = alerts[dates.between(str(start), str(end))]
    sections = []
    if not idx.empty:
        latest = idx.sort_values("minute").iloc[-1]
        summary = [
            f"Số phút dữ liệu chỉ số: {len(idx):,}.",
            f"VN30 cuối kỳ: {latest.get('index_value', float('nan')):,.2f}.",
            f"MBI cuối kỳ: {latest.get('mbi', float('nan')):.3f}." if pd.notna(latest.get("mbi")) else "MBI cuối kỳ: không khả dụng.",
            f"Số thời điểm phân kỳ: {int(idx['divergence'].fillna(False).sum()) if 'divergence' in idx else 0}.",
        ]
        sections.append({"heading":"Tóm tắt trạng thái thị trường", "items":summary})
        cols=[c for c in ["minute","index_value","ret","advances","declines","unchanged","mbi","regime","total_value","value_ratio","divergence"] if c in idx]
        sections.append({"heading":"Biểu đồ VN30", "image":_market_chart(idx)})
        sections.append({"heading":"Diễn biến VN30 và độ rộng thị trường", "text":"Bảng thể hiện dữ liệu theo phút đã tổng hợp từ nguồn được chọn.", "table":idx[cols].tail(60)})
    else:
        sections.append({"heading":"Diễn biến VN30 và độ rộng thị trường", "text":"Không khả dụng: không có dữ liệu chỉ số trong khoảng thời gian đã chọn."})
    if not book.empty:
        agg = book.groupby("symbol",as_index=False).agg(
            so_phut=("minute","count"), OBI=("obi","mean"), WOBI=("wobi","mean"),
            spread_bps=("spread_bps","mean"), depth_total=("depth_total","mean"),
            depth_ratio=("depth_ratio","mean"))
        agg["depth_total_ty"] = agg.pop("depth_total") / 1e9
        sections.append({"heading":"Tổng hợp thanh khoản các cổ phiếu", "text":"Các chỉ báo là trung bình theo phút trong kỳ; độ sâu được quy đổi sang tỷ đồng.", "table":agg.sort_values("spread_bps",ascending=False).round(4)})
        cols=[c for c in ["minute","symbol","obi","wobi","spread_bps","depth_total","depth_ratio","n_snap"] if c in book]
        sections.append({"heading":"Diễn biến chỉ báo thanh khoản", "table":book[cols].tail(80)})
    else:
        sections.append({"heading":"Thanh khoản cổ phiếu", "text":"Không khả dụng: không có dữ liệu sổ lệnh hợp lệ trong kỳ."})
    if not alerts.empty:
        sections.append({"heading":"Tổng hợp cảnh báo", "items":[
            f"Tổng số cảnh báo: {len(alerts)}.",
            "Phân bổ mức độ: " + ", ".join(f"{k}: {v}" for k,v in alerts["severity"].value_counts().items()) if "severity" in alerts else "Không có trường mức độ."
        ], "table":alerts[[c for c in ["symbol","severity","start_ts","end_ts","reason","closed_reason"] if c in alerts]].tail(50)})
    else:
        sections.append({"heading":"Tổng hợp cảnh báo", "text":"Không ghi nhận cảnh báo trong kỳ hoặc dữ liệu cảnh báo không khả dụng. Không đồng nghĩa rủi ro bằng 0."})
    sections.append({"heading":"Chất lượng dữ liệu và giới hạn", "items":[
        f"Nguồn dữ liệu: {source}.",
        "Báo cáo chỉ phản ánh bản ghi hiện có trong cơ sở dữ liệu và khoảng thời gian được chọn.",
        "Các ô hoặc nhóm chỉ tiêu không có dữ liệu được ghi rõ là không khả dụng; không nội suy hay tự tạo số liệu.",
        "MBI và các chỉ báo sổ lệnh là chỉ báo mô tả, không phải xác suất hay khuyến nghị mua/bán.",
        "Dữ liệu mô phỏng (nếu chọn source=simulated) chỉ phục vụ kiểm thử quy trình, không đại diện thị trường thực."
    ]})
    metadata={"Loại báo cáo":"Báo cáo tổng hợp thị trường","Từ ngày":str(start),"Đến ngày":str(end),"Nguồn":source,
              "Số phiên có dữ liệu":str(idx["session_date"].nunique()) if not idx.empty else "Không khả dụng"}
    return generate_pdf("BÁO CÁO TỔNG HỢP THỊ TRƯỜNG", "Giám sát trạng thái VN30 và rủi ro thanh khoản cổ phiếu", metadata, sections)
