"""Article用のHTML取得処理"""

from __future__ import annotations

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.logging import get_logger
from src.domain.task_queue.http_request.model import HttpRequest

from .model import Article

_log = get_logger()


def fetch_article_content(
    request: HttpRequest, *, client: HttpsClient | None = None
) -> Article | None:
    """HttpRequestを基に記事HTMLを取得しArticleを生成する"""

    http_client = client or HttpsClient()

    try:
        response = http_client.get(str(request.url))
    except RuntimeError:  # pragma: no cover - ネットワーク例外のログ確認
        _log.exception(
            "記事HTML取得中にネットワークエラーが発生しました",
            feed_id=request.id,
            url=str(request.url),
        )
        return None

    if response.status_code != HTTP_STATUS_OK:
        _log.warning(
            "記事HTMLの取得に失敗しました",
            feed_id=request.id,
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
        created_at=now,
        updated_at=now,
        description=request.description,
    )
    _log.info(
        "記事HTMLの取得に成功しました",
        feed_id=request.id,
        url=str(request.url),
        bytes=len(response.body),
    )
    return article


def _decode_body(response: HttpResponse) -> str:
    """HTTPレスポンスボディをテキスト化する"""

    encoding = response.encoding or "utf-8"
    return response.body.decode(encoding)


class TestMod:
    """このモジュールのテストコレクション"""

    def test_fetch_article_content_returns_model_on_success(self) -> None:
        """
        docs:
            目的: ステータス200の場合にArticleが生成されることを確認する。
            検証観点:
                - HTML本文がデコードされる。
                - HttpRequestの属性が引き継がれる。
                - description が nullable であることを確認する。
        """

        from datetime import datetime, timezone
        from typing import cast

        from pydantic import HttpUrl

        html_text = "<html><body>記事</body></html>"
        html_bytes = html_text.encode("utf-8")

        def mock_fetcher(
            method: str,
            url: str,
            headers: dict[str, str],
            data: bytes | None,
            timeout: float,
        ) -> HttpResponse:
            return HttpResponse(
                url=url,
                method=method,
                status_code=HTTP_STATUS_OK,
                headers={},
                body=html_bytes,
                encoding="utf-8",
            )

        client = HttpsClient(fetcher=mock_fetcher)

        request = HttpRequest(
            id="abc",
            url=cast(HttpUrl, "https://example.com/detail"),
            description="テスト",
            group="test:fetch",
            status_code=200,
            created_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
        )

        article = fetch_article_content(request, client=client)

        assert article is not None
        assert article.content == html_text
        assert article.id == request.id
        assert article.description == "テスト"

        # description が None のケース
        request_no_desc = HttpRequest(
            id="xyz",
            url=cast(HttpUrl, "https://example.com/no-title"),
            description=None,
            group="test:fetch",
            status_code=200,
            created_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
        )

        article_no_desc = fetch_article_content(request_no_desc, client=client)

        assert article_no_desc is not None
        assert article_no_desc.description is None

    def test_fetch_article_content_returns_none_on_error_status(self) -> None:
        """
        docs:
            目的: ステータスが200以外の場合にNoneが返ることを確認する。
            検証観点:
                - HTTP 404 時にNoneが返る。
        """

        from datetime import datetime, timezone
        from typing import cast

        from pydantic import HttpUrl

        def mock_fetcher(
            method: str,
            url: str,
            headers: dict[str, str],
            data: bytes | None,
            timeout: float,
        ) -> HttpResponse:
            return HttpResponse(
                url=url,
                method=method,
                status_code=404,
                headers={},
                body=b"",
                encoding="utf-8",
            )

        client = HttpsClient(fetcher=mock_fetcher)

        request = HttpRequest(
            id="abc",
            url=cast(HttpUrl, "https://example.com/detail"),
            description="テスト",
            group="test:fetch",
            status_code=None,
            created_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 9, 29, 12, 0, tzinfo=timezone.utc),
        )

        article = fetch_article_content(request, client=client)

        assert article is None
