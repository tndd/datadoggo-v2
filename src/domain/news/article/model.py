"""Articleドメインのデータモデル群"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

from src.domain.news.common import ensure_http_url, ensure_saved_at


class ArticleFetchStatus(str, Enum):
    """記事取得の保存状況"""

    SAVED = "saved"
    FETCH_FAILED = "fetch_failed"


class ArticleContent(BaseModel):
    """HTML取得直後の中間モデル"""

    id: str
    url: HttpUrl
    title: str
    pub_date: datetime
    html_content: str


class ArticleBucketMetadata(BaseModel):
    """記事コンテンツのメタデータ"""

    id: str
    url: HttpUrl
    title: str
    status: ArticleFetchStatus
    pub_date: datetime
    saved_at: datetime


class ArticleBucketMetadataRecord(SQLModel, table=True):
    """ArticleBucketMetadataの永続化レコード"""

    __tablename__: ClassVar[Any] = "article_bucket_metadata"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    title: str = SQLField(nullable=False)
    status: str = SQLField(nullable=False)
    pub_date: datetime = SQLField(nullable=False)
    saved_at: datetime = SQLField(nullable=False)


class Article(BaseModel):
    """メタデータとコンテンツを結合したビュー"""

    id: str
    url: HttpUrl
    title: str
    pub_date: datetime
    html_content: str


def metadata_to_record(metadata: ArticleBucketMetadata) -> ArticleBucketMetadataRecord:
    """ArticleBucketMetadataを永続化レコードに変換する"""

    return ArticleBucketMetadataRecord(
        id=metadata.id,
        url=str(metadata.url),
        title=metadata.title,
        status=metadata.status.value,
        pub_date=metadata.pub_date,
        saved_at=metadata.saved_at,
    )


def record_to_metadata(record: ArticleBucketMetadataRecord) -> ArticleBucketMetadata:
    """永続化レコードをArticleBucketMetadataへ変換する"""

    return ArticleBucketMetadata(
        id=record.id,
        url=ensure_http_url(record.url),
        title=record.title,
        status=ArticleFetchStatus(record.status),
        pub_date=record.pub_date,
        saved_at=ensure_saved_at(record.saved_at),
    )


class Tests:
    class Test_article_content_model:
        def test_article_content_holds_html(self) -> None:
            """
            docs:
                目的: ArticleContent がHTML本体を保持できることを確認する。
                検証観点:
                    - HTML文字列が格納される。
                    - Feed由来の属性が保持される。
            """

            from datetime import datetime, timezone
            from typing import cast

            from pydantic import HttpUrl

            base_time = datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc)
            content = ArticleContent(
                id="abc",
                url=cast(HttpUrl, "https://example.com/article"),
                title="テスト記事",
                pub_date=base_time,
                html_content="<html>content</html>",
            )

            assert content.html_content == "<html>content</html>"
            assert content.pub_date == base_time

    class Test_metadata_conversion:
        def test_metadata_round_trip(self) -> None:
            """
            docs:
                目的: ArticleBucketMetadata と永続化レコードの相互変換を確認する。
                検証観点:
                    - status が保存・復元される。
                    - URL が HttpUrl として復元される。
            """

            from datetime import datetime, timezone
            from typing import cast

            from pydantic import HttpUrl

            saved_at = datetime(2025, 9, 29, 10, 0, tzinfo=timezone.utc)
            metadata = ArticleBucketMetadata(
                id="def",
                url=cast(HttpUrl, "https://example.com/detail"),
                title="詳細",
                status=ArticleFetchStatus.SAVED,
                pub_date=saved_at,
                saved_at=saved_at,
            )

            record = metadata_to_record(metadata)
            restored = record_to_metadata(record)

            assert restored.status is ArticleFetchStatus.SAVED
            assert str(restored.url) == "https://example.com/detail"
