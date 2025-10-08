"""RequestTask向け共通サービスユーティリティ"""

import hashlib
from datetime import datetime

from pydantic import HttpUrl, TypeAdapter

from .model import RequestTask, RequestTaskRecord

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列やHttpUrlを受け取りHttpUrlとして正規化する"""
    return _HTTP_URL_ADAPTER.validate_python(value)


def ensure_saved_at(value: datetime | None = None) -> datetime:
    """保存日時をUTCのtimezone-aware datetimeに整形する"""
    from datetime import timezone

    target = value or datetime.now(timezone.utc)
    if target.tzinfo is None:
        return target.replace(tzinfo=timezone.utc)
    return target.astimezone(timezone.utc)


def create_request_task(
    *,
    url: str,
    description: str | None,
    group: str | None,
    status_code: int | None,
    created_at: datetime | None = None,
) -> RequestTask:
    """入力値からRequestTaskドメインモデルを生成する"""

    request_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
    normalized_created_at = ensure_saved_at(created_at)
    normalized_updated_at = normalized_created_at

    return RequestTask(
        id=request_id,
        url=ensure_http_url(url),
        description=description,
        group=group,
        status_code=status_code,
        created_at=normalized_created_at,
        updated_at=normalized_updated_at,
    )


def request_task_to_record(task: RequestTask) -> RequestTaskRecord:
    """RequestTaskドメインモデルを永続化レコードへ変換する"""

    return RequestTaskRecord(
        id=task.id,
        url=str(task.url),
        description=task.description,
        group=task.group,
        status_code=task.status_code,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def record_to_request_task(record: RequestTaskRecord) -> RequestTask:
    """永続化レコードをRequestTaskドメインモデルに変換する"""

    return RequestTask(
        id=record.id,
        url=ensure_http_url(record.url),
        description=record.description,
        group=record.group,
        status_code=record.status_code,
        created_at=ensure_saved_at(record.created_at),
        updated_at=ensure_saved_at(record.updated_at),
    )
