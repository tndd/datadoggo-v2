# rssをbucketから読み込む

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast
from xml.etree.ElementTree import Element

from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import select

from infra.storage.bucket import (
    DEFAULT_STORAGE_ROOT,
    load_object,
    save_object,
    search_object_keys,
)
from infra.storage.rds import initialize_database, session_scope

from .convert import record_to_rss_bucket
from .model import RssBucketItem, RssBucketRecord, RssBucketStatus


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

    class find_rss_bucket_by_id:
        def test_find_rss_bucket_by_id_returns_item(self, tmp_path) -> None:
            """
            docs:
                目的:
                    find_rss_bucket_by_id が保存済みレコードを取得できることを確認する。
                検証観点:
                    - 保存した ID を指定すると戻り値が得られる。
                    - 取得したドメインモデルの属性が一致する。
            """

            import os

            from .command import store_rss_bucket_payload
            from .load import RssItem

            element = Element("rss")
            rss_item = RssItem(
                group="bbc",
                name="world",
                url="https://example.com/world",
            )

            storage_root = tmp_path / "bucket"
            db_path = tmp_path / "rss_bucket_find.db"
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

            try:
                stored = store_rss_bucket_payload(
                    rss_item,
                    element,
                    storage_root=storage_root,
                )

                fetched = find_rss_bucket_by_id(stored.id)
                assert fetched is not None
                assert fetched.id == stored.id
                assert fetched.group == "bbc"
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

        def test_find_rss_bucket_by_id_returns_none(self, tmp_path) -> None:
            """
            docs:
                目的:
                    未登録IDで None が返ることを確認する。
                検証観点:
                    - 例外が発生しない。
                    - 戻り値が None である。
            """

            import os

            db_path = tmp_path / "rss_bucket_missing.db"
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

            try:
                missing = find_rss_bucket_by_id("unknown")
                assert missing is None
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

    class search_rss_buckets:
        def test_search_rss_buckets_filters_and_orders(self, tmp_path) -> None:
            """
            docs:
                目的:
                    search_rss_buckets が条件指定と順序付けを正しく扱うことを確認する。
                検証観点:
                    - group/name/status で絞り込める。
                    - saved_at 降順で並び、limit/offset が機能する。
            """

            import os

            from .command import store_rss_bucket_payload
            from .load import RssItem

            def make_element(url: str) -> Element:
                element = Element("rss")
                element.text = url
                return element

            storage_root = tmp_path / "bucket"
            db_path = tmp_path / "rss_bucket_search.db"
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

            try:
                items = [
                    RssItem(group="bbc", name="top", url="https://example.com/top"),
                    RssItem(group="bbc", name="world", url="https://example.com/world"),
                    RssItem(
                        group="guardian",
                        name="world",
                        url="https://example.com/guardian",
                    ),
                ]

                stored_records: list[RssBucketItem] = []
                for rss_item in items:
                    stored_records.append(
                        store_rss_bucket_payload(
                            rss_item,
                            make_element(rss_item.url),
                            storage_root=storage_root,
                        )
                    )

                expected_count = 2
                query = RssBucketQuery(limit=expected_count, offset=0)
                results = search_rss_buckets(query)
                assert len(results) == expected_count
                assert results[0].saved_at >= results[1].saved_at

                group_filtered = search_rss_buckets(
                    RssBucketQuery(group="guardian", limit=5)
                )
                assert [item.group for item in group_filtered] == ["guardian"]

                status_filtered = search_rss_buckets(
                    RssBucketQuery(status=RssBucketStatus.registered, limit=10)
                )
                assert len(status_filtered) == len(stored_records)

                offset_filtered = search_rss_buckets(RssBucketQuery(limit=1, offset=1))
                assert len(offset_filtered) == 1
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)


class RssBucketQuery(BaseModel):
    """RSSバケット検索条件モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    group: str | None = None
    name: str | None = None
    status: RssBucketStatus | None = None
    saved_at_from: datetime | None = None
    saved_at_to: datetime | None = None


def find_rss_bucket_by_id(bucket_id: str) -> RssBucketItem | None:
    """IDでRSSバケットエントリを検索する"""

    initialize_database()
    with session_scope() as session:
        statement = select(RssBucketRecord).where(RssBucketRecord.id == bucket_id)
        record = session.exec(statement).first()
        if record is None:
            return None

        return record_to_rss_bucket(record)


def search_rss_buckets(query: RssBucketQuery) -> list[RssBucketItem]:
    """RSSバケットエントリを検索する"""

    initialize_database()
    with session_scope() as session:
        statement = select(RssBucketRecord)

        if query.group:
            statement = statement.where(RssBucketRecord.group == query.group)

        if query.name:
            statement = statement.where(RssBucketRecord.name == query.name)

        if query.status is not None:
            statement = statement.where(RssBucketRecord.status == query.status.value)

        if query.saved_at_from is not None:
            statement = statement.where(RssBucketRecord.saved_at >= query.saved_at_from)

        if query.saved_at_to is not None:
            statement = statement.where(RssBucketRecord.saved_at <= query.saved_at_to)

        statement = (
            statement.order_by(desc(cast(Any, RssBucketRecord.saved_at)))
            .offset(query.offset)
            .limit(query.limit)
        )

        records = session.exec(statement).all()
        return [record_to_rss_bucket(record) for record in records]
