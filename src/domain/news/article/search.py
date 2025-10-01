"""Article検索とArticle再構築"""

from __future__ import annotations

from sqlmodel import Session, col, select

from domain.common import ensure_http_url
from infra.storage.bucket import load_object, load_objects
from domain.task_queue.http_request.model import HttpRequestTaskRecord

from .model import Article

# HTTPステータスコード
HTTP_OK = 200


def find_article_by_id(session: Session, http_request_id: str) -> Article | None:
    """保存済みArticleを取得する。http_request_queueテーブルからメタデータを取得し、バケットからHTMLを取得"""

    # http_request_queueテーブルからメタデータを取得
    statement = select(HttpRequestTaskRecord).where(
        HttpRequestTaskRecord.id == http_request_id
    )
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
    statement = select(HttpRequestTaskRecord).where(
        col(HttpRequestTaskRecord.id).in_(http_request_ids)
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
