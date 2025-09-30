"""Article検索とArticle再構築"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlmodel import Session, col, select

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


def search_articles_by_ids(
    session: Session,
    feed_ids: list[str],
    *,
    parallel: bool | int = False,
) -> dict[str, Article]:
    """複数のfeed_idを指定してArticleを取得する。idをkeyにしたdictを返す"""

    if not feed_ids:
        return {}

    # メタデータを一括取得
    statement = select(FeedRecord).where(col(FeedRecord.id).in_(feed_ids))
    feed_records = session.exec(statement).all()

    # status_code=200のもののみをフィルタ
    valid_records = {
        record.id: record for record in feed_records if record.status_code == HTTP_OK
    }

    if not valid_records:
        return {}

    # 並列度の決定
    worker_count = _normalize_parallel(parallel, len(valid_records))

    # バケットからHTMLを並列取得
    if worker_count <= 1:
        # 逐次実行
        results: dict[str, Article] = {}
        for feed_id, record in valid_records.items():
            html_content = load_object(
                bucket_name="article", object_key=feed_id, as_text=True
            )
            if html_content and isinstance(html_content, str):
                results[feed_id] = Article(
                    id=record.id,
                    url=ensure_http_url(record.url),
                    title=record.title,
                    pub_date=record.pub_date,
                    html_content=html_content,
                )
        return results

    # 並列実行
    results_dict: dict[str, Article] = {}

    def load_article(feed_id: str, record: FeedRecord) -> tuple[str, Article | None]:
        html_content = load_object(
            bucket_name="article", object_key=feed_id, as_text=True
        )
        if not html_content or not isinstance(html_content, str):
            return (feed_id, None)

        article = Article(
            id=record.id,
            url=ensure_http_url(record.url),
            title=record.title,
            pub_date=record.pub_date,
            html_content=html_content,
        )
        return (feed_id, article)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(load_article, feed_id, record): feed_id
            for feed_id, record in valid_records.items()
        }

        for future in as_completed(futures):
            feed_id, article = future.result()
            if article is not None:
                results_dict[feed_id] = article

    return results_dict


def _normalize_parallel(parallel: bool | int, item_count: int) -> int:
    """並列実行時のワーカー数を決定する"""

    if not parallel:
        return 1

    if parallel is True:
        return max(1, item_count)

    if isinstance(parallel, int):
        if parallel <= 1:
            return 1
        return min(parallel, item_count)

    return 1


class TestMod:
    """このモジュールのテストコレクション"""

    def test_find_article_by_id_returns_article(self, fs) -> None:
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

        from infra.storage.rds import create_sqlite_engine

        # pytestにより自動的にインメモリDBが使用される（fixtureで初期化済み）
        engine = create_sqlite_engine()

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

    def test_find_article_by_id_returns_none_when_missing(self, fs) -> None:
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

        from infra.storage.rds import create_sqlite_engine

        # pytestにより自動的にインメモリDBが使用される（fixtureで初期化済み）
        engine = create_sqlite_engine()

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

    def test_search_articles_by_ids_returns_dict(self, fs) -> None:
        """
        docs:
            目的:
                複数IDで複数のArticleを取得でき、
                idをkeyとしたdictが返ることを確認する。
            検証観点:
                - 複数のFeedRecordとバケットデータからArticleが復元される。
                - 返り値がdict[str, Article]である。
                - キーはfeed_idと一致する。
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

        from infra.storage.rds import create_sqlite_engine

        engine = create_sqlite_engine()

        with session_scope(engine) as session:
            # 複数のFeedレコードを作成
            feed_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
            feed_records = [
                FeedRecord(
                    id=f"article_{i}",
                    url=f"https://example.com/article/{i}",
                    title=f"記事{i}",
                    pub_date=feed_time,
                    status_code=200,
                    created_at=feed_time,
                    updated_at=feed_time,
                )
                for i in range(3)
            ]
            for record in feed_records:
                session.add(record)
            session.commit()

            # Articleを作成してバケット保存
            for i in range(3):
                article = Article(
                    id=f"article_{i}",
                    url=cast(HttpUrl, f"https://example.com/article/{i}"),
                    title=f"記事{i}",
                    pub_date=feed_time,
                    html_content=f"<html>article{i}</html>",
                )
                save_article_content(article)

            # 取得テスト
            test_ids = ["article_0", "article_1", "article_2"]
            retrieved = search_articles_by_ids(session, test_ids)
            assert len(retrieved) == len(test_ids)
            assert "article_0" in retrieved
            assert "article_1" in retrieved
            assert "article_2" in retrieved
            assert retrieved["article_0"].html_content == "<html>article0</html>"
            assert retrieved["article_1"].html_content == "<html>article1</html>"
            assert retrieved["article_2"].html_content == "<html>article2</html>"

    def test_search_articles_by_ids_skips_failures(self, fs) -> None:
        """
        docs:
            目的:
                一部のIDが取得失敗した場合、
                成功したもののみがdictに含まれることを確認する。
            検証観点:
                - status_code != 200 のレコードはスキップされる。
                - バケットにHTMLがないIDはスキップされる。
                - 未登録のIDはスキップされる。
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

        from infra.storage.rds import create_sqlite_engine

        engine = create_sqlite_engine()

        with session_scope(engine) as session:
            feed_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)

            # 成功するレコード
            success_record = FeedRecord(
                id="success",
                url="https://example.com/success",
                title="成功",
                pub_date=feed_time,
                status_code=200,
                created_at=feed_time,
                updated_at=feed_time,
            )
            session.add(success_record)

            # status_code != 200
            failed_status_record = FeedRecord(
                id="failed_status",
                url="https://example.com/failed",
                title="失敗",
                pub_date=feed_time,
                status_code=404,
                created_at=feed_time,
                updated_at=feed_time,
            )
            session.add(failed_status_record)

            # バケットなし
            no_bucket_record = FeedRecord(
                id="no_bucket",
                url="https://example.com/no_bucket",
                title="バケットなし",
                pub_date=feed_time,
                status_code=200,
                created_at=feed_time,
                updated_at=feed_time,
            )
            session.add(no_bucket_record)

            session.commit()

            # 成功するものだけバケット保存
            article = Article(
                id="success",
                url=cast(HttpUrl, "https://example.com/success"),
                title="成功",
                pub_date=feed_time,
                html_content="<html>success</html>",
            )
            save_article_content(article)

            # 取得テスト（未登録IDも含める）
            retrieved = search_articles_by_ids(
                session,
                ["success", "failed_status", "no_bucket", "missing"],
            )

            # 成功したもののみが含まれる
            assert len(retrieved) == 1
            assert "success" in retrieved
            assert retrieved["success"].html_content == "<html>success</html>"

    def test_search_articles_by_ids_returns_empty_dict_for_empty_list(self, fs) -> None:
        """
        docs:
            目的: 空リストを渡した場合、空のdictが返ることを確認する。
            検証観点:
                - feed_ids=[] で空dictが返る。
        """

        import os
        from pathlib import Path

        from infra.storage.rds import session_scope

        project_root = Path(__file__).resolve().parents[4]
        if not fs.exists(str(project_root)):
            fs.create_dir(str(project_root))
        os.chdir(project_root)

        if not fs.exists("/tmp"):
            fs.create_dir("/tmp")

        from infra.storage.rds import create_sqlite_engine

        engine = create_sqlite_engine()

        with session_scope(engine) as session:
            retrieved = search_articles_by_ids(session, [])
            assert retrieved == {}
