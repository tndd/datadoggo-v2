"""HttpRequestTask向け共通サービスユーティリティ"""

from __future__ import annotations

from datetime import datetime

from domain.common import ensure_http_url, ensure_saved_at
from infra.compute import hash_text_sha256

from .model import HttpRequestTask, HttpRequestTaskRecord


def create_http_request(
    *,
    url: str,
    description: str | None,
    group: str | None,
    status_code: int | None,
    created_at: datetime | None = None,
) -> HttpRequestTask:
    """入力値からHttpRequestTaskドメインモデルを生成する"""

    request_id = hash_text_sha256(url)
    normalized_created_at = ensure_saved_at(created_at)
    normalized_updated_at = normalized_created_at

    return HttpRequestTask(
        id=request_id,
        url=ensure_http_url(url),
        description=description,
        group=group,
        status_code=status_code,
        created_at=normalized_created_at,
        updated_at=normalized_updated_at,
    )


def http_request_to_record(request: HttpRequestTask) -> HttpRequestTaskRecord:
    """HttpRequestTaskドメインモデルを永続化レコードへ変換する"""

    return HttpRequestTaskRecord(
        id=request.id,
        url=str(request.url),
        description=request.description,
        group=request.group,
        status_code=request.status_code,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def record_to_http_request(record: HttpRequestTaskRecord) -> HttpRequestTask:
    """永続化レコードをHttpRequestTaskドメインモデルに変換する"""

    return HttpRequestTask(
        id=record.id,
        url=ensure_http_url(record.url),
        description=record.description,
        group=record.group,
        status_code=record.status_code,
        created_at=ensure_saved_at(record.created_at),
        updated_at=ensure_saved_at(record.updated_at),
    )
