"""Thu thập dữ liệu SSI FastConnect (WebSocket) vào SQLite. CHỈ ĐỌC dữ liệu thị trường, không gửi lệnh.

Chạy:  python scripts/collect.py            (nên để chạy suốt các phiên giao dịch)
       python scripts/collect.py --refresh-components   (lấy rổ VN30 từ REST IndexComponents)
"""
import argparse
import logging
import signal
import threading

import _common  # noqa: F401
from vmap.config import load_settings
from vmap.data.collector import Collector
from vmap.data.db import Database
from vmap.logging_setup import setup_logging
from vmap.ssi.auth import SSIAuthError, TokenManager
from vmap.ssi.rest import SSIRestClient
from vmap.ssi.stream import StreamSupervisor

log = logging.getLogger("collect")


def build_tokens(s) -> TokenManager:
    return TokenManager(client_id=s.client_id, api_key=s.api_key, api_secret=s.api_secret,
                        private_key=s.private_key, api_url=s.api_url, streaming_url=s.streaming_url,
                        timeout_ms=s.timeout_ms, max_retries=s.max_retries,
                        rate_limit_per_second=s.rate_limit_per_second)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-components", action="store_true")
    a = ap.parse_args()
    setup_logging()
    s = load_settings()
    try:
        tokens = build_tokens(s)
        tokens.get()  # kiểm tra khoá sớm, lỗi thì dừng ngay thay vì chạy rỗng
    except SSIAuthError as e:
        raise SystemExit(f"Lỗi xác thực: {e}")
    if a.refresh_components:
        try:
            comps = SSIRestClient(s.api_url, tokens, s.rest_min_interval).index_components(s.index_code)
            if comps:
                s.symbols = comps
                s.stream_channels = []
                s.__post_init__()
                log.info("Rổ %s từ REST: %d mã", s.index_code, len(comps))
        except Exception as e:  # rổ dự phòng vẫn dùng được
            log.warning("Không lấy được danh sách thành phần (%s) -> dùng danh sách mặc định", e)
    db = Database(s.db_path)
    log.info("Ghi dữ liệu vào %s (lưu tin thô: %s)", s.db_path, s.store_raw)
    col = Collector(db, s, "live")
    sup = StreamSupervisor(s, col.handle_message, col.event, token_manager=tokens)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("Bắt đầu thu thập %d mã. Nhấn Ctrl+C để dừng.", len(s.symbols))
    try:
        sup.run_forever(stop)
    finally:
        col.flush()
        log.info("Đã dừng. Chất lượng dữ liệu: %s", dict(col.q.counts))


if __name__ == "__main__":
    main()
