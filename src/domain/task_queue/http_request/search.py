"""HttpRequestTaskをhttp_request_queueテーブルから読み出す処理(CQRSのクエリ側)"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import select

from infra.storage.rds import session_scope

from .model import HttpRequestTask, HttpRequestTaskRecord
from .service import record_to_http_request


class HttpRequestQuery(BaseModel):
    """HttpRequestTask検索時の条件入力モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    description: str | None = None
    url: str | None = None
    group: str | None = None
    status_code: int | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None


def find_http_request_by_id(request_id: str) -> HttpRequestTask | None:
    """IDでHttpRequestTaskを検索し、存在すれば返す"""

    with session_scope() as session:
        statement = select(HttpRequestTaskRecord).where(
            HttpRequestTaskRecord.id == request_id
        )
        record = session.exec(statement).first()
        if record is None:
            return None

        return record_to_http_request(record)


def search_http_requests(query: HttpRequestQuery) -> list[HttpRequestTask]:
    """HttpRequestTaskをページングして取得する"""

    with session_scope() as session:
        statement = select(HttpRequestTaskRecord)

        if query.description:
            statement = statement.where(
                # SQLModelの動的属性(contains)はSQLAlchemyカラムのメソッドだが、
                # 型チェッカーでは認識されない既知の問題のため型無視
                # 参考: https://github.com/fastapi/sqlmodel/discussions/428
                HttpRequestTaskRecord.description.contains(query.description)  # type: ignore[attr-defined]
            )

        if query.url:
            statement = statement.where(HttpRequestTaskRecord.url == query.url)

        if query.group:
            statement = statement.where(
                # SQLModelの動的属性(contains)はSQLAlchemyカラムのメソッドだが、
                # 型チェッカーでは認識されない既知の問題のため型無視
                # 参考: https://github.com/fastapi/sqlmodel/discussions/428
                HttpRequestTaskRecord.group.contains(query.group)  # type: ignore[attr-defined]
            )

        if query.status_code is not None:
            statement = statement.where(
                HttpRequestTaskRecord.status_code == query.status_code
            )

        if query.created_at_from is not None:
            statement = statement.where(
                HttpRequestTaskRecord.created_at >= query.created_at_from
            )

        if query.created_at_to is not None:
            statement = statement.where(
                HttpRequestTaskRecord.created_at <= query.created_at_to
            )

        statement = (
            # SQLAlchemyのdesc()関数はカラム型を受け取るが、SQLModelの型定義では
            # カラム型が適切に推論されない既知の問題のため型無視
            # 参考: https://github.com/fastapi/sqlmodel/discussions/428
            statement.order_by(desc(HttpRequestTaskRecord.created_at))  # type: ignore[arg-type]
            .offset(query.offset)
            .limit(query.limit)
        )
        records = session.exec(statement).all()
        return [record_to_http_request(item) for item in records]
