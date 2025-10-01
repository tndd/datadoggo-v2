"""ブラウザから記事コンテンツを抽出するロジック"""

from enum import Enum

import html2text
from bs4 import BeautifulSoup


class ExtractMode(Enum):
    HTML = "html"
    TEXT = "text"
    MARKDOWN = "markdown"


def extract_page_content(
    html: str,
    mode: ExtractMode,
) -> str:
    """ページHTMLから指定形式のコンテンツを抽出する"""
    match mode:
        case ExtractMode.HTML:
            return html
        case ExtractMode.TEXT:
            return _parse_to_text(html)
        case ExtractMode.MARKDOWN:
            return _parse_to_markdown(html)
        case _:
            raise ValueError(f"不正な抽出モード: {mode}")


def _parse_to_text(html: str) -> str:
    """HTMLをテキストに変換する"""
    soup = BeautifulSoup(html, "html.parser")

    # スクリプトやスタイル要素を除去
    for script in soup(["script", "style"]):
        script.extract()

    # テキストを抽出し、余分な空白を除去
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)

    return text


def _parse_to_markdown(html: str) -> str:
    """HTMLをMarkdownに変換する"""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # 行幅制限なし
    h.unicode_snob = True  # Unicode文字を保持
    h.escape_snob = True  # Markdown特殊文字をエスケープ

    return h.handle(html).strip()


