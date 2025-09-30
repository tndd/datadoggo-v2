"""Article検索とArticle再構築"""

from __future__ import annotations

from sqlmodel import Session, col, select

from infra.storage.bucket import load_object, load_objects
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
) -> dict[str, Article | None]:
    """複数のfeed_idを指定してArticleを取得する。idをkeyにしたdictを返す。取得失敗時はNoneを設定"""

    if not feed_ids:
        return {}

    # メタデータを一括取得
    statement = select(FeedRecord).where(col(FeedRecord.id).in_(feed_ids))
    feed_records = session.exec(statement).all()

    # status_code=200のもののみをフィルタ
    valid_records = {
        record.id: record for record in feed_records if record.status_code == HTTP_OK
    }

    # バケットからHTMLを並列取得
    html_contents = load_objects(
        bucket_name="article",
        object_keys=feed_ids,
        parallel=parallel,
        as_text=True,
    )

    # Articleを構築
    results: dict[str, Article | None] = {}
    for feed_id in feed_ids:
        # valid_recordsに含まれない場合はNone
        if feed_id not in valid_records:
            results[feed_id] = None
            continue

        # HTMLが取得できなかった場合はNone
        html_content = html_contents.get(feed_id, "")
        if not html_content or not isinstance(html_content, str):
            results[feed_id] = None
            continue

        # Article構築
        record = valid_records[feed_id]
        results[feed_id] = Article(
            id=record.id,
            url=ensure_http_url(record.url),
            title=record.title,
            pub_date=record.pub_date,
            html_content=html_content,
        )

    return results


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
            assert retrieved["article_0"] is not None
            assert retrieved["article_1"] is not None
            assert retrieved["article_2"] is not None
            assert retrieved["article_0"].html_content == "<html>article0</html>"
            assert retrieved["article_1"].html_content == "<html>article1</html>"
            assert retrieved["article_2"].html_content == "<html>article2</html>"

    def test_search_articles_by_ids_skips_failures(self, fs) -> None:
        """
        docs:
            目的:
                一部のIDが取得失敗した場合、
                そのkeyにNoneが設定されることを確認する。
            検証観点:
                - status_code != 200 のレコードはNone。
                - バケットにHTMLがないIDはNone。
                - 未登録のIDはNone。
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
            test_ids = ["success", "failed_status", "no_bucket", "missing"]
            retrieved = search_articles_by_ids(session, test_ids)

            # すべてのkeyが含まれる
            assert len(retrieved) == len(test_ids)
            assert "success" in retrieved
            assert "failed_status" in retrieved
            assert "no_bucket" in retrieved
            assert "missing" in retrieved

            # 成功したもののみがArticle、失敗はNone
            assert retrieved["success"] is not None
            assert retrieved["success"].html_content == "<html>success</html>"
            assert retrieved["failed_status"] is None
            assert retrieved["no_bucket"] is None
            assert retrieved["missing"] is None

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
