"""PDF renderer cho báo cáo V-MAP; dùng ReportLab Platypus và font Unicode."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, Image,
)

FONT_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "assets" / "fonts" / "DejaVuSans.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _font_name() -> str:
    if "VMapUnicode" not in pdfmetrics.getRegisteredFontNames():
        for path in FONT_CANDIDATES:
            if path.exists():
                pdfmetrics.registerFont(TTFont("VMapUnicode", str(path)))
                return "VMapUnicode"
        return "Helvetica"
    return "VMapUnicode"


def _cell(value):
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        value = "—"
    if isinstance(value, (float,)):
        value = f"{value:,.4f}".rstrip("0").rstrip(".")
    return Paragraph(escape(str(value)), ParagraphStyle(
        "table_cell", fontName=_font_name(), fontSize=7.3, leading=9,
        textColor=colors.HexColor("#514A68"), wordWrap="CJK"
    ))


def dataframe_table(df: pd.DataFrame, max_rows: int = 35):
    if df is None or df.empty:
        return [Paragraph("Không khả dụng / không có dữ liệu trong kỳ.", getSampleStyleSheet()["BodyText"])]
    view = df.head(max_rows).copy()
    data = [[_cell(c) for c in view.columns]]
    data.extend([[_cell(v) for v in row] for row in view.itertuples(index=False, name=None)])
    widths = [175 * mm / max(len(view.columns), 1)] * len(view.columns)
    table = Table(data, repeatRows=1, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#66578F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), _font_name()),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#E8E0F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF4F6")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    result = [table]
    if len(df) > max_rows:
        result.append(Paragraph(f"Hiển thị {max_rows}/{len(df)} dòng đầu tiên. Dữ liệu đầy đủ vẫn được giữ trong hệ thống.", getSampleStyleSheet()["Italic"]))
    return result


def generate_pdf(title: str, subtitle: str, metadata: dict, sections: list[dict]) -> bytes:
    """sections: [{heading, text?, table?}]"""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=14*mm, leftMargin=14*mm,
        topMargin=15*mm, bottomMargin=15*mm, title=title, author="V-MAP"
    )
    font = _font_name()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("VTitle", parent=styles["Title"], fontName=font,
                              fontSize=25, leading=31, textColor=colors.HexColor("#66578F"),
                              alignment=TA_LEFT, spaceAfter=5*mm))
    styles.add(ParagraphStyle("VSub", parent=styles["Normal"], fontName=font,
                              fontSize=10, leading=15, textColor=colors.HexColor("#526477")))
    styles.add(ParagraphStyle("VHead", parent=styles["Heading2"], fontName=font,
                              fontSize=14, leading=19, textColor=colors.HexColor("#78AFA0"),
                              spaceBefore=5*mm, spaceAfter=2*mm))
    styles.add(ParagraphStyle("VBody", parent=styles["BodyText"], fontName=font,
                              fontSize=8.5, leading=13, spaceAfter=2*mm))
    cover_brand = ParagraphStyle("CoverBrand", parent=styles["VSub"], fontName=font,
        fontSize=11, leading=16, textColor=colors.HexColor("#8D7BC4"), spaceAfter=8*mm)
    cover_title = ParagraphStyle("CoverTitle", parent=styles["VTitle"], fontName=font,
        fontSize=27, leading=35, textColor=colors.HexColor("#514A68"), spaceAfter=5*mm)
    cover_sub = ParagraphStyle("CoverSub", parent=styles["VSub"], fontName=font,
        fontSize=12, leading=18, textColor=colors.HexColor("#817891"))
    story = [
        Spacer(1, 12*mm),
        Paragraph("✿  V-MAP  ·  VIETNAM MARKET ALERT &amp; PULSE", cover_brand),
        Paragraph(escape(title), cover_title),
        Paragraph(escape(subtitle), cover_sub),
        Spacer(1, 8*mm),
    ]
    meta_rows = [[_cell(k), _cell(v)] for k, v in metadata.items()]
    if meta_rows:
        mt = Table(meta_rows, colWidths=[42*mm, 210*mm])
        mt.setStyle(TableStyle([
            ("FONTNAME", (0,0),(-1,-1),font), ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F0EBFF")),
            ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#E8E0F0")),
            ("LINEBEFORE",(0,0),(0,-1),2,colors.HexColor("#B7A9E4")),
            ("VALIGN",(0,0),(-1,-1),"TOP"), ("PADDING",(0,0),(-1,-1),5),
        ]))
        story.extend([mt, Spacer(1, 4*mm)])
    for section in sections:
        story.append(KeepTogether([
            Paragraph(escape(section.get("heading", "Nội dung")), styles["VHead"]),
            *([Paragraph(escape(section["text"]), styles["VBody"])] if section.get("text") else []),
        ]))
        if section.get("image"):
            story.append(Image(BytesIO(section["image"]), width=225*mm, height=82*mm, kind="proportional"))
            story.append(Spacer(1, 2*mm))
        if section.get("table") is not None:
            story.extend(dataframe_table(section["table"]))
        if section.get("items"):
            for item in section["items"]:
                story.append(Paragraph("• " + escape(str(item)), styles["VBody"]))
    generated = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#E8E0F0"))
        canvas.setLineWidth(.7)
        canvas.line(14*mm, 12*mm, landscape(A4)[0]-14*mm, 12*mm)
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#817891"))
        canvas.drawString(14*mm, 8*mm, f"V-MAP | Tạo lúc {generated} | Dữ liệu phụ thuộc nguồn và khoảng thời gian đã chọn")
        canvas.drawRightString(landscape(A4)[0]-14*mm, 8*mm, f"Trang {document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
