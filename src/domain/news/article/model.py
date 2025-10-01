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
    content: str  # 記事のHTMLコンテンツ
    group: str | None  # グループ名
    created_at: datetime  # レコードの生成日時(UTC)
    updated_at: datetime  # レコードの最終更新日時(UTC)
    description: str | None  # 説明。記事のタイトルや注釈など


class TestMod:
    """このモジュールのテストコレクション"""

    def test_article_holds_html(self) -> None:
        """
        docs:
            目的: Article がHTML本体を保持できることを確認する。
            検証観点:
                - HTML文字列が格納される。
                - HttpRequest由来の属性が保持される。
                - description と group が nullable であることを確認する。
        """

        from datetime import datetime, timezone
        from typing import cast

        from pydantic import HttpUrl

        base_time = datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc)
        article = Article(
            id="abc",
            url=cast(HttpUrl, "https://example.com/article"),
            content="<html>content</html>",
            group="tech",
            created_at=base_time,
            updated_at=base_time,
            description="テスト記事",
        )

        assert article.content == "<html>content</html>"
        assert article.created_at == base_time
        assert article.description == "テスト記事"
        assert article.group == "tech"

        # description と group が None でも生成可能
        article_no_desc = Article(
            id="xyz",
            url=cast(HttpUrl, "https://example.com/no-title"),
            content="<html>no title</html>",
            group=None,
            created_at=base_time,
            updated_at=base_time,
            description=None,
        )
        assert article_no_desc.description is None
        assert article_no_desc.group is None
