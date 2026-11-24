"""Dò luồng SSI V3: in MỌI callback của Stream để biết tin giá đi về đâu.

Chạy trong giờ giao dịch, khoảng 90 giây:
    python scripts/probe_stream.py
Không ghi vào database, không in token hay khóa.
"""
import inspect
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ssi_sdk import Stream  # noqa: E402

from vmap.config import load_settings  # noqa: E402
from vmap.ssi.auth import TokenManager  # noqa: E402

SYMBOLS = ["FPT", "VCB", "HPG"]   # vài mã thanh khoản cao là đủ để thử
counts: dict[str, int] = {}


def make_printer(name):
    def _p(*args, **kwargs):
        counts[name] = counts.get(name, 0) + 1
        if counts[name] <= 5:  # chỉ in 5 lần đầu của mỗi callback
            body = " | ".join(repr(a)[:300] for a in args)
            print(f"[{time.strftime('%H:%M:%S')}] {name} #{counts[name]}: {body}", flush=True)
    return _p


def main(seconds: int = 90) -> None:
    s = load_settings()
    tokens = TokenManager(client_id=s.client_id, api_key=s.api_key, api_secret=s.api_secret,
                          private_key=s.private_key, api_url=s.api_url, streaming_url=s.streaming_url,
                          timeout_ms=s.timeout_ms, max_retries=s.max_retries,
                          rate_limit_per_second=s.rate_limit_per_second)
    tokens.get()
    with Stream(tokens.auth) as client:
        st = client.streaming
        hooks = [n for n in dir(st) if n.startswith("on_")]
        print("Các callback SDK có:", hooks, flush=True)
        for n in hooks:
            cur = getattr(st, n)
            if inspect.ismethod(cur):   # phương thức nội bộ của SDK: không ghi đè
                print(f"  bỏ qua {n} (phương thức nội bộ)")
                continue
            setattr(st, n, make_printer(n))
        st.connect()
        st.subscribe_symbol_trade(SYMBOLS)
        st.subscribe_symbol_quote(SYMBOLS)
        st.subscribe_index_summary(s.index_code)
        if hasattr(st, "list_subscription"):
            try:
                print("Đang đăng ký:", st.list_subscription(), flush=True)
            except Exception as e:
                print("list_subscription lỗi:", type(e).__name__, e)
        threading.Thread(target=st.wait, daemon=True).start()
        print(f"Đang lắng nghe {seconds} giây...", flush=True)
        time.sleep(seconds)
        print("\nSố lần mỗi callback được gọi:", counts or "KHÔNG CÓ CALLBACK NÀO ĐƯỢC GỌI")
        try:
            st.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
