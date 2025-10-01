"""domain.news.article.model のテスト"""

from datetime import datetime, timezone
from typing import cast

from pydantic import HttpUrl

from domain.news.article.model import Article


def test_article_holds_html() -> None:
    """
    docs:
        目的: Article がHTML本体を保持できることを確認する。
        検証観点:
            - HTML文字列が格納される。
            - HttpRequestTask由来の属性が保持される。
            - description と group が nullable であることを確認する。
    """

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
