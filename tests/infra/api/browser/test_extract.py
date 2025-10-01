"""infra.api.browser.extract のテスト"""

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from infra.api.browser.extract import (
    ExtractMode,
    _parse_to_markdown,
    _parse_to_text,
    extract_page_content,
)
from infra.storage.file import load_file


def test_extract_page_content(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: extract_page_content の各モードでの変換動作を確認する。
        検証観点:
            - HTML モードは元のHTMLをそのまま返す
            - TEXT モードはプレーンテキストに変換される
            - MARKDOWN モードはMarkdown形式に変換される
            - 不正なモードの場合はValueErrorが発生する
    """
    # プロジェクトルートから計算
    project_root = Path(__file__).parent.parent.parent.parent
    fs.add_real_directory(project_root / "mock", read_only=True)
    html = load_file(str(project_root / "mock/plain.html"))

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


def test_parse_html_to_text(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: _parse_to_text の基本的なHTML→テキスト変換を確認する。
        検証観点:
            - HTMLタグが除去される
            - スクリプトやスタイルが除去される
            - テキスト内容が適切に抽出される
    """
    project_root = Path(__file__).parent.parent.parent.parent
    fs.add_real_directory(project_root / "mock", read_only=True)
    html = load_file(str(project_root / "mock/plain.html"))
    text = _parse_to_text(html)

    assert text is not None
    assert "DataDoggo テストサイト" in text
    assert "<html>" not in text
    assert "<script>" not in text
    assert "<style>" not in text
    assert "Rust言語の新機能について" in text


def test_parse_html_to_markdown(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: _parse_to_markdown の基本的なHTML→Markdown変換を確認する。
        検証観点:
            - HTMLがMarkdown形式に変換される
            - 見出しが # 記法になる
            - リストやテーブルが適切に変換される
    """
    project_root = Path(__file__).parent.parent.parent.parent
    fs.add_real_directory(project_root / "mock", read_only=True)
    html = load_file(str(project_root / "mock/plain.html"))
    markdown = _parse_to_markdown(html)

    assert markdown is not None
    assert "# DataDoggo テストサイト" in markdown
    assert "## " in markdown  # h2タグの変換確認
    assert "* " in markdown or "- " in markdown  # リストの変換確認


def test_parse_empty_html(fs: FakeFilesystem) -> None:
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
