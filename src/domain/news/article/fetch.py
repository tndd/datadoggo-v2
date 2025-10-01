"""Article用のHTML取得処理"""

from __future__ import annotations

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.logging import get_logger
from domain.task_queue.http_request.model import HttpRequestTask

from .model import Article

_log = get_logger()


def fetch_article_content(
    request: HttpRequestTask, *, client: HttpsClient | None = None
) -> Article | None:
    """HttpRequestTaskを基に記事HTMLを取得しArticleを生成する

    タイムスタンプの挙動:
        - created_at: HttpRequestTaskのcreated_atを保持（記事の公開日時を表す）
        - updated_at: 現在時刻を設定（記事HTMLの取得日時を表す）
    """

    http_client = client or HttpsClient()

    try:
        response = http_client.get(str(request.url))
    except Exception as error:  # pragma: no cover - ネットワーク例外のログ確認
        _log.exception(
            "記事HTML取得中に例外が発生しました",
            http_request_id=request.id,
            url=str(request.url),
            error_type=type(error).__name__,
        )
        return None

    if response.status_code != HTTP_STATUS_OK:
        _log.warning(
            "記事HTMLの取得に失敗しました",
            http_request_id=request.id,
            url=str(request.url),
            status_code=response.status_code,
        )
        return None

    from datetime import datetime, timezone

    html = _decode_body(response)
    now = datetime.now(timezone.utc)
    article = Article(
        id=request.id,
        url=request.url,
        content=html,
        group=request.group,
        created_at=request.created_at,  # 記事の公開日時を保持
        updated_at=now,  # HTML取得日時として現在時刻を設定
        description=request.description,
    )
    _log.info(
        "記事HTMLの取得に成功しました",
        http_request_id=request.id,
        url=str(request.url),
        bytes=len(response.body),
    )
    return article


def _decode_body(response: HttpResponse) -> str:
    """HTTPレスポンスボディをテキスト化する"""

    encoding = response.encoding or "utf-8"
    return response.body.decode(encoding)
