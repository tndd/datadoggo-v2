"""RSSリンクを読み込むためのユーティリティ"""

from __future__ import annotations

from yaml import YAMLError, safe_load

from infra.storage.file import load_file

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
