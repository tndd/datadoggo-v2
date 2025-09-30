"""Article用のHTML取得処理"""

from __future__ import annotations

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.logging import get_logger
from src.domain.request_queue.model import HttpRequest

from .model import Article

_log = get_logger()


def fetch_article_content(
    request: HttpRequest, *, client: HttpsClient | None = None
) -> Article | None:
    """HttpRequestを基に記事HTMLを取得しArticleを生成する"""

    http_client = client or HttpsClient()

    try:
        response = http_client.get(str(request.url))
    except Exception as error:  # pragma: no cover - ネットワーク例外のログ確認
        _log.exception(
            "記事HTML取得中に例外が発生しました",
            feed_id=request.id,
            url=str(request.url),
            error=str(error),
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

    html = _decode_body(response)
    article = Article(
        id=request.id,
        url=request.url,
        title=request.description or "",
        pub_date=request.created_at,
        html_content=html,
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
                - FeedItemの属性が引き継がれる。
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
        assert article.html_content == html_text
        assert article.id == request.id

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
