"""HttpRequestTask向け共通サービスユーティリティ"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element

from pydantic import ValidationError

from domain.common import ensure_http_url, ensure_saved_at
from infra.compute import hash_text_sha256
from infra.logging import get_logger

from .model import HttpRequestTask, HttpRequestTaskRecord

DEFAULT_HTTP_REQUEST_STATUS_CODE = None
_log = get_logger()


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


def convert_rss_items_to_http_requests(
    root: Element,
    *,
    group: str | None,
    default_status_code: int | None = DEFAULT_HTTP_REQUEST_STATUS_CODE,
) -> list[HttpRequestTask]:
    """RSSのitem要素をHttpRequestTaskリストに変換する"""

    channel = _extract_channel(root)
    http_requests: list[HttpRequestTask] = []

    for item in channel.findall("item"):
        link = _extract_text(item, "link")
        title = _extract_text(item, "title")
        published_at_text = _extract_text(item, "pubDate")

        if not link or not title or not published_at_text:
            continue

        published_at = _parse_published_at(published_at_text)
        if published_at is None:
            continue

        try:
            http_requests.append(
                create_http_request(
                    url=link,
                    description=title,
                    group=group,
                    status_code=default_status_code,
                    created_at=published_at,
                )
            )
        except (ValueError, ValidationError) as exc:
            _log.warning(
                "invalid http request task item skipped",
                rss_group=group,
                request_url=link,
                error_type=type(exc).__name__,
                exception_message=str(exc),
                description=title,
            )
            continue

    return http_requests


def _extract_channel(root: Element) -> Element:
    """RSSルートまたはchannel要素を返す"""

    local_name = _local_name(root.tag)
    if local_name == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSSにchannel要素が存在しません")
        return channel

    if local_name == "channel":
        return root

    raise ValueError("RSSルートにchannel要素が存在しません")


def _extract_text(parent: Element, tag: str) -> str | None:
    """指定タグのテキストを抽出し前後の空白を除去する"""

    child = parent.find(tag)
    if child is None:
        return None

    text = _join_itertext(child)
    stripped = text.strip()
    if not stripped:
        return None
    return stripped


def _join_itertext(element: Element) -> str:
    """要素内のテキストノードを結合する"""

    return "".join(part for part in element.itertext() if part)


def _parse_published_at(value: str) -> datetime | None:
    """RSS日付文字列をUTCのdatetimeに変換する"""

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _local_name(tag: str) -> str:
    """名前空間付きタグからローカル名のみを返す"""

    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag
