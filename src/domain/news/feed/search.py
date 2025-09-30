"""Feedテーブルからの読み出し処理(CQRSのクエリ側)"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import select

from infra.storage.rds import session_scope

from .model import FeedItem, FeedRecord
from .service import record_to_feed


class FeedQuery(BaseModel):
    """Feed検索時の条件入力モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    title: str | None = None
    url: str | None = None
    status_code: int | None = None
    pub_date_from: datetime | None = None
    pub_date_to: datetime | None = None


def find_feed_by_id(feed_id: str) -> FeedItem | None:
    """IDでFeedを検索し、存在すれば返す"""

    with session_scope() as session:
        statement = select(FeedRecord).where(FeedRecord.id == feed_id)
        record = session.exec(statement).first()
        if record is None:
            return None

        return record_to_feed(record)


def search_feeds(query: FeedQuery) -> list[FeedItem]:
    """Feedをページングして取得する"""

    with session_scope() as session:
        statement = select(FeedRecord)

        if query.title:
            title_expr = cast(Any, FeedRecord.title)
            statement = statement.where(title_expr.contains(query.title))

        if query.url:
            statement = statement.where(FeedRecord.url == query.url)

        if query.status_code is not None:
            statement = statement.where(FeedRecord.status_code == query.status_code)

        if query.pub_date_from is not None:
            statement = statement.where(FeedRecord.pub_date >= query.pub_date_from)

        if query.pub_date_to is not None:
            statement = statement.where(FeedRecord.pub_date <= query.pub_date_to)

        statement = (
            statement.order_by(desc(cast(Any, FeedRecord.pub_date)))
            .offset(query.offset)
            .limit(query.limit)
        )
        records = session.exec(statement).all()
        return [record_to_feed(item) for item in records]


class TestMod:
    def test_find_feed_by_id_returns_item(self) -> None:
        """
        docs:
            目的:
                find_feed_by_id が既存レコードを取得できることを確認する。
            検証観点:
                - store_feed で保存したIDを指定すると FeedItem が返る。
                - 取得した FeedItem の属性が保存時と一致する。
                - created_at / updated_at が取得結果でも保持される。
        """

        from .command import store_feed
        from .service import create_feed

        # pytestにより自動的にインメモリDBが使用される
        feed = create_feed(
            url="https://example.com/find",
            title="Find Target",
            status_code=200,
            pub_date=datetime(2024, 2, 1, 8, 0, 0),
        )
        stored = store_feed(feed)

        fetched = find_feed_by_id(feed.id)
        assert fetched is not None
        assert fetched.id == feed.id
        assert fetched.title == "Find Target"
        assert fetched.created_at == stored.created_at
        assert fetched.updated_at == stored.updated_at

    def test_find_feed_by_id_returns_none_when_missing(self) -> None:
        """
        docs:
            目的:
                存在しないIDで find_feed_by_id を呼び出した際に
                None が返ることを確認する。
            検証観点:
                - 例外が発生しない。
                - 戻り値が None になる。
        """

        # pytestにより自動的にインメモリDBが使用される
        missing = find_feed_by_id("non-existent")
        assert missing is None

    def test_search_feeds_filters_and_order(self) -> None:
        """
        docs:
            目的:
                search_feeds が条件指定と並び替えを正しく行うことを確認する。
            検証観点:
                - 公開日時の降順で並ぶ。
                - limit/offset が期待どおり機能する。
                - title/status_code/pub_date範囲/url 条件で絞り込める。
        """

        from .command import store_feed
        from .service import create_feed

        # pytestにより自動的にインメモリDBが使用される
        feed_success = create_feed(
            url="https://example.com/success",
            title="Daily Success Report",
            status_code=200,
            pub_date=datetime(2024, 1, 10, 8, 0, 0),
        )
        feed_failure = create_feed(
            url="https://example.com/failure",
            title="Weekly Failure Recap",
            status_code=500,
            pub_date=datetime(2024, 1, 5, 8, 0, 0),
        )
        feed_other = create_feed(
            url="https://example.org/other",
            title="Daily Other News",
            status_code=200,
            pub_date=datetime(2024, 1, 12, 12, 0, 0),
        )

        for feed in (feed_success, feed_failure, feed_other):
            store_feed(feed)

        expected_count = 2
        result = search_feeds(FeedQuery(limit=expected_count, offset=0))
        assert len(result) == expected_count
        assert result[0].pub_date > result[1].pub_date

        title_filtered = search_feeds(FeedQuery(title="Daily", limit=10))
        assert {item.id for item in title_filtered} == {
            feed_success.id,
            feed_other.id,
        }

        status_filtered = search_feeds(FeedQuery(status_code=500, limit=10))
        assert [item.id for item in status_filtered] == [feed_failure.id]

        range_filtered = search_feeds(
            FeedQuery(
                pub_date_from=datetime(2024, 1, 6, 0, 0, 0),
                pub_date_to=datetime(2024, 1, 11, 23, 59, 59),
                limit=10,
            )
        )
        assert [item.id for item in range_filtered] == [feed_success.id]

        url_filtered = search_feeds(
            FeedQuery(url="https://example.org/other", limit=10)
        )
        assert [item.id for item in url_filtered] == [feed_other.id]
