"""XML/RSS解析のテスト"""

from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from infra.parse import _extract_local_name, parse_rss


def test_parse_rss_returns_rss_root(fs: FakeFilesystem) -> None:
    """
    docs:
        目的:
            RSSモックファイルを解析し、rssルート要素が取得できることを確認する。
        検証観点:
            - parse_rss の戻り値が Element インスタンスであること。
            - ルートタグが rss であること。
            - channel 要素が存在すること。
    """

    # 実ファイルシステムからmockディレクトリを追加
    project_root = Path(__file__).parent.parent.parent
    fs.add_real_directory(project_root / "mock", read_only=True)
    fixture_path = project_root / "mock" / "google_news.rss"
    content = fixture_path.read_bytes()

    root = parse_rss(content)

    assert isinstance(root, Element)
    assert _extract_local_name(root.tag) == "rss"
    channel = root.find("channel")
    assert channel is not None


def test_parse_rss_rejects_non_rss_root() -> None:
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


def test_parse_rss_rejects_empty_payload() -> None:
    """
    docs:
        目的:
            空文字列を渡した場合に適切な例外が送出されることを確認する。
        検証観点:
            - ValueError が送出される。
    """

    with pytest.raises(ValueError):
        parse_rss("")


def test_parse_rss_rejects_broken_xml() -> None:
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


def test_parse_rss_sanitizes_unescaped_ampersand() -> None:
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
