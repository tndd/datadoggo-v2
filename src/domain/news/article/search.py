"""Article検索とArticle再構築"""

from __future__ import annotations

from sqlmodel import Session, select

from infra.storage.bucket import load_object
from src.domain.news.common import ensure_http_url
from src.domain.news.feed.model import FeedRecord

from .model import Article

# HTTPステータスコード
HTTP_OK = 200


def find_article_by_id(session: Session, feed_id: str) -> Article | None:
    """保存済みArticleを取得する。Feedテーブルからメタデータを取得し、バケットからHTMLを取得"""

    # Feedテーブルからメタデータを取得
    statement = select(FeedRecord).where(FeedRecord.id == feed_id)
    feed_record = session.exec(statement).first()
    if feed_record is None:
        return None

    # status_codeが200以外の場合、取得失敗と判定
    if feed_record.status_code != HTTP_OK:
        return None

    # バケットからHTMLコンテンツを取得
    html_content = load_object(
        bucket_name="article",
        object_key=feed_id,
        as_text=True,
    )
    if not html_content or not isinstance(html_content, str):
        return None

    return Article(
        id=feed_record.id,
        url=ensure_http_url(feed_record.url),
        title=feed_record.title,
        pub_date=feed_record.pub_date,
        html_content=html_content,
    )


class Tests:
    class Test_find_article_by_id:
        def test_find_article_by_id_returns_article(self, fs, test_db_env) -> None:
            """
            docs:
                目的: 保存済み記事を完全なArticleモデルとして取得できることを確認する。
                検証観点:
                    - Feedテーブル とバケット HTML から Article が復元される。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path
            from typing import cast

            from pydantic import HttpUrl

            from infra.storage.rds import session_scope
            from src.domain.news.feed.model import FeedRecord

            from .command import save_article_content

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            # test_db_envフィクスチャが環境変数を設定済み
            from infra.storage.rds import create_sqlite_engine

            # インメモリDBのエンジンを作成
            engine = create_sqlite_engine("sqlite:///:memory:")

            # FeedRecordのテーブルを明示的に作成
            FeedRecord.metadata.create_all(engine)

            with session_scope(engine) as session:
                # Feedレコードを作成
                feed_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
                feed_record = FeedRecord(
                    id="article_test",
                    url="https://example.com/article",
                    title="記事",
                    pub_date=feed_time,
                    status_code=200,
                    created_at=feed_time,
                    updated_at=feed_time,
                )
                session.add(feed_record)
                session.commit()

                # Article作成してバケット保存
                article = Article(
                    id="article_test",
                    url=cast(HttpUrl, "https://example.com/article"),
                    title="記事",
                    pub_date=feed_time,
                    html_content="<html>article</html>",
                )
                save_article_content(article)

                # 取得テスト
                retrieved = find_article_by_id(session, "article_test")
                assert retrieved is not None
                assert retrieved.html_content == "<html>article</html>"

        def test_find_article_by_id_returns_none_when_missing(
            self, fs, test_db_env
        ) -> None:
            """
            docs:
                目的: 未保存IDでは None が返ることを確認する。
                検証観点:
                    - メタデータ未登録時は None。
                    - status_code が 200以外の場合も None。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path

            from infra.storage.rds import session_scope
            from src.domain.news.feed.model import FeedRecord

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            if not fs.exists("/tmp"):
                fs.create_dir("/tmp")
            # test_db_envフィクスチャが環境変数を設定済み
            from infra.storage.rds import create_sqlite_engine

            # インメモリDBのエンジンを作成
            engine = create_sqlite_engine("sqlite:///:memory:")

            # FeedRecordのテーブルを明示的に作成
            FeedRecord.metadata.create_all(engine)

            with session_scope(engine) as session:
                # 未登録IDのテスト
                assert find_article_by_id(session, "missing") is None

                # status_code != 200のテスト
                feed_time = datetime(2025, 9, 29, 10, 0, tzinfo=timezone.utc)
                failed_feed = FeedRecord(
                    id="failed_test",
                    url="https://example.com/fail",
                    title="失敗",
                    pub_date=feed_time,
                    status_code=404,
                    created_at=feed_time,
                    updated_at=feed_time,
                )
                session.add(failed_feed)
                session.commit()

                assert find_article_by_id(session, "failed_test") is None
