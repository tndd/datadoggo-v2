"""Feedテーブルのドメインモデルと永続化操作を提供する"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl
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


class _FeedRecord(SQLModel, table=True):
    """SQLModelによるFeedテーブル定義"""

    __tablename__ = "feeds"

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
        url=url,
        title=title,
        status_code=status_code,
        pub_date=pub_date,
    )


def store_feed(feed: Feed) -> Feed:
    """Feedを保存し、保存後の状態を返す"""

    _ensure_initialized()
    return _save_feed(feed)


def find_feed_by_id(feed_id: str) -> Optional[Feed]:
    """IDでFeedを検索し、存在すれば返す"""

    _ensure_initialized()
    return _load_feed_by_id(feed_id)


def search_feeds(query: FeedQuery) -> list[Feed]:
    """Feedをページングして取得する"""

    _ensure_initialized()
    return _load_feeds(limit=query.limit, offset=query.offset)


def _ensure_initialized() -> None:
    initialize_database()


def _save_feed(feed: Feed) -> Feed:
    with session_scope() as session:
        record = _feed_to_record(feed)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return _record_to_domain(merged)


def _load_feed_by_id(feed_id: str) -> Optional[Feed]:
    with session_scope() as session:
        statement = select(_FeedRecord).where(_FeedRecord.id == feed_id)
        result = session.exec(statement).first()
        if result is None:
            return None

        return _record_to_domain(result)


def _load_feeds(*, limit: int, offset: int) -> list[Feed]:
    with session_scope() as session:
        statement = (
            select(_FeedRecord)
            .order_by(_FeedRecord.pub_date.desc())
            .offset(offset)
            .limit(limit)
        )
        records = session.exec(statement).all()
        return [_record_to_domain(item) for item in records]


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
        url=record.url,
        title=record.title,
        status_code=record.status_code,
        pub_date=record.pub_date,
    )


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

        db_path = tmp_path / "feed.db"
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

        db_path = tmp_path / "feed_search.db"
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

        db_path = tmp_path / "feed_missing.db"
        os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

        missing = find_feed_by_id("non-existent")
        assert missing is None

        os.environ.pop("FEED_DATABASE_URL", None)
