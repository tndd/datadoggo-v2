"""HttpRequestTaskをhttp_request_queueテーブルへ書き込む処理(CQRSのコマンド側)"""

from __future__ import annotations

from domain.common import ensure_saved_at
from infra.storage.rds import session_scope

from .model import HttpRequestTask
from .service import http_request_to_record, record_to_http_request


def store_http_request(request: HttpRequestTask) -> HttpRequestTask:
    """HttpRequestTaskを保存し、保存後の状態を返す"""

    with session_scope() as session:
        normalized = request.model_copy(update={"updated_at": ensure_saved_at()})
        record = http_request_to_record(normalized)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return record_to_http_request(merged)
