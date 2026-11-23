"""Xác thực và quản lý phiên FastConnect V3 thông qua ssi_sdk."""
from __future__ import annotations

import logging
import threading

from ssi_sdk import Auth, Config, SSIError

log = logging.getLogger(__name__)


class SSIAuthError(RuntimeError):
    pass


def build_sdk_config(
    *,
    client_id: str,
    api_key: str = "",
    api_secret: str = "",
    private_key: str = "",
    api_url: str = "https://api.ssi.com.vn",
    streaming_url: str = "wss://stream.ssi.com.vn/ws/v3",
    timeout_ms: int = 60000,
    max_retries: int = 5,
    rate_limit_per_second: int = 10,
) -> Config:
    if not client_id:
        raise SSIAuthError("Thiếu SSI_CLIENT_ID trong .env / biến môi trường")
    if not api_key or not api_secret:
        raise SSIAuthError("Thiếu SSI_API_KEY hoặc SSI_API_SECRET trong .env / biến môi trường")

    return Config(
        client_id=client_id,
        api_key=api_key,
        api_secret=api_secret,
        private_key=private_key,
        api_url=api_url,
        streaming_url=streaming_url,
        timeout_ms=timeout_ms,
        max_retries=max_retries,
        rate_limit_per_second=rate_limit_per_second,
    )


class TokenManager:
    """Bao bọc Auth của ssi_sdk để các module nội bộ lấy token/client đồng bộ."""

    def __init__(
        self,
        client_id: str = "",
        api_key: str = "",
        api_secret: str = "",
        private_key: str = "",
        api_url: str = "https://api.ssi.com.vn",
        streaming_url: str = "wss://stream.ssi.com.vn/ws/v3",
        timeout_ms: int = 60000,
        max_retries: int = 5,
        rate_limit_per_second: int = 10,
    ):
        self._config = build_sdk_config(
            client_id=client_id,
            api_key=api_key,
            api_secret=api_secret,
            private_key=private_key,
            api_url=api_url,
            streaming_url=streaming_url,
            timeout_ms=timeout_ms,
            max_retries=max_retries,
            rate_limit_per_second=rate_limit_per_second,
        )
        self._auth = Auth(self._config)
        self._lock = threading.Lock()

    @property
    def auth(self) -> Auth:
        return self._auth

    def authenticate(self, otp: str | None = None, transaction_id: str | None = None) -> Auth:
        with self._lock:
            try:
                if otp is not None or transaction_id is not None:
                    self._auth.authenticate(otp=otp, transaction_id=transaction_id)
                else:
                    self._auth.authenticate()
                log.info("Xác thực SSI FastConnect V3 thành công")
                return self._auth
            except SSIError as exc:
                raise SSIAuthError(f"Xác thực SSI thất bại: {exc}") from None

    def get(self, force: bool = False) -> str:
        with self._lock:
            try:
                expired_attr = getattr(self._auth, "is_token_expired", False)
                is_expired = expired_attr() if callable(expired_attr) else bool(expired_attr)
                if force or not self._auth.access_token or is_expired:
                    self._auth.authenticate()
                token = self._auth.access_token
                if not token:
                    raise SSIAuthError("Không nhận được access_token từ Auth")
                return token
            except SSIError as exc:
                raise SSIAuthError(f"Không lấy được access token V3: {exc}") from None

    def close(self) -> None:
        with self._lock:
            try:
                self._auth.close()
            except Exception:
                pass