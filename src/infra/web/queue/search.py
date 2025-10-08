"""RequestTaskをrequest_task_queueテーブルから読み出す処理"""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import select

from infra.storage.rds import session_scope

from .common import record_to_request_task
from .model import RequestTask, RequestTaskRecord


class SearchRequestTaskQuery(BaseModel):
    """RequestTask検索時の条件入力モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    description: str | None = None
    url: str | None = None
    group: str | None = None
    status_code: int | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None


def find_request_task_by_id(task_id: str) -> RequestTask | None:
    """IDでRequestTaskを検索し、存在すれば返す"""

    with session_scope() as session:
        statement = select(RequestTaskRecord).where(RequestTaskRecord.id == task_id)
        record = session.exec(statement).first()
        if record is None:
            return None

        return record_to_request_task(record)


def search_request_tasks(query: SearchRequestTaskQuery) -> list[RequestTask]:
    """RequestTaskをページングして取得する"""

    with session_scope() as session:
        statement = select(RequestTaskRecord)

        if query.description:
            statement = statement.where(
                # SQLModelの動的属性(contains)はSQLAlchemyカラムのメソッドだが、
                # 型チェッカーでは認識されない既知の問題のため型無視
                # 参考: https://github.com/fastapi/sqlmodel/discussions/428
                RequestTaskRecord.description.contains(query.description)  # type: ignore[attr-defined]
            )

        if query.url:
            statement = statement.where(RequestTaskRecord.url == query.url)

        if query.group:
            statement = statement.where(
                # SQLModelの動的属性(contains)はSQLAlchemyカラムのメソッドだが、
                # 型チェッカーでは認識されない既知の問題のため型無視
                # 参考: https://github.com/fastapi/sqlmodel/discussions/428
                RequestTaskRecord.group.contains(query.group)  # type: ignore[attr-defined]
            )

        if query.status_code is not None:
            statement = statement.where(
                RequestTaskRecord.status_code == query.status_code
            )

        if query.created_at_from is not None:
            statement = statement.where(
                RequestTaskRecord.created_at >= query.created_at_from
            )

        if query.created_at_to is not None:
            statement = statement.where(
                RequestTaskRecord.created_at <= query.created_at_to
            )

        statement = (
            # SQLAlchemyのdesc()関数はカラム型を受け取るが、SQLModelの型定義では
            # カラム型が適切に推論されない既知の問題のため型無視
            # 参考: https://github.com/fastapi/sqlmodel/discussions/428
            statement.order_by(desc(RequestTaskRecord.created_at))  # type: ignore[arg-type]
            .offset(query.offset)
            .limit(query.limit)
        )
        records = session.exec(statement).all()
        return [record_to_request_task(item) for item in records]


class TestMod:
    def test_find_request_task_by_id_returns_item(self) -> None:
        """
        docs:
            目的:
                find_request_task_by_id が既存レコードを取得できることを確認する。
            検証観点:
                - store_request_task で保存したIDを指定すると RequestTask が返る。
                - 取得した RequestTask の属性が保存時と一致する。
                - created_at / updated_at が取得結果でも保持される。
        """
        from datetime import datetime

        from infra.storage.rds import initialize_database

        from .common import create_request_task
        from .store import store_request_task

        # テーブル作成
        initialize_database()

        request = create_request_task(
            url="https://example.com/find",
            description="Find Target",
            group="test:find",
            status_code=200,
            created_at=datetime(2024, 2, 1, 8, 0, 0),
        )
        stored = store_request_task(request)

        fetched = find_request_task_by_id(request.id)
        assert fetched is not None
        assert fetched.id == request.id
        assert fetched.description == "Find Target"
        assert fetched.created_at == stored.created_at
        assert fetched.updated_at == stored.updated_at

    def test_find_request_task_by_id_returns_none_when_missing(self) -> None:
        """
        docs:
            目的:
                存在しないIDで find_request_task_by_id を呼び出した際に
                None が返ることを確認する。
            検証観点:
                - 例外が発生しない。
                - 戻り値が None になる。
        """
        from infra.storage.rds import initialize_database

        # テーブル作成
        initialize_database()

        missing = find_request_task_by_id("non-existent")
        assert missing is None

    def test_search_request_tasks_filters_and_order(self) -> None:
        """
        docs:
            目的:
                search_request_tasks が条件指定と並び替えを正しく行うことを確認する。
            検証観点:
                - created_atの降順で並ぶ。
                - limit/offset が期待どおり機能する。
                - description/status_code/created_at範囲/url/group 条件で絞り込める。
        """
        from datetime import datetime

        from infra.storage.rds import initialize_database

        from .common import create_request_task
        from .store import store_request_task

        # テーブル作成
        initialize_database()

        request_success = create_request_task(
            url="https://example.com/success",
            description="Daily Success Report",
            group="test:success",
            status_code=200,
            created_at=datetime(2024, 1, 10, 8, 0, 0),
        )
        request_failure = create_request_task(
            url="https://example.com/failure",
            description="Weekly Failure Recap",
            group="test:failure",
            status_code=500,
            created_at=datetime(2024, 1, 5, 8, 0, 0),
        )
        request_other = create_request_task(
            url="https://example.org/other",
            description="Daily Other News",
            group="other:news",
            status_code=200,
            created_at=datetime(2024, 1, 12, 12, 0, 0),
        )

        for req in (request_success, request_failure, request_other):
            store_request_task(req)

        expected_count = 2
        result = search_request_tasks(
            SearchRequestTaskQuery(limit=expected_count, offset=0)
        )
        assert len(result) == expected_count
        assert result[0].created_at > result[1].created_at

        description_filtered = search_request_tasks(
            SearchRequestTaskQuery(description="Daily", limit=10)
        )
        assert {item.id for item in description_filtered} == {
            request_success.id,
            request_other.id,
        }

        status_filtered = search_request_tasks(
            SearchRequestTaskQuery(status_code=500, limit=10)
        )
        assert [item.id for item in status_filtered] == [request_failure.id]

        range_filtered = search_request_tasks(
            SearchRequestTaskQuery(
                created_at_from=datetime(2024, 1, 6, 0, 0, 0),
                created_at_to=datetime(2024, 1, 11, 23, 59, 59),
                limit=10,
            )
        )
        assert [item.id for item in range_filtered] == [request_success.id]

        url_filtered = search_request_tasks(
            SearchRequestTaskQuery(url="https://example.org/other", limit=10)
        )
        assert [item.id for item in url_filtered] == [request_other.id]

        group_filtered = search_request_tasks(
            SearchRequestTaskQuery(group="test", limit=10)
        )
        assert {item.id for item in group_filtered} == {
            request_success.id,
            request_failure.id,
        }
