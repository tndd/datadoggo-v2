"""RSSフィードを取得して解析するユーティリティ"""

from __future__ import annotations

from xml.etree.ElementTree import Element

import pytest

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.parse import parse_rss


def fetch_rss_element(url: str, *, client: HttpsClient | None = None) -> Element:
    """指定URLのRSSフィードを取得しXMLルート要素として返す"""

    http_client = client or HttpsClient()
    response = http_client.get(url)

    if response.status_code != HTTP_STATUS_OK:
        raise RuntimeError(f"RSS取得に失敗しました: status={response.status_code}")

    return parse_rss(response.body)


class Tests:
    class fetch_rss_element:
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

            rss_xml = (
                b"<rss version='2.0'><channel><title>Example</title></channel></rss>"
            )

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
