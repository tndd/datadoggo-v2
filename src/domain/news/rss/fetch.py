# リンク経由で外部通信してコンテンツを取得

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree.ElementTree import Element

import pytest

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.compute import normalize_parallel
from infra.parse.rss import parse_rss

from .model import RssItem


def fetch_rss_element(url: str, *, client: HttpsClient | None = None) -> Element:
    """指定URLのRSSフィードを取得しXMLルート要素として返す"""

    http_client = client or HttpsClient()
    response = http_client.get(url)

    if response.status_code != HTTP_STATUS_OK:
        raise RuntimeError(f"RSS取得に失敗しました: status={response.status_code}")

    return parse_rss(response.body)


def fetch_rss_from_links(
    items: list[RssItem],
    *,
    client: HttpsClient | None = None,
    parallel: bool | int = False,
) -> list[Element]:
    """RssItem の一覧を受け取り RSS のルート要素を取得する"""

    if not items:
        return []

    worker_count = normalize_parallel(parallel, len(items))
    if worker_count <= 1:
        return [fetch_rss_element(item.url, client=client) for item in items]

    results: list[Element | None] = [None] * len(items)

    def make_client() -> HttpsClient | None:
        if client is None:
            return None
        return client.clone()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                fetch_rss_element,
                rss_item.url,
                client=make_client(),
            ): index
            for index, rss_item in enumerate(items)
        }

        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()

    return [element for element in results if element is not None]


class TestMod:
    """このモジュールのテストコレクション"""

    def test_fetch_rss_element_returns_rss_root(self) -> None:
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

    def test_fetch_rss_element_raises_on_non_success_status(self) -> None:
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

    def test_fetch_rss_from_links_fetches_each_item(self) -> None:
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

    def test_fetch_rss_from_links_returns_empty_on_no_items(self) -> None:
        """
        docs:
            目的: 取得対象が存在しない場合でも例外なく空リストを返すことを確認する。
            検証観点:
                - 空リスト入力で空リストが返る。
        """

        roots = fetch_rss_from_links([])
        assert roots == []

    def test_fetch_rss_from_links_runs_in_parallel(self) -> None:
        """
        docs:
            目的:
                parallel オプション指定時に並列取得が行われることを確認する。
            検証観点:
                - 戻り値の順序が入力順に保たれる。
                - 実行スレッドが ThreadPoolExecutor のワーカーになる。
        """

        import threading
        import time

        rss_payloads = {
            "https://example.com/rss": (
                b"<rss version='2.0'><channel>"
                b"<title>SlowHeadline</title></channel></rss>"
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
