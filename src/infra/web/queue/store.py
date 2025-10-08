"""RequestTaskをrequest_task_queueテーブルへ書き込む処理"""

from infra.storage.rds import save_record, save_records

from .common import ensure_saved_at, record_to_request_task, request_task_to_record
from .model import RequestTask


def store_request_task(task: RequestTask) -> RequestTask:
    """RequestTaskを保存し、保存後の状態を返す"""

    normalized = task.model_copy(update={"updated_at": ensure_saved_at()})
    record = request_task_to_record(normalized)
    saved_record = save_record(record)
    return record_to_request_task(saved_record)


def store_request_tasks(tasks: list[RequestTask]) -> list[RequestTask]:
    """複数のRequestTaskを一括保存し、保存後の状態を返す"""

    if not tasks:
        return []

    normalized_tasks = [
        task.model_copy(update={"updated_at": ensure_saved_at()}) for task in tasks
    ]
    records = [request_task_to_record(task) for task in normalized_tasks]
    saved_records = save_records(records)
    return [record_to_request_task(record) for record in saved_records]


class TestMod:
    def test_store_request_task_persists_record(self) -> None:
        """
        docs:
            目的:
                store_request_task が永続化を行い、戻り値として最新状態の
                RequestTask を返すことを確認する。
            検証観点:
                - create_request_task で生成した RequestTask が
                  store_request_task で保存される。
                - 保存後に同一IDのレコードがDB上に存在する。
                - created_at が保持され、updated_at が更新される。
        """
        from datetime import datetime

        from sqlmodel import select

        from infra.storage.rds import initialize_database, session_scope

        from .common import create_request_task
        from .model import RequestTaskRecord

        # テーブル作成
        initialize_database()

        request = create_request_task(
            url="https://example.com/store",
            description="Store Request",
            group="test:store",
            status_code=201,
            created_at=datetime(2024, 1, 1, 9, 0, 0),
        )

        stored = store_request_task(request)
        assert stored.id == request.id
        assert stored.status_code == request.status_code
        assert stored.created_at == request.created_at
        assert stored.updated_at >= stored.created_at

        with session_scope() as session:
            statement = select(RequestTaskRecord).where(
                RequestTaskRecord.id == request.id
            )
            record = session.exec(statement).first()
            assert record is not None
            assert record.description == "Store Request"
            assert record.group == "test:store"
