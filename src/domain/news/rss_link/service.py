"""RSSリンクを読み込むためのユーティリティ"""

from __future__ import annotations

from yaml import YAMLError, safe_load

from src.infra.storage.file import load_file

from .model import RssItem


def load_rss_links(path: str = "./links.yml") -> list[RssItem]:
    """links.yml を読み込み RssItem の一覧を返す"""

    yaml_text = load_file(path)
    if not yaml_text.strip():
        return []

    try:
        raw = safe_load(yaml_text) or {}
    except YAMLError as error:
        raise ValueError("links.yml の読み込みに失敗しました。") from error

    if not isinstance(raw, dict):
        raise ValueError("links.yml の形式が不正です。")

    links: list[RssItem] = []
    for group, mapping in raw.items():
        if not isinstance(group, str):
            raise ValueError("RSSリンクのグループ名が文字列ではありません。")
        if not isinstance(mapping, dict):
            raise ValueError(f"{group} のリンク定義がマッピングではありません。")

        for name, url in mapping.items():
            if not isinstance(name, str):
                raise ValueError(f"{group} のリンク名が文字列ではありません。")
            if not isinstance(url, str):
                raise ValueError(f"{group}::{name} のURLが文字列ではありません。")
            links.append(RssItem(group=group, name=name, url=url))

    return links


class Tests:
    class Test_load_rss_links:
        def test_load_rss_links_reads_default_file(self) -> None:
            """
            docs:
                目的: 規定の links.yml から RSS リンクを読み込めることを確認する。
                検証観点:
                    - 相対パス指定で links.yml が解決される。
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

        def test_load_rss_links_rejects_invalid_structure(self, tmp_path) -> None:
            """
            docs:
                目的: links.yml の構造が不正な場合に例外が送出されることを確認する。
                検証観点:
                    - グループ配下が辞書以外のとき ValueError となる。
            """

            invalid_yaml = tmp_path / "links.yml"
            invalid_yaml.write_text("- just: text\n", encoding="utf-8")

            try:
                load_rss_links(str(invalid_yaml))
                raise AssertionError("不正な構造で例外が発生しませんでした。")
            except ValueError:
                pass
