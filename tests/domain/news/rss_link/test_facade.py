"""domain.news.rss_link.facade のテスト"""

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from domain.news.rss_link.facade import fetch_rss_elements_from_query
from domain.news.rss_link.search import RssItemQuery
from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient


def test_fetch_rss_elements_from_query_returns_elements(fs: FakeFilesystem) -> None:
    """
    docs:
        目的:
            RssItemQuery で指定したリンクの RSS 要素が取得できることを確認する。
        検証観点:
            - group 指定で絞り込まれたリンクのみが通信される。
            - 返却された Element からタイトルが読み取れる。
    """

    yaml_path = Path("/tmp/links.yml")
    fs.create_file(
        str(yaml_path),
        contents="\n".join(
            [
                "sample:",
                "  headline: https://example.com/rss",
                "  latest: https://example.com/rss-2",
                "other:",
                "  daily: https://example.com/rss-3",
            ]
        ),
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
    fs: FakeFilesystem,
) -> None:
    """
    docs:
        目的: クエリに一致するリンクが無い場合でも空リストで返ることを確認する。
        検証観点:
            - 通信は発生せず空リストとなる。
    """

    yaml_path = Path("/tmp/links.yml")
    fs.create_file(
        str(yaml_path),
        contents="""
        sample:
        headline: https://example.com/rss
        """.strip(),
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
