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
    status_code: int | None = None
    pub_date: datetime

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
