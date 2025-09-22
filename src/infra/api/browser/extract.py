"""ブラウザから記事コンテンツを抽出するロジック"""

from enum import Enum


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
    pass


def _parse_to_markdown(html: str) -> str:
    """HTMLをMarkdownに変換する"""
    pass


### TEST ###
class Tests:
    def test_extract_page_content(self) -> None:
        pass

    class TestPrivate:
        def test_parse_html_to_text(self) -> None:
            pass

        def test_parse_html_to_markdown(self) -> None:
            pass
