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


class Tests:
    """このモジュールのテストコレクション"""

    def test_ensure_http_url_accepts_str(self) -> None:
        """
        docs:
            目的: 文字列URLがHttpUrlとして正規化されることを確認する。
            検証観点:
                - httpsスキームのURLがそのまま返る。
        """

        result = ensure_http_url("https://example.com/path")
        assert str(result) == "https://example.com/path"

    def test_ensure_saved_at_normalizes_naive_datetime(self) -> None:
        """
        docs:
            目的: naive datetime が UTC 付きに補正されることを確認する。
            検証観点:
                - tzinfo が None の場合に UTC タイムゾーンが付与される。
        """

        naive = datetime(2025, 9, 27, 12, 0, 0)

        normalized = ensure_saved_at(naive)

        assert normalized.tzinfo is not None
        offset = normalized.utcoffset()
        assert offset is not None and offset.total_seconds() == 0
