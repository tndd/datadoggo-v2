"""Feed向け共通サービスユーティリティ"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import pytest
from pydantic import ValidationError

from infra.compute import hash_text_sha256
from infra.logging import get_logger
from infra.parse import parse_rss

from ..common import ensure_http_url
from .model import FeedItem, FeedRecord

DEFAULT_FEED_STATUS_CODE = None
_log = get_logger()


def create_feed(
    url: str,
    title: str,
    bucket_id: str,
    status_code: int | None,
    pub_date: datetime,
) -> FeedItem:
    """入力値からFeedドメインモデルを生成する"""

    feed_id = hash_text_sha256(url)
    return FeedItem(
        id=feed_id,
        url=ensure_http_url(url),
        title=title,
        bucket_id=bucket_id,
        status_code=status_code,
        pub_date=pub_date,
    )


def feed_to_record(feed: FeedItem) -> FeedRecord:
    """Feedドメインモデルを永続化レコードへ変換する"""

    return FeedRecord(
        id=feed.id,
        url=str(feed.url),
        title=feed.title,
        status_code=feed.status_code,
        pub_date=feed.pub_date,
        bucket_id=feed.bucket_id,
    )


def record_to_feed(record: FeedRecord) -> FeedItem:
    """永続化レコードをFeedドメインモデルに変換する"""

    return FeedItem(
        id=record.id,
        url=ensure_http_url(record.url),
        title=record.title,
        status_code=record.status_code,
        pub_date=record.pub_date,
        bucket_id=record.bucket_id,
    )


def convert_rss_items_to_feed_items(
    root: Element,
    *,
    bucket_id: str,
    default_status_code: int | None = DEFAULT_FEED_STATUS_CODE,
) -> list[FeedItem]:
    """RSSのitem要素をFeedItemリストに変換する"""

    channel = _extract_channel(root)
    feed_items: list[FeedItem] = []

    for item in channel.findall("item"):
        link = _extract_text(item, "link")
        title = _extract_text(item, "title")
        pub_date_text = _extract_text(item, "pubDate")

        if not link or not title or not pub_date_text:
            continue

        pub_date = _parse_pub_date(pub_date_text)
        if pub_date is None:
            continue

        try:
            feed_items.append(
                create_feed(
                    url=link,
                    title=title,
                    bucket_id=bucket_id,
                    status_code=default_status_code,
                    pub_date=pub_date,
                )
            )
        except (ValueError, ValidationError) as exc:
            _log.warning(
                "invalid feed item skipped",
                bucket_id=bucket_id,
                feed_url=link,
                error_type=type(exc).__name__,
                exception_message=str(exc),
                feed_title=title,
            )
            continue

    return feed_items


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


def _parse_pub_date(value: str) -> datetime | None:
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


class Tests:
    def test_convert_rss_items_to_feed_items_parses_mock_feed(self) -> None:
        """
        docs:
            目的:
                RSSモックファイルからFeedItemリストが生成されることを確認する。
            検証観点:
                - item要素からFeedItemが生成される。
                - pubDateがUTCのdatetimeに変換される。
                - bucket_id が指定値で保持される。
        """

        fixture_path = Path(__file__).resolve().parents[4] / "mock" / "google_news.rss"
        content = fixture_path.read_bytes()
        root = parse_rss(content)

        items = convert_rss_items_to_feed_items(root, bucket_id="rss-bucket-1")

        assert items, "FeedItemが1件以上生成されること"
        first = items[0]
        assert first.title.startswith("Stocks dip as dollar rises")
        assert str(first.url).startswith("https://news.google.com/rss/articles/")
        expected_datetime = datetime(2025, 9, 24, 11, 52, 38, tzinfo=timezone.utc)
        assert first.pub_date == expected_datetime
        assert first.status_code is DEFAULT_FEED_STATUS_CODE
        assert first.bucket_id == "rss-bucket-1"

    def test_convert_rss_items_to_feed_items_skips_incomplete_item(self) -> None:
        """
        docs:
            目的:
                必須要素が欠けたitemをスキップすることを確認する。
            検証観点:
                - linkが欠けたitemは結果に含まれない。
                - 妥当なitemのみがFeedItemとして返る。
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

        items = convert_rss_items_to_feed_items(root, bucket_id="rss-bucket-2")

        assert len(items) == 1
        assert str(items[0].url) == "https://example.com/valid"
        assert items[0].status_code is DEFAULT_FEED_STATUS_CODE

    def test_convert_rss_items_to_feed_items_skips_invalid_http_url(self) -> None:
        """
        docs:
            目的:
                URLが不正なitemが全体処理を止めずにスキップされることを確認する。
            検証観点:
                - 不正URLのitemは結果に含まれない。
                - 妥当なitemはFeedItemとして生成される。
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

        items = convert_rss_items_to_feed_items(root, bucket_id="rss-bucket-4")

        assert len(items) == 1
        first = items[0]
        assert first.title == "Valid URL"
        assert str(first.url) == "https://example.com/article"
        assert first.bucket_id == "rss-bucket-4"

    def test_convert_rss_items_to_feed_items_logs_invalid_http_url(
        self,
        app_logging,
    ) -> None:
        """
        docs:
            目的:
                不正URLを含むitemをスキップした際にログへ詳細が出力されることを確認する。
            検証観点:
                - ログファイルが生成され、メッセージがJSONで出力される。
                - ログのextraにbucket_idとfeed_urlが含まれる。
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

        items = convert_rss_items_to_feed_items(root, bucket_id="rss-bucket-5")

        assert not items

        log_path = app_logging
        assert log_path.exists()

        log_lines = [line for line in log_path.read_text().splitlines() if line.strip()]
        assert log_lines, "ログが1行以上出力されること"
        payload = json.loads(log_lines[-1])
        record = payload["record"]
        assert record["message"] == "invalid feed item skipped"
        extra = record["extra"]
        assert extra["bucket_id"] == "rss-bucket-5"
        assert extra["feed_url"] == "notaurl"

    def test_convert_rss_items_to_feed_items_raises_without_channel(self) -> None:
        """
        docs:
            目的:
                channel要素を持たないRSS入力では例外が送出されることを確認する。
            検証観点:
                - ValueError が送出される。
        """

        root = ET.fromstring("<rss version='2.0'></rss>")

        with pytest.raises(ValueError):
            convert_rss_items_to_feed_items(root, bucket_id="rss-bucket-3")
