"""Feedテーブルの永続化関連ユーティリティ"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import HttpUrl, TypeAdapter
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

from infra.storage.rds import initialize_database

from .model import FeedItem

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


class _FeedRecord(SQLModel, table=True):
    """SQLModelによるFeedテーブル定義"""

    __tablename__: ClassVar[Any] = "feeds"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    title: str = SQLField(nullable=False)
    status_code: int = SQLField(nullable=False)
    pub_date: datetime = SQLField(nullable=False)


def ensure_feed_table_initialized() -> None:
    """テーブル初期化を一度だけ行うためのヘルパー"""

    initialize_database()


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列/HttpUrl入力をHttpUrlとして検証する"""

    return HTTP_URL_ADAPTER.validate_python(value)


def feed_to_record(feed: FeedItem) -> _FeedRecord:
    """ドメインモデルを永続化用レコードに変換する"""

    return _FeedRecord(
        id=feed.id,
        url=str(feed.url),
        title=feed.title,
        status_code=feed.status_code,
        pub_date=feed.pub_date,
    )


def record_to_feed(record: _FeedRecord) -> FeedItem:
    """永続化レコードをドメインモデルに変換する"""

    return FeedItem(
        id=record.id,
        url=ensure_http_url(record.url),
        title=record.title,
        status_code=record.status_code,
        pub_date=record.pub_date,
    )
