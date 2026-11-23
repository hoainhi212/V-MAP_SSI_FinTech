"""Client REST cho SSI FastConnect V3 Market Data thông qua ssi_sdk."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any

from ssi_sdk import Data, SSIError

from .auth import TokenManager

log = logging.getLogger(__name__)


class SSIApiError(RuntimeError):
    pass


def _to_plain(obj: Any) -> Any:
    """Chuyển dataclass / Enum / object của ssi_sdk về kiểu dữ liệu thuần Python."""
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_plain(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    return obj


class SSIRestClient:
    def __init__(
        self,
        rest_url: str = "https://api.ssi.com.vn",
        tokens: TokenManager | None = None,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: int = 20,
    ):
        if tokens is None:
            raise SSIApiError("Thiếu TokenManager cho SSIRestClient")
        self._rest_url = rest_url.rstrip("/")
        self._tokens = tokens
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._last_call = 0.0
        self._lock = threading.Lock()
        self._data: Data | None = None

    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    @property
    def market_data(self):
        with self._lock:
            self._tokens.get()
            if self._data is None:
                self._data = Data(self._tokens.auth)
            return self._data.market_data

    def _call_md(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        refreshed = False
        attempts = max(1, self._max_retries)
        for attempt in range(1, attempts + 1):
            self._throttle()
            md = self.market_data
            fn = getattr(md, method_name, None)
            if not callable(fn):
                raise SSIApiError(f"market_data không hỗ trợ phương thức '{method_name}'")
            try:
                return fn(*args, **kwargs)
            except SSIError as exc:
                msg = str(exc)
                if ("401" in msg or "token" in msg.lower() or "auth" in msg.lower()) and not refreshed:
                    log.warning("REST %s gặp lỗi xác thực, làm mới token và thử lại", method_name)
                    self._tokens.get(force=True)
                    with self._lock:
                        self._data = Data(self._tokens.auth)
                    refreshed = True
                    continue
                if attempt < attempts:
                    log.warning("REST %s lỗi (lần %d/%d): %s", method_name, attempt, attempts, exc)
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise SSIApiError(f"{method_name}: {exc}") from None
        raise SSIApiError(f"{method_name}: hết số lần thử")

    def index_components(self, index_code: str = "VN30") -> list[str]:
        """Lấy danh sách mã chứng khoán thuộc chỉ số (ví dụ VN30) qua V3."""
        items = self._call_md("get_securities_info_by_index", index_code.strip().upper())
        symbols: list[str] = []
        for raw in items or []:
            row = _to_plain(raw)
            if isinstance(row, dict):
                sym = row.get("symbol") or row.get("StockSymbol") or row.get("Symbol")
                if sym:
                    symbols.append(str(sym).strip().upper())
        return sorted(set(symbols))

    def index_summary(self, index_id: str = "VN30") -> dict[str, Any] | None:
        """Lấy thông tin tổng hợp hiện tại/gần nhất của chỉ số qua V3."""
        summary = self._call_md("get_index_summary", index_id.strip().upper())
        if summary is None:
            return None
        plain = _to_plain(summary)
        return plain if isinstance(plain, dict) else {"value": plain}

    def daily_index(self, index_id: str, start: date, end: date) -> list[dict[str, Any]]:
        """Lấy dữ liệu chỉ số theo từng ngày giao dịch trong khoảng [start, end]."""
        code = index_id.strip().upper()
        md = self.market_data
        if not hasattr(md, "get_index_summary_historical"):
            cur = self.index_summary(code)
            return [cur] if cur else []

        rows: list[dict[str, Any]] = []
        cur_date = start
        while cur_date <= end:
            if cur_date.weekday() < 5:
                date_str = cur_date.strftime("%Y/%m/%d")
                try:
                    item = self._call_md("get_index_summary_historical", code, date_str)
                except SSIApiError as exc:
                    log.debug("Không lấy được lịch sử %s ngày %s: %s", code, date_str, exc)
                    item = None
                if item is not None:
                    plain = _to_plain(item)
                    if isinstance(plain, dict):
                        rows.append(plain)
            cur_date += timedelta(days=1)
        return rows

    def ohlc_1minute(self, symbol: str) -> list[dict[str, Any]]:
        """Lấy dữ liệu OHLC 1 phút cho mã chứng khoán."""
        rows = self._call_md("get_ohlc_1minute", symbol.strip().upper())
        plain_rows = [_to_plain(r) for r in (rows or [])]
        return [r for r in plain_rows if isinstance(r, dict)]

    def close(self) -> None:
        with self._lock:
            if self._data is not None and hasattr(self._data, "close"):
                try:
                    self._data.close()
                except Exception:
                    pass
            self._data = None