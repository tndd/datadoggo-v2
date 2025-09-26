"""Feed向け共通サービスユーティリティ"""

from __future__ import annotations

from datetime import datetime

from pydantic import HttpUrl, TypeAdapter

from infra.compute import hash_text_sha256

from .model import FeedItem

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列/HttpUrl入力をHttpUrlとして検証する"""

    return HTTP_URL_ADAPTER.validate_python(value)


def create_feed(url: str, title: str, status_code: int, pub_date: datetime) -> FeedItem:
    """入力値からFeedドメインモデルを生成する"""

    feed_id = hash_text_sha256(url)
    return FeedItem(
        id=feed_id,
        url=ensure_http_url(url),
        title=title,
        status_code=status_code,
        pub_date=pub_date,
    )
