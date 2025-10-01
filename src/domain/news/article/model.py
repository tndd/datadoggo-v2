"""Articleドメインのデータモデル群"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl


class ArticleFetchStatus(str, Enum):
    """記事取得の保存状況"""

    SAVED = "saved"
    FETCH_FAILED = "fetch_failed"


class Article(BaseModel):
    """メタデータとコンテンツを結合したビュー"""

    id: str
    url: HttpUrl
    description: str | None  # RSS item の <title> が格納される
    pub_date: datetime  # RSS item の <pubDate> が格納される
    content: str  # 記事のHTMLコンテンツ
    created_at: datetime  # バケット保存時のタイムスタンプ
    updated_at: datetime  # バケット保存時のタイムスタンプ


class TestMod:
    """このモジュールのテストコレクション"""

    def test_article_holds_html(self) -> None:
        """
        docs:
            目的: Article がHTML本体を保持できることを確認する。
            検証観点:
                - HTML文字列が格納される。
                - Feed由来の属性が保持される。
                - description が nullable であることを確認する。
        """

        from datetime import datetime, timezone
        from typing import cast

        from pydantic import HttpUrl

        base_time = datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc)
        article = Article(
            id="abc",
            url=cast(HttpUrl, "https://example.com/article"),
            description="テスト記事",
            pub_date=base_time,
            content="<html>content</html>",
            created_at=base_time,
            updated_at=base_time,
        )

        assert article.content == "<html>content</html>"
        assert article.pub_date == base_time
        assert article.description == "テスト記事"

        # description が None でも生成可能
        article_no_desc = Article(
            id="xyz",
            url=cast(HttpUrl, "https://example.com/no-title"),
            description=None,
            pub_date=base_time,
            content="<html>no title</html>",
            created_at=base_time,
            updated_at=base_time,
        )
        assert article_no_desc.description is None
