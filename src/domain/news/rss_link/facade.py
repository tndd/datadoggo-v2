"""RSSリンク関連サービス"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from infra.api.https import HttpsClient

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
