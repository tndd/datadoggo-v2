"""domain.news.article.fetch のテスト"""

from datetime import datetime, timezone
from typing import cast

from pydantic import HttpUrl

from domain.news.article.fetch import fetch_article_content
from domain.task_queue.http_request.model import HttpRequestTask
from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient


def test_fetch_article_content_returns_model_on_success() -> None:
    """
    docs:
        目的: ステータス200の場合にArticleが生成されることを確認する。
        検証観点:
            - HTML本文がデコードされる。
            - HttpRequestTaskの属性が引き継がれる。
            - description が nullable であることを確認する。
    """

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

    request = HttpRequestTask(
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
    request_no_desc = HttpRequestTask(
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


def test_fetch_article_content_returns_none_on_error_status() -> None:
    """
    docs:
        目的: ステータスが200以外の場合にNoneが返ることを確認する。
        検証観点:
            - HTTP 404 時にNoneが返る。
    """

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

    request = HttpRequestTask(
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
