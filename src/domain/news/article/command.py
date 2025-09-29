"""Articleコンテンツの保存コマンド"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from infra.storage.bucket import save_object
from infra.storage.rds import initialize_database
from src.domain.news.common import ensure_saved_at

from .model import (
    ArticleBucketMetadata,
    ArticleContent,
    ArticleFetchStatus,
    metadata_to_record,
)

BUCKET_NAME = "article"


def save_article_content(
    session: Session, content: ArticleContent
) -> ArticleBucketMetadata:
    """ArticleContentを保存しメタデータを永続化する"""

    initialize_database()

    saved_key = save_object(
        payload=content.html_content,
        bucket_name=BUCKET_NAME,
        object_key=content.id,
    )
    if not saved_key:
        raise RuntimeError(f"記事HTMLの保存に失敗しました: feed_id={content.id}")

    metadata = ArticleBucketMetadata(
        id=content.id,
        url=content.url,
        title=content.title,
        status=ArticleFetchStatus.SAVED,
        pub_date=content.pub_date,
        saved_at=ensure_saved_at(),
    )

    record = metadata_to_record(metadata)
    merged = session.merge(record)
    session.flush()
    session.refresh(merged)

    return metadata


def mark_fetch_failed(
    session: Session,
    *,
    feed_id: str,
    url: str,
    title: str,
    pub_date: datetime,
) -> ArticleBucketMetadata:
    """取得失敗状態のメタデータを登録する"""

    from src.domain.news.common import ensure_http_url

    initialize_database()

    metadata = ArticleBucketMetadata(
        id=feed_id,
        url=ensure_http_url(url),
        title=title,
        status=ArticleFetchStatus.FETCH_FAILED,
        pub_date=pub_date,
        saved_at=ensure_saved_at(),
    )

    record = metadata_to_record(metadata)
    merged = session.merge(record)
    session.flush()
    session.refresh(merged)

    return metadata


class Tests:
    class Test_save_article_content:
        def test_save_article_content_persists_metadata(self, fs) -> None:
            """
            docs:
                目的: ArticleContent の保存とメタデータ永続化を確認する。
                検証観点:
                    - バケットにHTMLが保存される。
                    - メタデータレコードがDBに永続化される。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path
            from typing import cast

            from pydantic import HttpUrl
            from sqlmodel import select

            from infra.storage.bucket import load_object
            from infra.storage.rds import session_scope

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            db_path = Path("/tmp/article-command.db")
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"
            try:
                content = ArticleContent(
                    id="abc",
                    url=cast(HttpUrl, "https://example.com/article"),
                    title="サンプル",
                    pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                    html_content="<html>body</html>",
                )

                with session_scope() as session:
                    metadata = save_article_content(session, content)

                    assert metadata.status is ArticleFetchStatus.SAVED
                    stored_html = load_object(
                        bucket_name=BUCKET_NAME,
                        object_key=content.id,
                        as_text=True,
                    )
                    assert stored_html == "<html>body</html>"

                    from .model import ArticleBucketMetadataRecord

                    statement = select(ArticleBucketMetadataRecord).where(
                        ArticleBucketMetadataRecord.id == content.id
                    )
                    record = session.exec(statement).first()
                    assert record is not None
                    assert record.status == ArticleFetchStatus.SAVED.value
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

        def test_save_article_content_raises_on_save_failure(
            self, fs, monkeypatch
        ) -> None:
            """
            docs:
                目的: バケット保存失敗時に例外が送出されることを確認する。
                検証観点:
                    - save_object が空文字を返した場合に RuntimeError が発生する。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path
            from typing import cast

            from pydantic import HttpUrl

            from infra.storage.rds import session_scope

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            db_path = Path("/tmp/article-command-failure.db")
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"
            try:
                content = ArticleContent(
                    id="xyz",
                    url=cast(HttpUrl, "https://example.com/failure"),
                    title="失敗",
                    pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                    html_content="<html>failure</html>",
                )

                import sys

                def fake_save_object(**kwargs):  # type: ignore[no-untyped-def]
                    return ""

                module = sys.modules[__name__]
                monkeypatch.setattr(module, "save_object", fake_save_object)

                with session_scope() as session:
                    try:
                        save_article_content(session, content)
                        raise AssertionError("例外が発生しませんでした")
                    except RuntimeError:
                        pass
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)
