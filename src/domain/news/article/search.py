"""Article検索とArticle再構築"""

from __future__ import annotations

from sqlmodel import Session, col, select

from domain.common import ensure_http_url
from infra.storage.bucket import load_object, load_objects
from src.domain.task_queue.http_request.model import HttpRequestRecord

from .model import Article

# HTTPステータスコード
HTTP_OK = 200


def find_article_by_id(session: Session, http_request_id: str) -> Article | None:
    """保存済みArticleを取得する。HttpRequestテーブルからメタデータを取得し、バケットからHTMLを取得"""

    # HttpRequestテーブルからメタデータを取得
    statement = select(HttpRequestRecord).where(HttpRequestRecord.id == http_request_id)
    http_request_record = session.exec(statement).first()
    if http_request_record is None:
        return None

    # status_codeが200以外の場合、取得失敗と判定
    if http_request_record.status_code != HTTP_OK:
        return None

    # バケットからHTMLコンテンツを取得
    html_content = load_object(bucket_name="article", object_key=http_request_id)
    if html_content is None:
        return None

    return Article(
        id=http_request_record.id,
        url=ensure_http_url(http_request_record.url),
        content=html_content,
        group=http_request_record.group,
        created_at=http_request_record.created_at,
        updated_at=http_request_record.updated_at,
        description=http_request_record.description,
    )


def search_articles_by_ids(
    session: Session,
    http_request_ids: list[str],
    *,
    parallel: bool | int = False,
) -> dict[str, Article | None]:
    """複数のhttp_request_idを指定してArticleを取得する。idをkeyにしたdictを返す。取得失敗時はNoneを設定"""

    if not http_request_ids:
        return {}

    # メタデータを一括取得
    statement = select(HttpRequestRecord).where(
        col(HttpRequestRecord.id).in_(http_request_ids)
    )
    http_request_records = session.exec(statement).all()

    # status_code=200のもののみをフィルタ
    valid_records = {
        record.id: record
        for record in http_request_records
        if record.status_code == HTTP_OK
    }

    # バケットからHTMLを並列取得
    html_contents = load_objects(
        bucket_name="article", object_keys=http_request_ids, parallel=parallel
    )

    # Articleを構築
    results: dict[str, Article | None] = {}
    for http_request_id in http_request_ids:
        # valid_recordsに含まれない場合はNone
        if http_request_id not in valid_records:
            results[http_request_id] = None
            continue

        # HTMLが取得できなかった場合はNone
        html_content = html_contents.get(http_request_id)
        if html_content is None:
            results[http_request_id] = None
            continue

        # Article構築
        record = valid_records[http_request_id]
        results[http_request_id] = Article(
            id=record.id,
            url=ensure_http_url(record.url),
            content=html_content,
            group=record.group,
            created_at=record.created_at,
            updated_at=record.updated_at,
            description=record.description,
        )

    return results


class TestMod:
    """このモジュールのテストコレクション"""

    def test_find_article_by_id_returns_article(self, fs) -> None:
        """
        docs:
            目的: 保存済み記事を完全なArticleモデルとして取得できることを確認する。
            検証観点:
                - HttpRequestテーブル とバケット HTML から Article が復元される。
        """

        import os
        from datetime import datetime, timezone
        from pathlib import Path
        from typing import cast

        from pydantic import HttpUrl

        from infra.storage.rds import session_scope
        from src.domain.task_queue.http_request.model import HttpRequestRecord

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
            # HttpRequestレコードを作成
            request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
            http_request_record = HttpRequestRecord(
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
        from src.domain.task_queue.http_request.model import HttpRequestRecord

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
            request_time = datetime(2025, 9, 29, 10, 0, tzinfo=timezone.utc)
            failed_request = HttpRequestRecord(
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

    def test_search_articles_by_ids_returns_dict(self, fs) -> None:
        """
        docs:
            目的:
                複数IDで複数のArticleを取得でき、
                idをkeyとしたdictが返ることを確認する。
            検証観点:
                - 複数のHttpRequestRecordとバケットデータからArticleが復元される。
                - 返り値がdict[str, Article]である。
                - キーはhttp_request_idと一致する。
        """

        import os
        from datetime import datetime, timezone
        from pathlib import Path
        from typing import cast

        from pydantic import HttpUrl

        from infra.storage.rds import session_scope
        from src.domain.task_queue.http_request.model import HttpRequestRecord

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
            # 複数のHttpRequestレコードを作成
            request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
            http_request_records = [
                HttpRequestRecord(
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
        from src.domain.task_queue.http_request.model import HttpRequestRecord

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
            request_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)

            # 成功するレコード
            success_record = HttpRequestRecord(
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
            failed_status_record = HttpRequestRecord(
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
            no_bucket_record = HttpRequestRecord(
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
            assert retrieved["success"].content == "<html>success</html>"
            assert retrieved["failed_status"] is None
            assert retrieved["no_bucket"] is None
            assert retrieved["missing"] is None

    def test_search_articles_by_ids_returns_empty_dict_for_empty_list(self, fs) -> None:
        """
        docs:
            目的: 空リストを渡した場合、空のdictが返ることを確認する。
            検証観点:
                - http_request_ids=[] で空dictが返る。
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
