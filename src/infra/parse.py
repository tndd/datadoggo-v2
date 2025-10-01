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


