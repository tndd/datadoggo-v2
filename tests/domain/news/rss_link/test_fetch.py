"""domain.news.rss_link.fetch のテスト"""

import threading
import time
from xml.etree.ElementTree import Element

import pytest

from domain.news.rss_link.fetch import fetch_rss_element, fetch_rss_from_links
from domain.news.rss_link.model import RssItem
from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient

"""このモジュールのテストコレクション"""


def test_fetch_rss_element_returns_rss_root() -> None:
    """
    docs:
    目的:
        モックレスポンスを用いて fetch_rss_element が
        rss ルート要素を返すことを確認する。
    検証観点:
        - ステータスコード 200 のレスポンスで Element が得られる。
        - body の内容が parse_rss へ渡される。
    """
    rss_xml = b"<rss version='2.0'><channel><title>Example</title></channel></rss>"

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
            body=rss_xml,
            encoding="utf-8",
        )

    client = HttpsClient(fetcher=mock_fetcher)

    root = fetch_rss_element("https://example.com/rss", client=client)

    assert isinstance(root, Element)
    assert root.tag.endswith("rss")


def test_fetch_rss_element_raises_on_non_success_status() -> None:
    """
    docs:
    目的:
        ステータスコードが200以外の場合に例外が送出されることを確認する。
    検証観点:
        - RuntimeError が発生する。
    """

    def error_fetcher(
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes | None,
        timeout: float,
    ) -> HttpResponse:
        return HttpResponse(
            url=url,
            method=method,
            status_code=500,
            headers={},
            body=b"",
            encoding="utf-8",
        )

    client = HttpsClient(fetcher=error_fetcher)

    with pytest.raises(RuntimeError):
        fetch_rss_element("https://example.com/rss", client=client)


def test_fetch_rss_from_links_fetches_each_item() -> None:
    """
    docs:
    目的:
        渡された RssItem ごとに RSS を取得できることを確認する。
    検証観点:
        - 全ての URL へアクセスが発生する。
        - 戻り値の Element からタイトルを読み取れる。
    """
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

    items = [
        RssItem(group="sample", name="headline", url="https://example.com/rss"),
        RssItem(group="sample", name="latest", url="https://example.com/rss-2"),
    ]

    roots = fetch_rss_from_links(items, client=client)

    assert set(fetched_urls) == set(rss_payloads)
    assert len(roots) == len(rss_payloads)
    titles = {element.findtext("channel/title") for element in roots}
    assert titles == {"Headline", "Latest"}


def test_fetch_rss_from_links_returns_empty_on_no_items() -> None:
    """
    docs:
    目的: 取得対象が存在しない場合でも例外なく空リストを返すことを確認する。
    検証観点:
        - 空リスト入力で空リストが返る。
    """
    roots = fetch_rss_from_links([])
    assert roots == []


def test_fetch_rss_from_links_runs_in_parallel() -> None:
    """
    docs:
    目的:
        parallel オプション指定時に並列取得が行われることを確認する。
    検証観点:
        - 戻り値の順序が入力順に保たれる。
        - 実行スレッドが ThreadPoolExecutor のワーカーになる。
    """

    rss_payloads = {
        "https://example.com/rss": (
            b"<rss version='2.0'><channel><title>SlowHeadline</title></channel></rss>"
        ),
        "https://example.com/rss-2": (
            b"<rss version='2.0'><channel><title>FastLatest</title></channel></rss>"
        ),
    }

    thread_names: list[str] = []

    def mock_fetcher(
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes | None,
        timeout: float,
    ) -> HttpResponse:
        thread_names.append(threading.current_thread().name)
        if url.endswith("/rss"):
            time.sleep(0.01)
        return HttpResponse(
            url=url,
            method=method,
            status_code=HTTP_STATUS_OK,
            headers={},
            body=rss_payloads[url],
            encoding="utf-8",
        )

    client = HttpsClient(fetcher=mock_fetcher)

    items = [
        RssItem(group="sample", name="headline", url="https://example.com/rss"),
        RssItem(group="sample", name="latest", url="https://example.com/rss-2"),
    ]

    roots = fetch_rss_from_links(
        items,
        client=client,
        parallel=True,
    )

    assert [root.findtext("channel/title") for root in roots] == [
        "SlowHeadline",
        "FastLatest",
    ]
    assert all(name.startswith("ThreadPoolExecutor") for name in thread_names)
