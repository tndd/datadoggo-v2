"""Feedテーブルへの書き込み処理(CQRSのコマンド側)"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from infra.storage.rds import session_scope

from ..common import ensure_saved_at
from .model import FeedItem, FeedRecord
from .service import create_feed, feed_to_record, record_to_feed


def store_feed(feed: FeedItem) -> FeedItem:
    """Feedを保存し、保存後の状態を返す"""

    with session_scope() as session:
        normalized = feed.model_copy(update={"updated_at": ensure_saved_at()})
        record = feed_to_record(normalized)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return record_to_feed(merged)


class Tests:
    def test_store_feed_persists_record(self) -> None:
        """
        docs:
            目的:
                store_feed が永続化を行い、戻り値として最新状態の
                FeedItem を返すことを確認する。
            検証観点:
                - create_feed で生成した FeedItem が store_feed で保存される。
                - 保存後に同一IDのレコードがDB上に存在する。
                - created_at が保持され、updated_at が更新される。
        """

        # pytestにより自動的にインメモリDBが使用される
        origin_time = datetime(2024, 1, 1, 9, 0, 0)
        feed = create_feed(
            url="https://example.com/store",
            title="Store Feed",
            status_code=201,
            pub_date=origin_time,
            created_at=datetime(2024, 1, 1, 9, 0, 0),
        )

        stored = store_feed(feed)
        assert stored.id == feed.id
        assert stored.status_code == feed.status_code
        assert stored.created_at == ensure_saved_at(datetime(2024, 1, 1, 9, 0, 0))
        assert stored.updated_at >= stored.created_at

        with session_scope() as session:
            statement = select(FeedRecord).where(FeedRecord.id == feed.id)
            record = session.exec(statement).first()
            assert record is not None
            assert record.title == "Store Feed"
            assert ensure_saved_at(record.created_at) == stored.created_at
            assert ensure_saved_at(record.updated_at) == stored.updated_at
