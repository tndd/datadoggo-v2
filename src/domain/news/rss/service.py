"""RSS固有の変換サービス"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import pytest
from pydantic import ValidationError

from domain.task_queue.http_request.model import HttpRequestTask
from domain.task_queue.http_request.service import create_http_request
from infra.logging import get_logger
from infra.parse import parse_rss

DEFAULT_HTTP_REQUEST_STATUS_CODE = None
_log = get_logger()


def convert_rss_element_to_http_requests(
    root: Element,
    *,
    group: str | None,
    default_status_code: int | None = DEFAULT_HTTP_REQUEST_STATUS_CODE,
) -> list[HttpRequestTask]:
    """RSSのitem要素をHttpRequestTaskリストに変換する"""

    channel = _extract_channel(root)
    http_requests: list[HttpRequestTask] = []

    for item in channel.findall("item"):
        link = _extract_text(item, "link")
        title = _extract_text(item, "title")
        published_at_text = _extract_text(item, "pubDate")

        if not link or not title or not published_at_text:
            continue

        published_at = _parse_published_at(published_at_text)
        if published_at is None:
            continue

        try:
            http_requests.append(
                create_http_request(
                    url=link,
                    description=title,
                    group=group,
                    status_code=default_status_code,
                    created_at=published_at,
                )
            )
        except (ValueError, ValidationError) as exc:
            _log.warning(
                "invalid http request task item skipped",
                rss_group=group,
                request_url=link,
                error_type=type(exc).__name__,
                exception_message=str(exc),
                description=title,
            )
            continue

    return http_requests


def _extract_channel(root: Element) -> Element:
    """RSSルートまたはchannel要素を返す"""

    local_name = _local_name(root.tag)
    if local_name == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSSにchannel要素が存在しません")
        return channel

    if local_name == "channel":
        return root

    raise ValueError("RSSルートにchannel要素が存在しません")


def _extract_text(parent: Element, tag: str) -> str | None:
    """指定タグのテキストを抽出し前後の空白を除去する"""

    child = parent.find(tag)
    if child is None:
        return None

    text = _join_itertext(child)
    stripped = text.strip()
    if not stripped:
        return None
    return stripped


def _join_itertext(element: Element) -> str:
    """要素内のテキストノードを結合する"""

    return "".join(part for part in element.itertext() if part)


def _parse_published_at(value: str) -> datetime | None:
    """RSS日付文字列をUTCのdatetimeに変換する"""

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _local_name(tag: str) -> str:
    """名前空間付きタグからローカル名のみを返す"""

    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


class TestMod:
    def test_convert_rss_element_to_http_requests_parses_mock_feed(self) -> None:
        """
        docs:
            目的:
                RSSモックファイルからHttpRequestTaskリストが生成されることを確認する。
            検証観点:
                - item要素からHttpRequestTaskが生成される。
                - pubDateがcreated_atとしてUTCのdatetimeに変換される。
                - titleがdescriptionとして設定される。
        """

        fixture_path = Path(__file__).resolve().parents[4] / "mock" / "google_news.rss"
        content = fixture_path.read_bytes()
        root = parse_rss(content)

        items = convert_rss_element_to_http_requests(root, group="mock:google")

        assert items, "HttpRequestTaskが1件以上生成されること"
        first = items[0]
        assert first.description and first.description.startswith(
            "Stocks dip as dollar rises"
        )
        assert str(first.url).startswith("https://news.google.com/rss/articles/")
        expected_datetime = datetime(2025, 9, 24, 11, 52, 38, tzinfo=timezone.utc)
        assert first.created_at == expected_datetime
        assert first.status_code is DEFAULT_HTTP_REQUEST_STATUS_CODE
        assert first.group == "mock:google"
        assert first.updated_at.tzinfo is not None

    def test_convert_rss_element_to_http_requests_skips_incomplete_item(self) -> None:
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

        items = convert_rss_element_to_http_requests(root, group="mock:missing")

        assert len(items) == 1
        assert str(items[0].url) == "https://example.com/valid"
        assert items[0].status_code is DEFAULT_HTTP_REQUEST_STATUS_CODE

    def test_convert_rss_element_to_http_requests_skips_invalid_http_url(self) -> None:
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

        items = convert_rss_element_to_http_requests(root, group="mock:invalid")

        assert len(items) == 1
        first = items[0]
        assert first.description == "Valid URL"
        assert str(first.url) == "https://example.com/article"

    def test_convert_rss_element_to_http_requests_logs_invalid_http_url(
        self,
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

        items = convert_rss_element_to_http_requests(root, group="mock:logging")

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

    def test_convert_rss_element_to_http_requests_raises_without_channel(self) -> None:
        """
        docs:
            目的:
                channel要素を持たないRSS入力では例外が送出されることを確認する。
            検証観点:
                - ValueError が送出される。
        """

        root = ET.fromstring("<rss version='2.0'></rss>")

        with pytest.raises(ValueError):
            convert_rss_element_to_http_requests(root, group="mock:none")
