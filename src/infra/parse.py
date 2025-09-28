"""汎用的な入力解析ユーティリティ"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import pytest

from infra.logging import get_logger

RSS_INPUT = Union[str, bytes, bytearray]
_AMPERSAND_PATTERN = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9A-Fa-f]+);)")

LOG = get_logger()


def parse_rss(payload: RSS_INPUT) -> Element:
    """RSSフィードのXML文字列を解析しルート要素を返す"""

    source = _normalize_rss_payload(payload)

    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        LOG.error("RSSのXML解析に失敗しました", error=str(exc))
        raise ValueError("RSSのXML解析に失敗しました") from exc

    if _extract_local_name(root.tag) != "rss":
        LOG.error("RSSのルート要素がrssではありません", tag=root.tag)
        raise ValueError("RSSのルート要素がrssではありません")

    return root


def _normalize_rss_payload(payload: RSS_INPUT) -> str:
    """RSS入力をXMLパーサが扱えるUTF-8文字列に正規化する"""

    text: str
    if isinstance(payload, (bytes, bytearray)):
        raw_bytes = bytes(payload)
        if not raw_bytes.strip():
            LOG.error("RSSコンテンツが空です", input_type=type(payload).__name__)
            raise ValueError("RSSコンテンツが空です")
        text = raw_bytes.decode("utf-8")
    elif isinstance(payload, str):
        if not payload.strip():
            LOG.error("RSSコンテンツが空です", input_type=type(payload).__name__)
            raise ValueError("RSSコンテンツが空です")
        text = payload
    else:
        LOG.error(
            "RSS解析に不正な入力型が渡されました",
            input_type=type(payload).__name__,
        )
        raise TypeError("RSSの解析には文字列またはバイト列を渡してください")

    if "&" in text:
        text = _AMPERSAND_PATTERN.sub("&amp;", text)

    return text


def _extract_local_name(tag: str) -> str:
    """名前空間付きタグからローカル名のみを取り出す"""

    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


class Tests:
    def test_parse_rss_returns_rss_root(self) -> None:
        """
        docs:
            目的:
                RSSモックファイルを解析し、rssルート要素が取得できることを確認する。
            検証観点:
                - parse_rss の戻り値が Element インスタンスであること。
                - ルートタグが rss であること。
                - channel 要素が存在すること。
        """

        fixture_path = Path(__file__).resolve().parents[2] / "mock" / "google_news.rss"
        content = fixture_path.read_bytes()

        root = parse_rss(content)

        assert isinstance(root, Element)
        assert _extract_local_name(root.tag) == "rss"
        channel = root.find("channel")
        assert channel is not None

    def test_parse_rss_rejects_non_rss_root(self) -> None:
        """
        docs:
            目的:
                rss以外のルート要素を持つXMLを渡した際に例外を送出することを確認する。
            検証観点:
                - ValueError が送出される。
        """

        invalid_xml = "<feed><title>Example</title></feed>"

        with pytest.raises(ValueError):
            parse_rss(invalid_xml)

    def test_parse_rss_rejects_empty_payload(self) -> None:
        """
        docs:
            目的:
                空文字列を渡した場合に適切な例外が送出されることを確認する。
            検証観点:
                - ValueError が送出される。
        """

        with pytest.raises(ValueError):
            parse_rss("")

    def test_parse_rss_rejects_broken_xml(self) -> None:
        """
        docs:
            目的:
                閉じタグの欠落したXMLを渡した場合に解析エラーとなることを確認する。
            検証観点:
                - ValueError が送出される。
        """

        broken_xml = "<rss><channel><title>Example"  # 閉じタグ欠落

        with pytest.raises(ValueError):
            parse_rss(broken_xml)

    def test_parse_rss_sanitizes_unescaped_ampersand(self) -> None:
        """
        docs:
            目的:
                アンパサンドがエスケープされていない入力でも解析できることを確認する。
            検証観点:
                - `&` が含まれていても ValueError にならない。
                - channel 要素を取得できる。
        """

        xml_with_ampersand = """
            <rss version="2.0">
                <channel>
                    <title>Example & Co.</title>
                </channel>
            </rss>
        """

        root = parse_rss(xml_with_ampersand)

        assert _extract_local_name(root.tag) == "rss"
        assert root.find("channel") is not None
