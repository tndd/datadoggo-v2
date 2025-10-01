"""Articleドメインのデータモデル群"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl


class ArticleFetchStatus(str, Enum):
    """記事取得の保存状況"""

    SAVED = "saved"
    FETCH_FAILED = "fetch_failed"


class Article(BaseModel):
    """メタデータとコンテンツを結合したビュー

    Attributes:
        created_at: 記事の公開日時(UTC)。HttpRequestTaskのcreated_atを継承。
        updated_at: 記事HTMLの取得日時(UTC)。fetch時の現在時刻が設定される。
    """

    id: str
    url: HttpUrl
    content: str  # 記事のHTMLコンテンツ
    group: str | None  # グループ名
    created_at: datetime  # 記事の公開日時(UTC)
    updated_at: datetime  # 記事HTMLの取得日時(UTC)
    description: str | None  # 説明。記事のタイトルや注釈など


