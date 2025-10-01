"""domain.task_queue.http_request.service のテスト"""

import json

import pytest

from domain.task_queue.http_request.service import convert_rss_items_to_http_requests
from infra.parse import parse_rss


def test_convert_rss_items_to_http_requests_skips_incomplete_item() -> None:
    """
    docs:
        目的:
            必須要素が欠けたitemをスキップすることを確認する。
        検証観点:
            - linkが欠けたitemは結果に含まれない。
            - 妥当なitemのみがHttpRequestTaskとして返る。
    """

    rss_xml = """
        <rss version="2.0">
            <channel>
                <item>
                    <title>Valid</title>
                    <link>https://example.com/valid</link>
                    <pubDate>Tue, 23 Sep 2025 09:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Missing link</title>
                    <pubDate>Tue, 23 Sep 2025 09:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
    """
    root = parse_rss(rss_xml)

    items = convert_rss_items_to_http_requests(root, group="mock:missing")

    assert len(items) == 1
    assert str(items[0].url) == "https://example.com/valid"
    assert items[0].status_code is None


def test_convert_rss_items_to_http_requests_skips_invalid_http_url() -> None:
    """
    docs:
        目的:
            URLが不正なitemが全体処理を止めずにスキップされることを確認する。
        検証観点:
            - 不正URLのitemは結果に含まれない。
            - 妥当なitemはHttpRequestTaskとして生成される。
    """

    rss_xml = """
        <rss version="2.0">
            <channel>
                <item>
                    <title>Invalid URL</title>
                    <link>notaurl</link>
                    <pubDate>Sat, 27 Sep 2025 15:30:00 GMT</pubDate>
                </item>
                <item>
                    <title>Valid URL</title>
                    <link>https://example.com/article</link>
                    <pubDate>Sat, 27 Sep 2025 15:30:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
    """
    root = parse_rss(rss_xml)

    items = convert_rss_items_to_http_requests(root, group="mock:invalid")

    assert len(items) == 1
    first = items[0]
    assert first.description == "Valid URL"
    assert str(first.url) == "https://example.com/article"


def test_convert_rss_items_to_http_requests_logs_invalid_http_url(
    app_logging,
) -> None:
    """
    docs:
        目的:
            不正URLを含むitemをスキップした際にログへ詳細が出力されることを確認する。
        検証観点:
            - ログファイルが生成され、メッセージがJSONで出力される。
            - ログのextraにrss_groupとrequest_urlが含まれる。
    """

    rss_xml = """
        <rss version="2.0">
            <channel>
                <item>
                    <title>Broken</title>
                    <link>notaurl</link>
                    <pubDate>Sat, 27 Sep 2025 15:30:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
    """
    root = parse_rss(rss_xml)

    items = convert_rss_items_to_http_requests(root, group="mock:logging")

    assert not items

    log_path = app_logging
    assert log_path.exists()

    log_lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert log_lines, "ログが1行以上出力されること"
    payload = json.loads(log_lines[-1])
    record = payload["record"]
    assert record["message"] == "invalid http request task item skipped"
    extra = record["extra"]
    assert extra["rss_group"] == "mock:logging"
    assert extra["request_url"] == "notaurl"


def test_convert_rss_items_to_http_requests_raises_without_channel() -> None:
    """
    docs:
        目的:
            channel要素を持たないRSS入力では例外が送出されることを確認する。
        検証観点:
            - ValueError が送出される。
    """

    import xml.etree.ElementTree as ET

    root = ET.fromstring("<rss version='2.0'></rss>")

    with pytest.raises(ValueError):
        convert_rss_items_to_http_requests(root, group="mock:none")
