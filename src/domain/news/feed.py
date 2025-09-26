"""Feedテーブルのドメインモデルと永続化操作を提供する"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Optional, cast

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter
from sqlalchemy import desc
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select

from infra.compute import hash_text_sha256
from infra.storage.rds import initialize_database, session_scope


class Feed(BaseModel):
    """Feedテーブルのドメイン表現"""

    id: str
    url: HttpUrl
    title: str
    status_code: int
    pub_date: datetime


class FeedQuery(BaseModel):
    """Feed検索時の条件を表現する入力モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    title: str | None = None
    url: str | None = None
    status_code: int | None = None
    pub_date_from: datetime | None = None
    pub_date_to: datetime | None = None


HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


class _FeedRecord(SQLModel, table=True):
    """SQLModelによるFeedテーブル定義"""

    __tablename__: ClassVar[Any] = "feeds"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    title: str = SQLField(nullable=False)
    status_code: int = SQLField(nullable=False)
    pub_date: datetime = SQLField(nullable=False)


def create_feed(url: str, title: str, status_code: int, pub_date: datetime) -> Feed:
    """URLなどの入力からFeedモデルを生成する。IDはURLのSHA256ハッシュ"""

    feed_id = hash_text_sha256(url)
    return Feed(
        id=feed_id,
        url=_ensure_http_url(url),
        title=title,
        status_code=status_code,
        pub_date=pub_date,
    )


def store_feed(feed: Feed) -> Feed:
    """
    Feedを保存し、保存後の状態を返す
    再実行すると結果は上書きされる
    """

    _ensure_initialized()
    with session_scope() as session:
        record = _feed_to_record(feed)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return _record_to_domain(merged)


def find_feed_by_id(feed_id: str) -> Optional[Feed]:
    """IDでFeedを検索し、存在すれば返す"""

    _ensure_initialized()
    with session_scope() as session:
        statement = select(_FeedRecord).where(_FeedRecord.id == feed_id)
        record = session.exec(statement).first()
        if record is None:
            return None

        return _record_to_domain(record)


def search_feeds(query: FeedQuery) -> list[Feed]:
    """Feedをページングして取得する"""

    _ensure_initialized()
    with session_scope() as session:
        statement = select(_FeedRecord)

        if query.title:
            title_expr = cast(Any, _FeedRecord.title)
            statement = statement.where(title_expr.contains(query.title))

        if query.url:
            statement = statement.where(_FeedRecord.url == query.url)

        if query.status_code is not None:
            statement = statement.where(_FeedRecord.status_code == query.status_code)

        if query.pub_date_from is not None:
            statement = statement.where(_FeedRecord.pub_date >= query.pub_date_from)

        if query.pub_date_to is not None:
            statement = statement.where(_FeedRecord.pub_date <= query.pub_date_to)

        statement = (
            statement.order_by(desc(cast(Any, _FeedRecord.pub_date)))
            .offset(query.offset)
            .limit(query.limit)
        )
        records = session.exec(statement).all()
        return [_record_to_domain(item) for item in records]


def _ensure_initialized() -> None:
    initialize_database()


def _feed_to_record(feed: Feed) -> _FeedRecord:
    return _FeedRecord(
        id=feed.id,
        url=str(feed.url),
        title=feed.title,
        status_code=feed.status_code,
        pub_date=feed.pub_date,
    )


def _record_to_domain(record: _FeedRecord) -> Feed:
    return Feed(
        id=record.id,
        url=_ensure_http_url(record.url),
        title=record.title,
        status_code=record.status_code,
        pub_date=record.pub_date,
    )


def _ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列を含むURL入力をHttpUrlとして検証する"""

    return HTTP_URL_ADAPTER.validate_python(value)


class Tests:
    def test_store_feed_and_find_feed_by_id(self, tmp_path) -> None:
        """
        docs:
            目的:
                store_feed で保存したレコードが
                find_feed_by_id で取得できることを確認する。
            検証観点:
                - 同一URLから生成されたIDで取得できる。
                - status_code や pub_date などの属性が保持される。
        """

        db_path = tmp_path / "datadoggo.db"
        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

        feed = create_feed(
            url="https://example.com/feed.xml",
            title="Example Feed",
            status_code=200,
            pub_date=datetime(2024, 1, 1, 0, 0, 0),
        )

        stored = store_feed(feed)
        assert stored.id == feed.id

        fetched = find_feed_by_id(feed.id)
        assert fetched is not None
        assert fetched.id == feed.id
        expected_status = 200
        assert fetched.status_code == expected_status
        assert fetched.pub_date == datetime(2024, 1, 1, 0, 0, 0)

        os.environ.pop("FEED_DATABASE_URL", None)

    def test_search_feeds_returns_descending_order(self, tmp_path) -> None:
        """
        docs:
            目的:
                search_feeds が公開日時の降順でFeedを返すことを確認する。
            検証観点:
                - pub_date が新しい順に並ぶ。
                - limit/offset が機能する。
        """

        db_path = tmp_path / "datadoggo.db"
        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

        feeds = [
            create_feed(
                url=f"https://example.com/feed/{idx}",
                title=f"Feed {idx}",
                status_code=200,
                pub_date=datetime(2024, 1, idx + 1, 9, 0, 0),
            )
            for idx in range(3)
        ]

        for feed in feeds:
            store_feed(feed)

        result = search_feeds(FeedQuery(limit=2, offset=0))
        expected_count = 2
        assert len(result) == expected_count
        assert result[0].pub_date > result[1].pub_date

        os.environ.pop("FEED_DATABASE_URL", None)

    def test_search_feeds_filters_conditions(self, tmp_path) -> None:
        """
        docs:
            目的:
                search_feeds が複数条件(title/url/status_code/pub_date範囲)で
                絞り込みできることを確認する。
            検証観点:
                - title の部分一致で複数件がヒットする。
                - status_code 一致で特定のレコードだけ返る。
                - pub_date の範囲指定で対象が限定される。
                - url の完全一致で1件に絞り込める。
        """

        db_path = tmp_path / "datadoggo.db"
        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

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

        # title filter (部分一致)
        title_filtered = search_feeds(FeedQuery(title="Daily", limit=10))
        assert {item.id for item in title_filtered} == {
            feed_success.id,
            feed_other.id,
        }

        # status_code filter
        status_filtered = search_feeds(FeedQuery(status_code=500, limit=10))
        assert [item.id for item in status_filtered] == [feed_failure.id]

        # pub_date range filter
        range_filtered = search_feeds(
            FeedQuery(
                pub_date_from=datetime(2024, 1, 6, 0, 0, 0),
                pub_date_to=datetime(2024, 1, 11, 23, 59, 59),
                limit=10,
            )
        )
        assert [item.id for item in range_filtered] == [feed_success.id]

        # url filter (完全一致)
        url_filtered = search_feeds(
            FeedQuery(url="https://example.org/other", limit=10)
        )
        assert [item.id for item in url_filtered] == [feed_other.id]

        os.environ.pop("FEED_DATABASE_URL", None)

    def test_store_feed_creates_database_directory(self) -> None:
        """
        docs:
            目的:
                SQLiteファイル保存時に親ディレクトリが自動生成されるか確認する。
            検証観点:
                - 未作成のディレクトリでも store_feed が成功する。
                - 処理後にディレクトリとファイルが存在する。
        """

        target_dir = Path("tmp-feed-storage")
        target_db = target_dir / "test.db"
        if target_dir.exists():
            shutil.rmtree(target_dir)

        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{target_db}"

        try:
            feed = create_feed(
                url="https://example.com/new",
                title="New Entry",
                status_code=200,
                pub_date=datetime(2024, 1, 15, 9, 0, 0),
            )
            store_feed(feed)

            assert target_dir.exists()
            assert target_db.exists()
        finally:
            os.environ.pop("FEED_DATABASE_URL", None)
            if target_dir.exists():
                shutil.rmtree(target_dir)

    def test_find_feed_by_id_returns_none_when_missing(self, tmp_path) -> None:
        """
        docs:
            目的:
                存在しないIDで find_feed_by_id を呼び出した場合に
                None が返ることを確認する。
            検証観点:
                - 例外が発生しない。
                - None が返る。
        """

        db_path = tmp_path / "datadoggo.db"
        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

        missing = find_feed_by_id("non-existent")
        assert missing is None

        os.environ.pop("FEED_DATABASE_URL", None)
