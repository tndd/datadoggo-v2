"""domain.news.article.search のテスト"""

from datetime import datetime, timezone
from typing import cast

from pydantic import HttpUrl
from pyfakefs.fake_filesystem import FakeFilesystem

from domain.news.article.command import save_article_content
from domain.news.article.model import Article
from domain.news.article.search import find_article_by_id, search_articles_by_ids
from infra.storage.rds import session_scope
from domain.task_queue.http_request.model import HttpRequestTaskRecord


def test_find_article_by_id_returns_article(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 保存済み記事を完全なArticleモデルとして取得できることを確認する。
        検証観点:
            - HttpRequestTaskRecord とバケット HTML から Article が復元される。
    """

    # pytestにより自動的にインメモリDBが使用される(fixtureで初期化済み)
    with session_scope() as session:
        # HttpRequestTaskレコードを作成
        request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
        http_request_record = HttpRequestTaskRecord(
            id="article_test",
            url="https://example.com/article",
            description="記事",
            group="test:article",
            status_code=200,
            created_at=request_time,
            updated_at=request_time,
        )
        session.add(http_request_record)
        session.commit()

        # Article作成してバケット保存
        article = Article(
            id="article_test",
            url=cast(HttpUrl, "https://example.com/article"),
            content="<html>article</html>",
            group="test:article",
            created_at=request_time,
            updated_at=request_time,
            description="記事",
        )
        save_article_content(article)

        # 取得テスト
        retrieved = find_article_by_id(session, "article_test")
        assert retrieved is not None
        assert retrieved.content == "<html>article</html>"


def test_find_article_by_id_returns_none_when_missing(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 未保存IDでは None が返ることを確認する。
        検証観点:
            - メタデータ未登録時は None。
            - status_code が 200以外の場合も None。
    """

    # pytestにより自動的にインメモリDBが使用される(fixtureで初期化済み)
    with session_scope() as session:
        # 未登録IDのテスト
        assert find_article_by_id(session, "missing") is None

        # status_code != 200のテスト
        request_time = datetime(2025, 9, 29, 10, 0, tzinfo=timezone.utc)
        failed_request = HttpRequestTaskRecord(
            id="failed_test",
            url="https://example.com/fail",
            description="失敗",
            group="test:failed",
            status_code=404,
            created_at=request_time,
            updated_at=request_time,
        )
        session.add(failed_request)
        session.commit()

        assert find_article_by_id(session, "failed_test") is None


def test_search_articles_by_ids_returns_dict(fs: FakeFilesystem) -> None:
    """
    docs:
        目的:
            複数IDで複数のArticleを取得でき、
            idをkeyとしたdictが返ることを確認する。
        検証観点:
            - 複数のHttpRequestTaskRecordとバケットデータからArticleが復元される。
            - 返り値がdict[str, Article]である。
            - キーはhttp_request_idと一致する。
    """

    with session_scope() as session:
        # 複数のHttpRequestTaskレコードを作成
        request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
        http_request_records = [
            HttpRequestTaskRecord(
                id=f"article_{i}",
                url=f"https://example.com/article/{i}",
                description=f"記事{i}",
                group=f"test:article{i}",
                status_code=200,
                created_at=request_time,
                updated_at=request_time,
            )
            for i in range(3)
        ]
        for record in http_request_records:
            session.add(record)
        session.commit()

        # Articleを作成してバケット保存
        for i in range(3):
            article = Article(
                id=f"article_{i}",
                url=cast(HttpUrl, f"https://example.com/article/{i}"),
                content=f"<html>article{i}</html>",
                group=f"test:article{i}",
                created_at=request_time,
                updated_at=request_time,
                description=f"記事{i}",
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
        assert retrieved["article_0"].content == "<html>article0</html>"
        assert retrieved["article_1"].content == "<html>article1</html>"
        assert retrieved["article_2"].content == "<html>article2</html>"


def test_search_articles_by_ids_skips_failures(fs: FakeFilesystem) -> None:
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

    with session_scope() as session:
        request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)

        # 成功するレコード
        success_record = HttpRequestTaskRecord(
            id="success",
            url="https://example.com/success",
            description="成功",
            group="test:success",
            status_code=200,
            created_at=request_time,
            updated_at=request_time,
        )
        session.add(success_record)

        # status_code != 200
        failed_status_record = HttpRequestTaskRecord(
            id="failed_status",
            url="https://example.com/failed",
            description="失敗",
            group="test:failed",
            status_code=404,
            created_at=request_time,
            updated_at=request_time,
        )
        session.add(failed_status_record)

        # バケットなし
        no_bucket_record = HttpRequestTaskRecord(
            id="no_bucket",
            url="https://example.com/no_bucket",
            description="バケットなし",
            group="test:no_bucket",
            status_code=200,
            created_at=request_time,
            updated_at=request_time,
        )
        session.add(no_bucket_record)

        session.commit()

        # 成功するものだけバケット保存
        article = Article(
            id="success",
            url=cast(HttpUrl, "https://example.com/success"),
            content="<html>success</html>",
            group="test:success",
            created_at=request_time,
            updated_at=request_time,
            description="成功",
        )
        save_article_content(article)

        # 取得テスト(未登録IDも含める)
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
        assert retrieved["success"].content == "<html>success</html>"
        assert retrieved["failed_status"] is None
        assert retrieved["no_bucket"] is None
        assert retrieved["missing"] is None


def test_search_articles_by_ids_returns_empty_dict_for_empty_list(
    fs: FakeFilesystem,
) -> None:
    """
    docs:
        目的: 空リストを渡した場合、空のdictが返ることを確認する。
        検証観点:
            - http_request_ids=[] で空dictが返る。
    """

    with session_scope() as session:
        retrieved = search_articles_by_ids(session, [])
        assert retrieved == {}
