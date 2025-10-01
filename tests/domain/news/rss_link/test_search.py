"""domain.news.rss_link.search のテスト"""

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from domain.news.rss_link.search import RssItemQuery, load_rss_links



"""このモジュールのテストコレクション"""

def test_load_rss_links_reads_default_file() -> None:
    """
    docs:
    目的: 規定の links.yml から RSS リンクを読み込めることを確認する。
    検証観点:
        - デフォルトクエリで links.yml が解決される。
        - 代表的なリンク (bbc/top) が取得できる。
    """

links = load_rss_links()
assert links, "links.yml からリンクが取得できていません。"
assert any(
    link.group == "bbc"
    and link.name == "top"
    and link.url.startswith("https://feeds.bbci.co.uk")
    for link in links
), "bbc/top のリンクが存在しません。"

def test_load_rss_links_rejects_invalid_structure(fs: FakeFilesystem) -> None:
    """
    docs:
    目的: links.yml の構造が不正な場合に例外が送出されることを確認する。
    検証観点:
        - グループ配下が辞書以外のとき ValueError となる。
    """

    invalid_yaml = Path("/tmp/links.yml")
    fs.create_file(str(invalid_yaml), contents="- just: text\n")

    try:
        load_rss_links(RssItemQuery(path=str(invalid_yaml)))
        raise AssertionError("不正な構造で例外が発生しませんでした。")
    except ValueError:
        pass

def test_load_rss_links_filters_by_query(fs: FakeFilesystem) -> None:
    """
    docs:
    目的:
        クエリ指定で group/name に合致するリンクだけを
        取得できることを確認する。
    検証観点:
        - group 指定で該当グループのみ抽出される。
        - name まで指定すると1件に絞り込まれる。
    """

    yaml_path = Path("/tmp/links.yml")
    fs.create_file(
        str(yaml_path),
        contents="""
sample:
  headline: https://example.com/rss
  latest: https://example.com/rss-2
other:
  daily: https://example.com/rss-3
""".strip(),
    )

    group_only = load_rss_links(RssItemQuery(group="sample", path=str(yaml_path)))
    assert {item.name for item in group_only} == {"headline", "latest"}

    narrowed = load_rss_links(
        RssItemQuery(group="sample", name="latest", path=str(yaml_path))
    )
    assert [item.url for item in narrowed] == ["https://example.com/rss-2"]
