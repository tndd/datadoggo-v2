# リンク経由で外部通信してコンテンツを取得

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree.ElementTree import Element

import pytest

from infra.api.https import HTTP_STATUS_OK, HttpResponse, HttpsClient
from infra.parse import parse_rss

from .model import RssItem
from .service import load_rss_links


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
    parallel: bool | int = False,
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

    worker_count = _normalize_parallel(parallel, len(filtered))
    if worker_count <= 1:
        return [fetch_rss_element(item.url, client=client) for item in filtered]

    results: list[Element | None] = [None] * len(filtered)

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
            for index, rss_item in enumerate(filtered)
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


class Tests:
    class Test_fetch_rss_element:
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

    class Test_fetch_rss_from_links:
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

        def test_fetch_rss_from_links_runs_in_parallel(self, tmp_path) -> None:
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
                    b"<title>SlowHeadline</title></channel></rss>"
                ),
                "https://example.com/rss-2": (
                    b"<rss version='2.0'><channel>"
                    b"<title>FastLatest</title></channel></rss>"
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

            roots = fetch_rss_from_links(
                "sample",
                links_path=str(yaml_path),
                client=client,
                parallel=True,
            )

            assert [root.findtext("channel/title") for root in roots] == [
                "SlowHeadline",
                "FastLatest",
            ]
            assert all(name.startswith("ThreadPoolExecutor") for name in thread_names)
