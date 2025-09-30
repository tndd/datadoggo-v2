"""RSSリンクを読み込むためのユーティリティ"""

from __future__ import annotations

from yaml import YAMLError, safe_load

from src.infra.storage.file import load_file

from .model import RssItem, RssItemQuery


def load_rss_links(query: RssItemQuery | None = None) -> list[RssItem]:
    """links.yml を読み込みクエリに一致する RssItem 一覧を返す"""

    effective_query = query or RssItemQuery()

    yaml_text = load_file(effective_query.path)
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

        if effective_query.group and group != effective_query.group:
            continue

        for name, url in mapping.items():
            if not isinstance(name, str):
                raise ValueError(f"{group} のリンク名が文字列ではありません。")
            if not isinstance(url, str):
                raise ValueError(f"{group}::{name} のURLが文字列ではありません。")
            if effective_query.name and name != effective_query.name:
                continue
            links.append(RssItem(group=group, name=name, url=url))

    return links


class TestMod:
    """このモジュールのテストコレクション"""

    def test_load_rss_links_reads_default_file(self) -> None:
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
            load_rss_links(RssItemQuery(path=str(invalid_yaml)))
            raise AssertionError("不正な構造で例外が発生しませんでした。")
        except ValueError:
            pass

    def test_load_rss_links_filters_by_query(self, tmp_path) -> None:
        """
        docs:
            目的:
                クエリ指定で group/name に合致するリンクだけを
                取得できることを確認する。
            検証観点:
                - group 指定で該当グループのみ抽出される。
                - name まで指定すると1件に絞り込まれる。
        """

        yaml_path = tmp_path / "links.yml"
        yaml_path.write_text(
            """
sample:
  headline: https://example.com/rss
  latest: https://example.com/rss-2
other:
  daily: https://example.com/rss-3
""".strip(),
            encoding="utf-8",
        )

        group_only = load_rss_links(RssItemQuery(group="sample", path=str(yaml_path)))
        assert {item.name for item in group_only} == {"headline", "latest"}

        narrowed = load_rss_links(
            RssItemQuery(group="sample", name="latest", path=str(yaml_path))
        )
        assert [item.url for item in narrowed] == ["https://example.com/rss-2"]
