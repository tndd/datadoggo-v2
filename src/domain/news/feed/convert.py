"""Feedドメインと永続化レコードの相互変換ユーティリティ"""

from __future__ import annotations

from .model import FeedItem, FeedRecord
from .service import ensure_http_url


def feed_to_record(feed: FeedItem) -> FeedRecord:
    """ドメインモデルを永続化用レコードに変換する"""

    return FeedRecord(
        id=feed.id,
        url=str(feed.url),
        title=feed.title,
        status_code=feed.status_code,
        pub_date=feed.pub_date,
    )


def record_to_feed(record: FeedRecord) -> FeedItem:
    """永続化レコードをドメインモデルに変換する"""

    return FeedItem(
        id=record.id,
        url=ensure_http_url(record.url),
        title=record.title,
        status_code=record.status_code,
        pub_date=record.pub_date,
    )
