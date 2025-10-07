"""RSSリンク関連サービス"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infra.web.https import HTTP_STATUS_OK, HttpResponse, HttpsClient

from .common import convert_rss_element_to_http_requests
from .fetch import fetch_rss_from_links
from .search import RssItemQuery, load_rss_links

if TYPE_CHECKING:
    from domain.news.task_queue.http_request.model import HttpRequestTask


def fetch_http_requests_from_query(
    query: RssItemQuery,
    *,
    client: HttpsClient | None = None,
    parallel: bool | int = False,
) -> list[HttpRequestTask]:
    """RssItemQuery に一致するリンクを取得し HttpRequestTask リストを返す"""

    rss_items = load_rss_links(query)
    elements = fetch_rss_from_links(rss_items, client=client, parallel=parallel)

    # 各ElementをHttpRequestTaskリストに変換して結合
    http_requests: list[HttpRequestTask] = []
    for rss_item, element in zip(rss_items, elements, strict=True):
        # RssItemからgroupを取得（group:nameの形式）
        group = f"{rss_item.group}:{rss_item.name}"
        http_requests.extend(convert_rss_element_to_http_requests(element, group=group))

    return http_requests


class TestMod:
    """このモジュールのテストコレクション"""

    def test_fetch_http_requests_from_query_returns_http_requests(
        self, tmp_path
    ) -> None:
        """
        docs:
            目的:
                RssItemQuery で指定したリンクの HttpRequestTask が
                取得できることを確認する。
            検証観点:
                - group 指定で絞り込まれたリンクのみが通信される。
                - HttpRequestTaskからdescription, url, groupが読み取れる。
        """

        yaml_path = tmp_path / "links.yml"
        yaml_path.write_text(
            "\n".join(
                [
                    "sample:",
                    "  headline: https://example.com/rss",
                    "  latest: https://example.com/rss-2",
                    "other:",
                    "  daily: https://example.com/rss-3",
                ]
            ),
            encoding="utf-8",
        )

        rss_payloads = {
            "https://example.com/rss": (
                b"<rss version='2.0'><channel>"
                b"<item>"
                b"<title>Headline Article</title>"
                b"<link>https://example.com/article1</link>"
                b"<pubDate>Tue, 01 Oct 2025 12:00:00 GMT</pubDate>"
                b"</item>"
                b"</channel></rss>"
            ),
            "https://example.com/rss-2": (
                b"<rss version='2.0'><channel>"
                b"<item>"
                b"<title>Latest Article</title>"
                b"<link>https://example.com/article2</link>"
                b"<pubDate>Tue, 01 Oct 2025 13:00:00 GMT</pubDate>"
                b"</item>"
                b"</channel></rss>"
            ),
        }
        fetched_urls: list[str] = []

        def mock_fetcher(
            method: str,
            url: str,
            headers: dict[str, str],
            data: bytes | None,
            timeout: float,
        ) -> HttpResponse:
            fetched_urls.append(url)
            assert url in rss_payloads
            return HttpResponse(
                url=url,
                method=method,
                status_code=HTTP_STATUS_OK,
                headers={},
                body=rss_payloads[url],
                encoding="utf-8",
            )

        client = HttpsClient(fetcher=mock_fetcher)

        http_requests = fetch_http_requests_from_query(
            RssItemQuery(group="sample", path=str(yaml_path)),
            client=client,
        )

        expected_request_count = 2

        assert set(fetched_urls) == set(rss_payloads)
        assert len(http_requests) == expected_request_count
        descriptions = {req.description for req in http_requests}
        assert descriptions == {"Headline Article", "Latest Article"}
        groups = {req.group for req in http_requests}
        assert groups == {"sample:headline", "sample:latest"}

    def test_fetch_http_requests_from_query_returns_empty_when_not_matched(
        self, tmp_path
    ) -> None:
        """
        docs:
            目的: クエリに一致するリンクが無い場合でも空リストで返ることを確認する。
            検証観点:
                - 通信は発生せず空リストとなる。
        """

        yaml_path = tmp_path / "links.yml"
        yaml_path.write_text(
            """
            sample:
            headline: https://example.com/rss
            """.strip(),
            encoding="utf-8",
        )

        def error_fetcher(
            method: str,
            url: str,
            headers: dict[str, str],
            data: bytes | None,
            timeout: float,
        ) -> HttpResponse:
            raise AssertionError("通信が発生してはいけません。")

        client = HttpsClient(fetcher=error_fetcher)

        http_requests = fetch_http_requests_from_query(
            RssItemQuery(group="missing", path=str(yaml_path)),
            client=client,
        )

        assert http_requests == []
