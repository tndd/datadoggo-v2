"""RSSフィードを取得して解析するユーティリティ"""

from __future__ import annotations

from xml.etree.ElementTree import Element

import pytest

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.parse import parse_rss

from .load import RssItem, load_rss_links


def fetch_rss_element(url: str, *, client: HttpsClient | None = None) -> Element:
    """指定URLのRSSフィードを取得しXMLルート要素として返す"""

    http_client = client or HttpsClient()
    response = http_client.get(url)

    if response.status_code != HTTP_STATUS_OK:
        raise RuntimeError(f"RSS取得に失敗しました: status={response.status_code}")

    return parse_rss(response.body)


def fetch_rss_from_links(
    group: str,
    name: str | None = None,
    *,
    links_path: str | None = None,
    client: HttpsClient | None = None,
) -> list[Element]:
    """links.yml の定義から対象リンクを選び RSS を取得する"""

    target_path = links_path or "./links.yml"
    rss_items: list[RssItem] = load_rss_links(target_path)

    matched_group = [item for item in rss_items if item.group == group]
    if not matched_group:
        raise ValueError(f"指定したグループが見つかりません: group={group}")

    filtered = matched_group
    if name:
        filtered = [item for item in matched_group if item.name == name]
        if not filtered:
            raise ValueError(
                f"指定したリンクが見つかりません: group={group}, name={name}"
            )

    return [fetch_rss_element(item.url, client=client) for item in filtered]


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

    class fetch_rss_from_links:
        def test_fetch_rss_from_links_returns_all_group_links(self, tmp_path) -> None:
            """
            docs:
                目的:
                    links.yml から指定グループのリンクを抽出し
                    それぞれの RSS を取得できることを確認する。
                検証観点:
                    - 同一グループに複数リンクがある場合も全件取得する。
                    - 取得した Element からタイトル情報が読める。
            """

            yaml_path = tmp_path / "links.yml"
            yaml_path.write_text(
                """
                sample:
                headline: https://example.com/rss
                latest: https://example.com/rss-2
                """.strip(),
                encoding="utf-8",
            )

            rss_payloads = {
                "https://example.com/rss": (
                    b"<rss version='2.0'><channel>"
                    b"<title>Headline</title></channel></rss>"
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

            roots = fetch_rss_from_links(
                "sample", links_path=str(yaml_path), client=client
            )

            assert set(fetched_urls) == set(rss_payloads)
            assert len(roots) == len(rss_payloads)
            titles = {element.findtext("channel/title") for element in roots}
            assert titles == {"Headline", "Latest"}

        def test_fetch_rss_from_links_raises_when_not_found(self, tmp_path) -> None:
            """
            docs:
                目的:
                    指定した group/name に一致するリンクが存在しない場合に
                    例外が発生することを確認する。
                検証観点:
                    - 一致無しで ValueError が送出される。
            """

            yaml_path = tmp_path / "links.yml"
            yaml_path.write_text(
                """
                sample:
                headline: https://example.com/rss
                """.strip(),
                encoding="utf-8",
            )

            with pytest.raises(ValueError):
                fetch_rss_from_links("sample", "breaking", links_path=str(yaml_path))

        def test_fetch_rss_from_links_filters_by_name(self, tmp_path) -> None:
            """
            docs:
                目的:
                    name を指定した場合に該当リンクのみを取得することを確認する。
                検証観点:
                    - 指定した name のリンクだけが取得される。
                    - 返却される Element は RSS ルート要素である。
            """

            yaml_path = tmp_path / "links.yml"
            yaml_path.write_text(
                """
                sample:
                headline: https://example.com/rss
                latest: https://example.com/rss-2
                """.strip(),
                encoding="utf-8",
            )

            def mock_fetcher(
                method: str,
                url: str,
                headers: dict[str, str],
                data: bytes | None,
                timeout: float,
            ) -> HttpResponse:
                assert url == "https://example.com/rss-2"
                return HttpResponse(
                    url=url,
                    method=method,
                    status_code=HTTP_STATUS_OK,
                    headers={},
                    body=(
                        b"<rss version='2.0'><channel>"
                        b"<title>OnlyLatest</title></channel></rss>"
                    ),
                    encoding="utf-8",
                )

            client = HttpsClient(fetcher=mock_fetcher)

            roots = fetch_rss_from_links(
                "sample", "latest", links_path=str(yaml_path), client=client
            )

            assert len(roots) == 1
            element = roots[0]
            assert isinstance(element, Element)
            assert element.findtext("channel/title") == "OnlyLatest"
