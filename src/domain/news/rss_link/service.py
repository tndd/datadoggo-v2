"""RSSバケット向けの共通サービスユーティリティ"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import HttpUrl, TypeAdapter

from .model import RssBucketItem, RssBucketStatus, RssItem

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列/HttpUrl入力をHttpUrlとして検証する"""

    return _HTTP_URL_ADAPTER.validate_python(value)


def ensure_rss_bucket_status(value: RssBucketStatus | str) -> RssBucketStatus:
    """ステータス入力を RssBucketStatus へ正規化する"""

    if isinstance(value, RssBucketStatus):
        return value
    return RssBucketStatus(value)


def ensure_saved_at(value: datetime | None = None) -> datetime:
    """保存日時をUTCのtimezone-aware datetimeへ整形する"""

    target = value or datetime.now(timezone.utc)
    if target.tzinfo is None:
        return target.replace(tzinfo=timezone.utc)
    return target.astimezone(timezone.utc)


def create_rss_bucket_item(
    *,
    bucket_key: str,
    rss_item: RssItem,
    status: RssBucketStatus | str = RssBucketStatus.registered,
    saved_at: datetime | None = None,
    content_length: int | None = None,
) -> RssBucketItem:
    """RSSバケットエントリのドメインモデルを組み立てる"""

    normalized_url = ensure_http_url(rss_item.url)
    normalized_status = ensure_rss_bucket_status(status)
    normalized_saved_at = ensure_saved_at(saved_at)

    return RssBucketItem(
        id=bucket_key,
        group=rss_item.group,
        name=rss_item.name,
        url=normalized_url,
        status=normalized_status,
        saved_at=normalized_saved_at,
        content_length=content_length,
    )


class Tests:
    class Test_create_rss_bucket_item:
        def test_create_rss_bucket_item_sets_defaults(self) -> None:
            """
            docs:
                目的:
                    create_rss_bucket_item がデフォルト設定を適用することを確認する。
                検証観点:
                    - status が registered になる。
                    - saved_at が timezone-aware になる。
            """

            from .model import RssItem

            item = create_rss_bucket_item(
                bucket_key="abc",
                rss_item=RssItem(
                    group="bbc",
                    name="top",
                    url="https://example.com/rss",
                ),
            )

            assert item.status is RssBucketStatus.registered
            assert item.saved_at.tzinfo is not None

        def test_create_rss_bucket_item_accepts_str_status(self) -> None:
            """
            docs:
                目的:
                    文字列ステータスを正規化できることを確認する。
                検証観点:
                    - "error" 指定で RssBucketStatus.error に変換される。
                    - naive datetime が UTC 付きに補正される。
            """

            naive_time = datetime(2025, 9, 27, 12, 0, 0)

            from .model import RssItem

            item = create_rss_bucket_item(
                bucket_key="def",
                rss_item=RssItem(
                    group="guardian",
                    name="world",
                    url="https://example.com/world",
                ),
                status="error",
                saved_at=naive_time,
            )

            assert item.status is RssBucketStatus.error
            assert item.saved_at.tzinfo is not None
            offset = item.saved_at.utcoffset()
            assert offset is not None
            assert offset.total_seconds() == 0
