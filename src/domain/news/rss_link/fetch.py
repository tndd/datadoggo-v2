# リンク経由で外部通信してコンテンツを取得

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree.ElementTree import Element

from infra.api.https import HTTP_STATUS_OK, HttpsClient
from infra.parse import parse_rss

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

    worker_count = _normalize_parallel(parallel, len(items))
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


def _normalize_parallel(parallel: bool | int, item_count: int) -> int:
    """並列実行時のワーカー数を決定する"""

    if not parallel:
        return 1

    if parallel is True:
        return max(1, item_count)

    if isinstance(parallel, int):
        if parallel <= 1:
            return 1
        return min(parallel, item_count)

    return 1
