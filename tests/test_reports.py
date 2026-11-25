from datetime import date
import pandas as pd

from vmap.reports.market_report import build_market_report
from vmap.reports.stock_report import build_stock_report
from vmap.reports.report_history import save_report, list_reports, get_report


def sample_bundle():
    return {
        "idx": pd.DataFrame([{
            "session_date":"2026-11-24","minute":pd.Timestamp("2026-11-24 09:16"),
            "index_value":1800.1,"ret":0.002,"advances":18,"declines":9,
            "unchanged":3,"mbi":0.3,"regime":"Tăng đồng thuận",
            "divergence":False,"total_value":1e9,"value_ratio":1.1
        }]),
        "book": pd.DataFrame([{
            "session_date":"2026-11-24","minute":pd.Timestamp("2026-11-24 09:16"),
            "symbol":"FPT","obi":0.2,"wobi":0.1,"spread_bps":5.0,
            "spread_ticks":1.0,"depth_bid":1e9,"depth_ask":0.8e9,
            "depth_total":1.8e9,"depth_ratio":1.25,"n_snap":4
        }]),
        "alerts": pd.DataFrame(columns=["symbol","severity","start_ts","end_ts","reason","closed_reason"])
    }


def test_market_report_returns_pdf():
    pdf=build_market_report(sample_bundle(),date(2026,11,24),date(2026,11,24),"simulated")
    assert pdf.startswith(b"%PDF-")


def test_stock_report_returns_pdf():
    pdf=build_stock_report(sample_bundle(),"FPT",date(2026,11,24),date(2026,11,24),"simulated")
    assert pdf.startswith(b"%PDF-")


def test_report_history_roundtrip(tmp_path):
    path=tmp_path/"history.sqlite"
    report_id=save_report(path,"market",None,"2026-11-24","2026-11-24","market.pdf",b"%PDF-test")
    assert list_reports(path)[0][0] == report_id
    assert get_report(path,report_id) == ("market.pdf",b"%PDF-test")
