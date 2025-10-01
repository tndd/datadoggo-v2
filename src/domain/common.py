"""Newsドメイン共通ユーティリティ"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import HttpUrl, TypeAdapter

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列やHttpUrlを受け取りHttpUrlとして正規化する"""

    return _HTTP_URL_ADAPTER.validate_python(value)


def ensure_saved_at(value: datetime | None = None) -> datetime:
    """保存日時をUTCのtimezone-aware datetimeに整形する"""

    target = value or datetime.now(timezone.utc)
    if target.tzinfo is None:
        return target.replace(tzinfo=timezone.utc)
    return target.astimezone(timezone.utc)


