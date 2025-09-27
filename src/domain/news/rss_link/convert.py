"""RSSバケットのドメイン <-> 永続化変換ユーティリティ"""

from __future__ import annotations

from .model import RssBucketItem, RssBucketRecord, RssBucketStatus
from .service import ensure_http_url, ensure_saved_at


def rss_bucket_to_record(item: RssBucketItem) -> RssBucketRecord:
    """ドメインモデルを永続化レコードに変換する"""

    return RssBucketRecord(
        id=item.id,
        group=item.group,
        name=item.name,
        url=str(item.url),
        status=item.status.value,
        saved_at=item.saved_at,
        content_length=item.content_length,
    )


def record_to_rss_bucket(record: RssBucketRecord) -> RssBucketItem:
    """永続化レコードをドメインモデルに変換する"""

    return RssBucketItem(
        id=record.id,
        group=record.group,
        name=record.name,
        url=ensure_http_url(record.url),
        status=RssBucketStatus(record.status),
        saved_at=ensure_saved_at(record.saved_at),
        content_length=record.content_length,
    )


class Tests:
    class Test_rss_bucket_to_record:
        def test_rss_bucket_to_record_preserves_fields(self) -> None:
            """
            docs:
                目的:
                    ドメインモデルが永続化レコードへ正しく変換されることを確認する。
                検証観点:
                    - status が文字列化される。
                    - saved_at や content_length が保持される。
            """

            from datetime import datetime, timezone

            content_length = 1234

            from typing import cast

            from pydantic import HttpUrl

            url_value = cast(HttpUrl, "https://example.com/rss")

            item = RssBucketItem(
                id="abc",
                group="bbc",
                name="top",
                url=url_value,
                status=RssBucketStatus.registered,
                saved_at=datetime(2025, 9, 27, 3, 0, tzinfo=timezone.utc),
                content_length=content_length,
            )

            record = rss_bucket_to_record(item)

            assert record.status == "registered"
            assert record.saved_at == item.saved_at
            assert record.content_length == content_length

    class Test_record_to_rss_bucket:
        def test_record_to_rss_bucket_restores_domain(self) -> None:
            """
            docs:
                目的:
                    永続化レコードからドメインモデルへ復元できることを確認する。
                検証観点:
                    - URL が HttpUrl として検証される。
                    - StrEnum のステータスに戻る。
            """

            from datetime import datetime, timezone

            record = RssBucketRecord(
                id="abc",
                group="bbc",
                name="top",
                url="https://example.com/rss",
                status="error",
                saved_at=datetime(2025, 9, 27, 3, 0, tzinfo=timezone.utc),
                content_length=None,
            )

            item = record_to_rss_bucket(record)

            assert item.status is RssBucketStatus.error
            assert str(item.url) == "https://example.com/rss"
