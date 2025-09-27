"""Feedドメインモデル群"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class FeedItem(BaseModel):
    """Feedテーブルの要素のドメイン表現"""

    id: str
    url: HttpUrl
    title: str
    status_code: int | None = None
    pub_date: datetime


class FeedRecord(SQLModel, table=True):
    """SQLModelによるFeedテーブル定義"""

    __tablename__: ClassVar[Any] = "feeds"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    title: str = SQLField(nullable=False)
    status_code: int | None = SQLField(default=None, nullable=True)
    pub_date: datetime = SQLField(nullable=False)
