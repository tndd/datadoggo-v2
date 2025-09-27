"""RSSリンクのロードおよびバケットサービスユーティリティ"""

from __future__ import annotations

from datetime import datetime

from yaml import YAMLError, safe_load

from src.infra.storage.file import load_file

from ..common import ensure_http_url, ensure_saved_at
from .model import RssBucketItem, RssBucketRecord, RssBucketStatus, RssItem


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


def rss_bucket_to_record(item: RssBucketItem) -> RssBucketRecord:
    """ドメインモデルを永続化レコードに変換する"""

    return RssBucketRecord(
        id=item.id,
        group=item.group,
        name=item.name,
        url=str(item.url),
        status=item.status.value,
        saved_at=item.saved_at,
        content_length=item.content_length,
    )


def record_to_rss_bucket(record: RssBucketRecord) -> RssBucketItem:
    """永続化レコードをドメインモデルに変換する"""

    return RssBucketItem(
        id=record.id,
        group=record.group,
        name=record.name,
        url=ensure_http_url(record.url),
        status=RssBucketStatus(record.status),
        saved_at=ensure_saved_at(record.saved_at),
        content_length=record.content_length,
    )


def ensure_rss_bucket_status(value: RssBucketStatus | str) -> RssBucketStatus:
    """ステータス入力を RssBucketStatus へ正規化する"""

    if isinstance(value, RssBucketStatus):
        return value
    return RssBucketStatus(value)


def create_rss_bucket_item(
    *,
    bucket_key: str,
    rss_item: RssItem,
    status: RssBucketStatus | str = RssBucketStatus.registered,
    saved_at: datetime | None = None,
    content_length: int | None = None,
) -> RssBucketItem:
    """RSSバケットエントリのドメインモデルを組み立てる"""

    normalized_url = ensure_http_url(rss_item.url)
    normalized_status = ensure_rss_bucket_status(status)
    normalized_saved_at = ensure_saved_at(saved_at)

    return RssBucketItem(
        id=bucket_key,
        group=rss_item.group,
        name=rss_item.name,
        url=normalized_url,
        status=normalized_status,
        saved_at=normalized_saved_at,
        content_length=content_length,
    )


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

    class Test_rss_bucket_to_record:
        def test_rss_bucket_to_record_preserves_fields(self) -> None:
            """
            docs:
                目的:
                    ドメインモデルが永続化レコードへ正しく変換されることを確認する。
                検証観点:
                    - status が文字列化される。
                    - saved_at や content_length が保持される。
            """

            from datetime import datetime, timezone

            content_length = 1234

            from typing import cast

            from pydantic import HttpUrl

            url_value = cast(HttpUrl, "https://example.com/rss")

            item = RssBucketItem(
                id="abc",
                group="bbc",
                name="top",
                url=url_value,
                status=RssBucketStatus.registered,
                saved_at=datetime(2025, 9, 27, 3, 0, tzinfo=timezone.utc),
                content_length=content_length,
            )

            record = rss_bucket_to_record(item)

            assert record.status == "registered"
            assert record.saved_at == item.saved_at
            assert record.content_length == content_length

    class Test_record_to_rss_bucket:
        def test_record_to_rss_bucket_restores_domain(self) -> None:
            """
            docs:
                目的:
                    永続化レコードからドメインモデルへ復元できることを確認する。
                検証観点:
                    - URL が HttpUrl として検証される。
                    - StrEnum のステータスに戻る。
            """

            from datetime import datetime, timezone

            record = RssBucketRecord(
                id="abc",
                group="bbc",
                name="top",
                url="https://example.com/rss",
                status="error",
                saved_at=datetime(2025, 9, 27, 3, 0, tzinfo=timezone.utc),
                content_length=None,
            )

            item = record_to_rss_bucket(record)

            assert item.status is RssBucketStatus.error
            assert str(item.url) == "https://example.com/rss"

    class Test_create_rss_bucket_item:
        def test_create_rss_bucket_item_sets_defaults(self) -> None:
            """
            docs:
                目的:
                    create_rss_bucket_item がデフォルト設定を適用することを確認する。
                検証観点:
                    - status が registered になる。
                    - saved_at が timezone-aware になる。
            """

            item = create_rss_bucket_item(
                bucket_key="abc",
                rss_item=RssItem(
                    group="bbc",
                    name="top",
                    url="https://example.com/rss",
                ),
            )

            assert item.status is RssBucketStatus.registered
            assert item.saved_at.tzinfo is not None

        def test_create_rss_bucket_item_accepts_str_status(self) -> None:
            """
            docs:
                目的:
                    文字列ステータスを正規化できることを確認する。
                検証観点:
                    - "error" 指定で RssBucketStatus.error に変換される。
                    - naive datetime が UTC 付きに補正される。
            """

            naive_time = datetime(2025, 9, 27, 12, 0, 0)

            item = create_rss_bucket_item(
                bucket_key="def",
                rss_item=RssItem(
                    group="guardian",
                    name="world",
                    url="https://example.com/world",
                ),
                status="error",
                saved_at=naive_time,
            )

            assert item.status is RssBucketStatus.error
            assert item.saved_at.tzinfo is not None
            offset = item.saved_at.utcoffset()
            assert offset is not None
            assert offset.total_seconds() == 0
