"""Feedドメインモデル群"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

SUCCESS_STATUS_CODE = 200


class FeedItem(BaseModel):
    """Feedテーブルの要素のドメイン表現"""

    id: str
    url: HttpUrl
    title: str
    pub_date: datetime
    status_code: int | None = None
    created_at: datetime
    updated_at: datetime

    def is_success(self) -> bool:
        """成功通信を表す"""
        return self.status_code == SUCCESS_STATUS_CODE

    def is_backlog(self) -> bool:
        """通信未実行または通信失敗を表す"""
        return self.status_code is not SUCCESS_STATUS_CODE


class FeedRecord(SQLModel, table=True):
    """SQLModelによるFeedテーブル定義"""

    __tablename__: ClassVar[Any] = "feed_item"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    title: str = SQLField(nullable=False)
    status_code: int | None = SQLField(default=None, nullable=True)
    pub_date: datetime = SQLField(nullable=False)
    created_at: datetime = SQLField(nullable=False)
    updated_at: datetime = SQLField(nullable=False)


class Tests:
    class Test_FeedItem:
        def test_is_success_and_backlog(self) -> None:
            """
            docs:
                目的:
                    ステータスコードに応じた成功/失敗判定を確認する。
                検証観点:
                    - 200 の場合 is_success が True。
                    - 200 以外または None の場合 is_backlog が True。
            """

            from datetime import datetime, timezone

            base_time = datetime(2025, 9, 29, 0, 0, tzinfo=timezone.utc)

            from typing import cast

            from pydantic import HttpUrl

            url_value = cast(HttpUrl, "https://example.com/rss")

            success = FeedItem(
                id="abc",
                url=url_value,
                title="example",
                pub_date=base_time,
                status_code=SUCCESS_STATUS_CODE,
                created_at=base_time,
                updated_at=base_time,
            )
            assert success.is_success()

            backlog = success.model_copy(update={"status_code": None})
            assert backlog.is_backlog()
