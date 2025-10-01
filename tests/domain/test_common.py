"""domain.common のテスト"""

from datetime import datetime, timezone

from domain.common import ensure_http_url, ensure_saved_at


def test_ensure_http_url_accepts_str() -> None:
    """
    docs:
        目的: 文字列URLがHttpUrlとして正規化されることを確認する。
        検証観点:
            - httpsスキームのURLがそのまま返る。
    """

    result = ensure_http_url("https://example.com/path")
    assert str(result) == "https://example.com/path"


def test_ensure_saved_at_normalizes_naive_datetime() -> None:
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
