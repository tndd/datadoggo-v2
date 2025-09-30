"""Feedテーブルへの書き込み処理(CQRSのコマンド側)"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from domain.common import ensure_saved_at
from infra.storage.rds import session_scope

from .model import HttpRequest, HttpRequestRecord
from .service import create_http_request, http_request_to_record, record_to_http_request


def store_http_request(request: HttpRequest) -> HttpRequest:
    """HttpRequestを保存し、保存後の状態を返す"""

    with session_scope() as session:
        normalized = request.model_copy(update={"updated_at": ensure_saved_at()})
        record = http_request_to_record(normalized)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return record_to_http_request(merged)


class TestMod:
    def test_store_http_request_persists_record(self) -> None:
        """
        docs:
            目的:
                store_http_request が永続化を行い、戻り値として最新状態の
                HttpRequest を返すことを確認する。
            検証観点:
                - create_http_request で生成した HttpRequest が
                  store_http_request で保存される。
                - 保存後に同一IDのレコードがDB上に存在する。
                - created_at が保持され、updated_at が更新される。
        """

        # pytestにより自動的にインメモリDBが使用される
        request = create_http_request(
            url="https://example.com/store",
            description="Store Request",
            group="test:store",
            status_code=201,
            created_at=datetime(2024, 1, 1, 9, 0, 0),
        )

        stored = store_http_request(request)
        assert stored.id == request.id
        assert stored.status_code == request.status_code
        assert stored.created_at == ensure_saved_at(datetime(2024, 1, 1, 9, 0, 0))
        assert stored.updated_at >= stored.created_at

        with session_scope() as session:
            statement = select(HttpRequestRecord).where(
                HttpRequestRecord.id == request.id
            )
            record = session.exec(statement).first()
            assert record is not None
            assert record.description == "Store Request"
            assert record.group == "test:store"
            assert ensure_saved_at(record.created_at) == stored.created_at
            assert ensure_saved_at(record.updated_at) == stored.updated_at
