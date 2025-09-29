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


class Article(BaseModel):
    """メタデータとコンテンツを結合したビュー"""

    id: str
    url: HttpUrl
    title: str
    pub_date: datetime
    html_content: str


class Tests:
    class Test_article_model:
        def test_article_holds_html(self) -> None:
            """
            docs:
                目的: Article がHTML本体を保持できることを確認する。
                検証観点:
                    - HTML文字列が格納される。
                    - Feed由来の属性が保持される。
            """

            from datetime import datetime, timezone
            from typing import cast

            from pydantic import HttpUrl

            base_time = datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc)
            article = Article(
                id="abc",
                url=cast(HttpUrl, "https://example.com/article"),
                title="テスト記事",
                pub_date=base_time,
                html_content="<html>content</html>",
            )

            assert article.html_content == "<html>content</html>"
            assert article.pub_date == base_time
