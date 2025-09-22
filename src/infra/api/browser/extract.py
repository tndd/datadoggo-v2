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


### TEST ###
class Tests:
    def test_extract_page_content(self) -> None:
        """
        docs:
            目的: extract_page_content の各モードでの変換動作を確認する。
            検証観点:
                - HTML モードは元のHTMLをそのまま返す
                - TEXT モードはプレーンテキストに変換される
                - MARKDOWN モードはMarkdown形式に変換される
                - 不正なモードの場合はValueErrorが発生する
        """
        from infra.storage.file.load import load_file

        html = load_file("src/infra/api/browser/mock/plain.html")

        # HTMLモード
        result_html = extract_page_content(html, ExtractMode.HTML)
        assert result_html == html

        # TEXTモード
        result_text = extract_page_content(html, ExtractMode.TEXT)
        assert "DataDoggo テストサイト" in result_text
        assert "<html>" not in result_text

        # MARKDOWNモード
        result_markdown = extract_page_content(html, ExtractMode.MARKDOWN)
        assert "# DataDoggo テストサイト" in result_markdown
        assert "**" in result_markdown or "_" in result_markdown

        # 不正なモード
        try:
            extract_page_content(html, ExtractMode("invalid"))  # 不正な値でEnumを生成
            raise AssertionError("ValueErrorが発生するべき")
        except ValueError:
            pass

    class TestsPrivate:
        def test_parse_html_to_text(self) -> None:
            """
            docs:
                目的: _parse_to_text の基本的なHTML→テキスト変換を確認する。
                検証観点:
                    - HTMLタグが除去される
                    - スクリプトやスタイルが除去される
                    - テキスト内容が適切に抽出される
            """
            from infra.storage.file.load import load_file

            html = load_file("src/infra/api/browser/mock/plain.html")
            text = _parse_to_text(html)

            assert text is not None
            assert "DataDoggo テストサイト" in text
            assert "<html>" not in text
            assert "<script>" not in text
            assert "<style>" not in text
            assert "Rust言語の新機能について" in text

        def test_parse_html_to_markdown(self) -> None:
            """
            docs:
                目的: _parse_to_markdown の基本的なHTML→Markdown変換を確認する。
                検証観点:
                    - HTMLがMarkdown形式に変換される
                    - 見出しが # 記法になる
                    - リストやテーブルが適切に変換される
            """
            from infra.storage.file.load import load_file

            html = load_file("src/infra/api/browser/mock/plain.html")
            markdown = _parse_to_markdown(html)

            assert markdown is not None
            assert "# DataDoggo テストサイト" in markdown
            assert "## " in markdown  # h2タグの変換確認
            assert "* " in markdown or "- " in markdown  # リストの変換確認

        def test_parse_empty_html(self) -> None:
            """
            docs:
                目的: 空のHTMLや無効なHTMLに対する関数の挙動を確認する。
                検証観点:
                    - 空文字列を渡した場合の処理
                    - エラーが発生しないこと
            """
            # 空文字列
            text = _parse_to_text("")
            assert text == ""

            markdown = _parse_to_markdown("")
            assert markdown == ""

            # 不正なHTML
            invalid_html = "<html><body><p>test</p></body>"  # 閉じタグなし
            text = _parse_to_text(invalid_html)
            assert "test" in text

            markdown = _parse_to_markdown(invalid_html)
            assert "test" in markdown
