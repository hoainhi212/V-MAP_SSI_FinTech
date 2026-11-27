"""Real-time WebSocket streaming qua `ssi_sdk.Stream` (FastConnect V3), kèm watchdog và reconnect."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from ssi_sdk import Stream

from ..config import MARKET_HOURS, VN_TZ, Settings, in_hours
from .auth import TokenManager

log = logging.getLogger(__name__)
EventCb = Callable[[str, str], None]  # (event_type, detail)


def _serialize_message(message: Any) -> str:
    """Chuẩn hóa payload từ Stream (str / dict / dataclass / SDK model) sang chuỗi JSON/text."""
    if isinstance(message, str):
        return message
    if isinstance(message, Enum):
        return json.dumps(message.value, ensure_ascii=False)
    if is_dataclass(message) and not isinstance(message, type):
        return json.dumps(asdict(message), ensure_ascii=False, default=str)
    if isinstance(message, dict):
        return json.dumps(message, ensure_ascii=False, default=str)
    if hasattr(message, "to_dict") and callable(message.to_dict):
        return json.dumps(message.to_dict(), ensure_ascii=False, default=str)
    if hasattr(message, "__dict__"):
        data = {k: v for k, v in vars(message).items() if not k.startswith("_")}
        return json.dumps(data, ensure_ascii=False, default=str)
    return str(message)


def _parse_channels(
    raw_channels: list[str],
    default_symbols: list[str],
    default_index: str,
) -> tuple[list[str], list[str], list[str]]:
    """Tách danh sách kênh cấu hình (ví dụ 'X-QUOTE:ACB,FPT', 'X-TRADE:ACB,FPT', 'MI:VN30')."""
    quote_syms: list[str] = []
    trade_syms: list[str] = []
    index_ids: list[str] = []

    for ch in raw_channels or []:
        entry = ch.strip()
        if not entry:
            continue
        upper = entry.upper()
        if ":" in upper:
            prefix, rest = upper.split(":", 1)
            items = [x.strip() for x in rest.split(",") if x.strip()]
            if "QUOTE" in prefix or prefix in ("Q", "X-QUOTE"):
                quote_syms.extend(items)
            elif "TRADE" in prefix or prefix in ("T", "X-TRADE"):
                trade_syms.extend(items)
            elif "INDEX" in prefix or prefix in ("MI", "X-INDEX"):
                index_ids.extend(items)
            else:
                index_ids.append(upper)
        else:
            index_ids.append(upper)

    if not quote_syms and not trade_syms and default_symbols:
        quote_syms = list(default_symbols)
        trade_syms = list(default_symbols)
    if not index_ids and default_index:
        index_ids = [default_index.strip().upper()]

    return (
        sorted(set(s.upper() for s in quote_syms)),
        sorted(set(s.upper() for s in trade_syms)),
        sorted(set(i.upper() for i in index_ids)),
    )


def _subscribe_all(streaming: Any, settings: Settings) -> list[str]:
    """Đăng ký các kênh theo cấu hình trên `client.streaming` của `ssi_sdk`."""
    quote_syms, trade_syms, index_ids = _parse_channels(
        settings.stream_channels,
        settings.symbols,
        settings.index_code,
    )
    registered: list[str] = []

    if trade_syms and callable(getattr(streaming, "subscribe_symbol_trade", None)):
        streaming.subscribe_symbol_trade(trade_syms)
        registered.append(f"trade({len(trade_syms)})")

    if quote_syms and callable(getattr(streaming, "subscribe_symbol_quote", None)):
        streaming.subscribe_symbol_quote(quote_syms)
        registered.append(f"quote({len(quote_syms)})")

    for idx in index_ids:
        if callable(getattr(streaming, "subscribe_index_summary", None)):
            streaming.subscribe_index_summary([idx])
            registered.append(f"index_summary:{idx}")
        elif callable(getattr(streaming, "subscribe_index", None)):
            streaming.subscribe_index(idx)
            registered.append(f"index:{idx}")

    return registered


class StreamSupervisor:
    def __init__(
        self,
        settings: Settings,
        handler: Callable[[str], object],
        on_event: EventCb,
        token_manager: TokenManager | None = None,
    ):
        self.s = settings
        self.handler = handler
        self.on_event = on_event
        self._tokens = token_manager or TokenManager(
            client_id=settings.client_id,
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            private_key=settings.private_key,
            api_url=settings.api_url,
            streaming_url=settings.streaming_url,
            timeout_ms=settings.timeout_ms,
            max_retries=settings.max_retries,
            rate_limit_per_second=settings.rate_limit_per_second,
        )
        self._last_msg = time.monotonic()
        self._lost_at: float | None = None
        self._active_stream: Stream | None = None

    def _touch_alive(self) -> None:
        self._last_msg = time.monotonic()
        if self._lost_at is not None:
            self.on_event("reconnected", f"duration_sec={time.monotonic() - self._lost_at:.1f}")
            self._lost_at = None

    def _on_message(self, message: Any) -> None:
        self._touch_alive()
        try:
            self.handler(_serialize_message(message))
        except Exception:
            log.exception("Lỗi khi xử lý thông điệp streaming")

    def _on_heartbeat(self, *args: Any, **kwargs: Any) -> None:
        self._touch_alive()

    def _on_connection(self, connected: Any, *args: Any) -> None:
        if connected is False:
            self.on_event("stream_error", f"connection_state={connected}")

    def _disconnect_active(self) -> None:
        stream = self._active_stream
        self._active_stream = None
        if stream is None:
            return
        try:
            streaming = getattr(stream, "streaming", None)
            if streaming is not None and hasattr(streaming, "disconnect"):
                streaming.disconnect()
        except Exception:
            pass
        try:
            stream.__exit__(None, None, None)
        except Exception:
            pass

    def _worker(self, stop: threading.Event, worker_error: list[str]) -> None:
        try:
            self._tokens.get()
            auth = self._tokens.auth
            with Stream(auth) as client:
                self._active_stream = client
                streaming = client.streaming

                streaming.on_data = self._on_message
                if hasattr(streaming, "on_index_summary"):
                    streaming.on_index_summary = self._on_message
                if hasattr(streaming, "on_heartbeat"):
                    streaming.on_heartbeat = self._on_heartbeat
                if hasattr(streaming, "on_connection"):
                    streaming.on_connection = self._on_connection

                streaming.connect()
                subs = _subscribe_all(streaming, self.s)
                log.info("Đã kết nối Stream V3 và đăng ký: %s", ", ".join(subs) or "none")

                if hasattr(streaming, "list_subscription"):
                    try:
                        log.debug("Subscriptions hiện tại: %s", streaming.list_subscription())
                    except Exception:
                        pass

                streaming.wait()
        except Exception as exc:
            if not stop.is_set():
                err_detail = str(exc).strip()
                if not err_detail and getattr(self._active_stream, "streaming", None):
                    err_detail = str(getattr(self._active_stream.streaming, "last_error", "") or "")
                worker_error.append((err_detail or exc.__class__.__name__)[:200])
                log.exception("Luồng Stream V3 dừng bất thường")
        finally:
            self._active_stream = None

    def run_forever(self, stop: threading.Event) -> None:
        backoff = 1
        while not stop.is_set():
            self._last_msg = time.monotonic()
            self._lost_at = None
            worker_error: list[str] = []
            t = threading.Thread(target=self._worker, args=(stop, worker_error), daemon=True)
            t.start()
            self.on_event("connect", f"channels={len(self.s.stream_channels)}")

            reason = self._watch(stop, t, worker_error)
            self._disconnect_active()

            if stop.is_set():
                break
            self._lost_at = self._lost_at or time.monotonic()
            self.on_event("disconnect", reason)
            log.warning("Mất kết nối (%s). Thử lại sau %ds", reason, backoff)
            stop.wait(backoff)
            backoff = min(backoff * 2, 60)

    def _watch(self, stop: threading.Event, thread: threading.Thread, worker_error: list[str]) -> str:
        while not stop.wait(1.0):
            if not thread.is_alive():
                return worker_error[-1] if worker_error else "worker_dead"
            now_t = datetime.now(VN_TZ)
            silent = time.monotonic() - self._last_msg
            if (
                in_hours(now_t.time(), MARKET_HOURS)
                and now_t.weekday() < 5
                and silent > self.s.heartbeat_timeout
            ):
                return f"heartbeat_timeout_{int(silent)}s"
        return "stopped"