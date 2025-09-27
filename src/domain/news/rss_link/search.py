# rssをbucketから読み込む

from __future__ import annotations

from pathlib import Path

from infra.storage.bucket import (
    DEFAULT_STORAGE_ROOT,
    load_object,
    save_object,
    search_object_keys,
)


def search_rss_keys(
    *,
    prefix: str = "",
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
) -> list[str]:
    """RSSバケット内のオブジェクトキー一覧を取得する"""

    return search_object_keys(
        bucket_name=bucket_name,
        prefix=prefix,
        storage_root=storage_root,
    )


def find_rss_content(
    key: str,
    *,
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
    as_text: bool = True,
    encoding: str = "utf-8",
) -> str | bytes:
    """指定キーのRSSコンテンツを読み込む"""

    return load_object(
        bucket_name=bucket_name,
        object_key=key,
        storage_root=storage_root,
        as_text=as_text,
        encoding=encoding,
    )


class Tests:
    class search_rss_keys:
        def test_search_rss_keys_returns_matching_keys(self, tmp_path) -> None:
            """
            docs:
                目的:
                    RSSバケットに保存されたキーを検索できることを確認する。
                検証観点:
                    - prefix で絞り込んだキー一覧が取得できる。
                    - 該当無しの場合は空リストとなる。
            """

            storage_root = tmp_path / "bucket"
            bucket_name = "rss"
            save_object(
                "alpha",
                bucket_name=bucket_name,
                object_key="aa001",
                storage_root=storage_root,
            )
            save_object(
                "beta",
                bucket_name=bucket_name,
                object_key="bb001",
                storage_root=storage_root,
            )

            all_keys = search_rss_keys(storage_root=storage_root)
            assert set(all_keys) == {"aa001", "bb001"}

            filtered = search_rss_keys(prefix="aa", storage_root=storage_root)
            assert filtered == ["aa001"]

            missing = search_rss_keys(prefix="zz", storage_root=storage_root)
            assert missing == []

    class find_rss_content:
        def test_find_rss_content_returns_text(self, tmp_path) -> None:
            """
            docs:
                目的:
                    保存済みRSSコンテンツをテキストとして取得できることを確認する。
                検証観点:
                    - 保存した文字列が復元される。
                    - 存在しないキーでは空文字列となる。
            """

            storage_root = tmp_path / "bucket"
            bucket_name = "rss"
            key = "feed001"
            save_object(
                "<rss>alpha</rss>",
                bucket_name=bucket_name,
                object_key=key,
                storage_root=storage_root,
            )

            content = find_rss_content(
                key,
                storage_root=storage_root,
            )
            assert content == "<rss>alpha</rss>"

            missing = find_rss_content(
                "unknown",
                storage_root=storage_root,
            )
            assert missing == ""

        def test_find_rss_content_returns_bytes(self, tmp_path) -> None:
            """
            docs:
                目的:
                    バイト列として保存されたRSSコンテンツを復元できることを確認する。
                検証観点:
                    - as_text=False 指定で元のバイト列が取得できる。
            """

            storage_root = tmp_path / "bucket"
            bucket_name = "rss"
            key = "feed-bytes"
            payload = b"<rss>bytes</rss>"
            save_object(
                payload,
                bucket_name=bucket_name,
                object_key=key,
                storage_root=storage_root,
            )

            content = find_rss_content(
                key,
                storage_root=storage_root,
                as_text=False,
            )
            assert content == payload
