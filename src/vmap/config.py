"""Cấu hình trung tâm. Mọi bí mật đọc từ biến môi trường / .env, không hard-code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # UTC+7, dùng nhất quán toàn hệ thống
ROOT = Path(__file__).resolve().parents[2]

# Rổ VN30 dự phòng khi gọi REST lấy danh sách thành phần không được. Rổ đổi 6 tháng/lần,
# nên LUÔN ưu tiên lấy từ API và đối chiếu lại trước khi nộp bài.
DEFAULT_VN30 = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
]

# Phiên khớp lệnh liên tục HOSE (bỏ ATO/ATC vì sổ lệnh không có nghĩa thanh khoản bình thường)
CONTINUOUS_SESSIONS = [(time(9, 15), time(11, 30)), (time(13, 0), time(14, 30))]
MARKET_HOURS = [(time(9, 0), time(11, 30)), (time(13, 0), time(14, 45))]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "yes")


@dataclass
class Settings:
    client_id: str = ""
    api_key: str = ""
    api_secret: str = ""
    private_key: str = ""

    api_url: str = "https://api.ssi.com.vn"
    streaming_url: str = "wss://stream.ssi.com.vn/ws/v3"

    # Giữ tương thích tên cũ nếu có module khác tham chiếu
    consumer_id: str = ""
    consumer_secret: str = ""
    rest_url: str = "https://api.ssi.com.vn"
    stream_url: str = "wss://stream.ssi.com.vn/ws/v3"

    index_code: str = "VN30"
    index_channel: str = "MI:VN30"
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_VN30))
    stream_channels: list[str] = field(default_factory=list)
    db_path: str = str(ROOT / "data" / "vmap_live.db")
    store_raw: bool = True
    rest_min_interval: float = 1.0
    timeout_ms: int = 60000
    max_retries: int = 5
    rate_limit_per_second: int = 10

    # --- tham số phương pháp (xem docs/methodology.md để biết cơ sở chọn) ---
    obi_levels: int = 3
    depth_levels: int = 5
    price_scale: float = 1.0       # nhân giá SSI về VND nếu API trả theo nghìn đồng
    heartbeat_timeout: int = 180    # giây không có tin trong giờ giao dịch => coi là mất kết nối
    stale_after: int = 30          # giây: dữ liệu cũ hơn mức này bị gắn cờ "stale"
    late_tolerance: int = 2        # giây: tin có mốc thời gian lùi quá mức này bị coi là đến muộn

    def __post_init__(self):
        if not self.client_id and self.consumer_id:
            self.client_id = self.consumer_id
        if not self.api_secret and self.consumer_secret:
            self.api_secret = self.consumer_secret

        self.api_url = (self.api_url or self.rest_url or "https://api.ssi.com.vn").rstrip("/")
        self.streaming_url = self.streaming_url or self.stream_url or "wss://stream.ssi.com.vn/ws/v3"
        self.rest_url = self.api_url
        self.stream_url = self.streaming_url

        if not self.stream_channels:
            syms = ",".join(self.symbols)
            self.stream_channels = [f"X-QUOTE:{syms}", f"X-TRADE:{syms}", self.index_channel]


def load_settings() -> Settings:
    if load_dotenv:
        load_dotenv(ROOT / ".env", override=True)

    symbols = [s.strip().upper() for s in os.getenv("VMAP_SYMBOLS", "").split(",") if s.strip()]
    channels = [c.strip() for c in os.getenv("VMAP_STREAM_CHANNELS", "").split(";") if c.strip()]

    client_id = (os.getenv("SSI_CLIENT_ID") or os.getenv("SSI_CONSUMER_ID") or "").strip()
    api_key = (os.getenv("SSI_API_KEY") or "").strip()
    api_secret = (os.getenv("SSI_API_SECRET") or os.getenv("SSI_CONSUMER_SECRET") or "").strip()
    private_key = (os.getenv("SSI_PRIVATE_KEY") or "").strip()

    api_url = (os.getenv("SSI_API_URL") or os.getenv("SSI_REST_URL") or "https://api.ssi.com.vn").strip()
    streaming_url = (
        os.getenv("SSI_STREAMING_URL") or os.getenv("SSI_STREAM_URL") or "wss://stream.ssi.com.vn/ws/v3"
    ).strip()

    return Settings(
        client_id=client_id,
        api_key=api_key,
        api_secret=api_secret,
        private_key=private_key,
        api_url=api_url,
        streaming_url=streaming_url,
        consumer_id=client_id,
        consumer_secret=api_secret,
        rest_url=api_url,
        stream_url=streaming_url,
        index_code=os.getenv("VMAP_INDEX_CODE", "VN30").strip().upper(),
        index_channel=os.getenv("VMAP_INDEX_CHANNEL", "MI:VN30").strip(),
        symbols=symbols or list(DEFAULT_VN30),
        stream_channels=channels,
        db_path=os.getenv("VMAP_DB_PATH", str(ROOT / "data" / "vmap_live.db")).strip(),
        store_raw=_bool("VMAP_STORE_RAW", True),
        rest_min_interval=float(os.getenv("VMAP_REST_MIN_INTERVAL", "1.0")),
        timeout_ms=int(os.getenv("SSI_TIMEOUT_MS", "60000")),
        max_retries=int(os.getenv("SSI_MAX_RETRIES", "5")),
        rate_limit_per_second=int(os.getenv("SSI_RATE_LIMIT_PER_SECOND", "10")),
    )


def in_hours(t: time, windows) -> bool:
    return any(a <= t <= b for a, b in windows)