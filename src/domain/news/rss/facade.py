"""RSSリンク関連サービス"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient

from .fetch import fetch_rss_from_links
from .search import RssItemQuery, load_rss_links


def fetch_rss_elements_from_query(
    query: RssItemQuery,
    *,
    client: HttpsClient | None = None,
    parallel: bool | int = False,
) -> list[Element]:
    """RssItemQuery に一致するリンクを取得し RSS のルート要素を返す"""

    rss_items = load_rss_links(query)
    return fetch_rss_from_links(rss_items, client=client, parallel=parallel)


class TestMod:
    """このモジュールのテストコレクション"""

    def test_fetch_rss_elements_from_query_returns_elements(self, tmp_path) -> None:
        """
        docs:
            目的:
                RssItemQuery で指定したリンクの RSS 要素が取得できることを確認する。
            検証観点:
                - group 指定で絞り込まれたリンクのみが通信される。
                - 返却された Element からタイトルが読み取れる。
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
                b"<rss version='2.0'><channel><title>Headline</title></channel></rss>"
            ),
            "https://example.com/rss-2": (
                b"<rss version='2.0'><channel><title>Latest</title></channel></rss>"
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

        elements = fetch_rss_elements_from_query(
            RssItemQuery(group="sample", path=str(yaml_path)),
            client=client,
        )

        assert set(fetched_urls) == set(rss_payloads)
        assert {element.findtext("channel/title") for element in elements} == {
            "Headline",
            "Latest",
        }

    def test_fetch_rss_elements_from_query_returns_empty_when_not_matched(
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

        elements = fetch_rss_elements_from_query(
            RssItemQuery(group="missing", path=str(yaml_path)),
            client=client,
        )

        assert elements == []
