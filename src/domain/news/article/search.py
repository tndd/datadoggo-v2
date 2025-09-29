"""Articleメタデータ検索とArticle再構築"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from infra.storage.bucket import load_object
from infra.storage.rds import initialize_database

from .model import (
    Article,
    ArticleBucketMetadata,
    ArticleBucketMetadataRecord,
    ArticleFetchStatus,
    record_to_metadata,
)


class ArticleSearchQuery(BaseModel):
    """ArticleBucketMetadata検索用の入力モデル"""

    statuses: list[ArticleFetchStatus] | None = Field(default=None)


def search_article_metadata(
    session: Session, query: ArticleSearchQuery | None = None
) -> list[ArticleBucketMetadata]:
    """Articleメタデータを検索してドメインモデル一覧で返す"""

    initialize_database()

    effective_query = query or ArticleSearchQuery()

    statement = select(ArticleBucketMetadataRecord)
    if effective_query.statuses:
        status_column = cast(Any, ArticleBucketMetadataRecord.status)
        statement = statement.where(
            status_column.in_([status.value for status in effective_query.statuses])
        )

    records = session.exec(statement).all()
    return [record_to_metadata(record) for record in records]


def find_article_by_id(session: Session, feed_id: str) -> Article | None:
    """保存済みArticleを完全なビューモデルとして取得する"""

    initialize_database()

    statement = select(ArticleBucketMetadataRecord).where(
        ArticleBucketMetadataRecord.id == feed_id
    )
    record = session.exec(statement).first()
    if record is None:
        return None

    metadata = record_to_metadata(record)
    if metadata.status is not ArticleFetchStatus.SAVED:
        return None

    html_content = load_object(
        bucket_name="article",
        object_key=metadata.id,
        as_text=True,
    )
    if not html_content:
        return None

    if not isinstance(html_content, str):
        return None

    return Article(
        id=metadata.id,
        url=metadata.url,
        title=metadata.title,
        pub_date=metadata.pub_date,
        html_content=html_content,
    )


class Tests:
    class Test_search_article_metadata:
        def test_search_article_metadata_filters_by_status(self, fs) -> None:
            """
            docs:
                目的: ステータス指定でメタデータ一覧を絞り込めることを確認する。
                検証観点:
                    - FETCH_FAILED のみ抽出できる。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path

            from infra.storage.rds import session_scope

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            db_path = Path("/tmp/article-search-metadata.db")
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"
            try:
                from pydantic import HttpUrl

                from .command import mark_fetch_failed, save_article_content
                from .model import ArticleContent

                with session_scope() as session:
                    failed = mark_fetch_failed(
                        session,
                        feed_id="fail",
                        url="https://example.com/fail",
                        title="失敗",
                        pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                    )

                    content = ArticleContent(
                        id="ok",
                        url=cast(HttpUrl, "https://example.com/ok"),
                        title="成功",
                        pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                        html_content="<html>ok</html>",
                    )
                    save_article_content(session, content)

                    failed_only = search_article_metadata(
                        session,
                        ArticleSearchQuery(statuses=[ArticleFetchStatus.FETCH_FAILED]),
                    )
                    assert [item.id for item in failed_only] == [failed.id]
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

    class Test_find_article_by_id:
        def test_find_article_by_id_returns_article(self, fs) -> None:
            """
            docs:
                目的: 保存済み記事を完全なArticleモデルとして取得できることを確認する。
                検証観点:
                    - ArticleBucketMetadata とバケット HTML から Article が復元される。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path

            from pydantic import HttpUrl

            from infra.storage.rds import session_scope

            from .command import save_article_content
            from .model import ArticleContent

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            db_path = Path("/tmp/article-search-find.db")
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"
            try:
                with session_scope() as session:
                    content = ArticleContent(
                        id="article",
                        url=cast(HttpUrl, "https://example.com/article"),
                        title="記事",
                        pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                        html_content="<html>article</html>",
                    )
                    save_article_content(session, content)

                    article = find_article_by_id(session, "article")
                    assert article is not None
                    assert article.html_content == "<html>article</html>"
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

        def test_find_article_by_id_returns_none_when_missing(self, fs) -> None:
            """
            docs:
                目的: 未保存IDでは None が返ることを確認する。
                検証観点:
                    - メタデータ未登録時は None。
                    - status が FETCH_FAILED の場合も None。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path

            from infra.storage.rds import session_scope

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            db_path = Path("/tmp/article-search-missing.db")
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"
            try:
                with session_scope() as session:
                    assert find_article_by_id(session, "missing") is None

                    from .command import mark_fetch_failed

                    mark_fetch_failed(
                        session,
                        feed_id="failed",
                        url="https://example.com/fail",
                        title="失敗",
                        pub_date=datetime(2025, 9, 29, 10, 0, tzinfo=timezone.utc),
                    )

                    assert find_article_by_id(session, "failed") is None
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)
