"""RSSバケットメタデータのドメイン／永続化モデル"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class RssBucketStatus(StrEnum):
    """RSSバケットエントリの状態"""

    pending = "pending"
    registered = "registered"
    overridden = "overridden"
    error = "error"


class RssBucketItem(BaseModel):
    """RSSバケットに保存された要素のドメイン表現"""

    model_config = ConfigDict(frozen=True)

    id: str
    group: str
    name: str
    url: HttpUrl
    status: RssBucketStatus = Field(default=RssBucketStatus.pending)
    saved_at: datetime
    content_length: int | None = None

    def is_registered(self) -> bool:
        """登録済み状態かを判定する"""

        return self.status is RssBucketStatus.registered

    def is_error(self) -> bool:
        """エラー状態かを判定する"""

        return self.status is RssBucketStatus.error


class RssBucketRecord(SQLModel, table=True):
    """SQLModel による rss_bucket テーブル定義"""

    __tablename__: ClassVar[Any] = "rss_bucket"

    id: str = SQLField(primary_key=True, index=True)
    group: str = SQLField(nullable=False, index=True)
    name: str = SQLField(nullable=False, index=True)
    url: str = SQLField(nullable=False)
    status: str = SQLField(nullable=False, index=True)
    saved_at: datetime = SQLField(nullable=False)
    content_length: int | None = SQLField(default=None, nullable=True)


class Tests:
    class RssBucketItemModel:
        def test_rss_bucket_item_accepts_status_enum(self) -> None:
            """
            docs:
                目的:
                    RssBucketItem が StrEnum ステータスを保持できることを確認する。
                検証観点:
                    - registered 状態で is_registered が True を返す。
                    - error 状態で is_error が True を返す。
            """

            saved_at = datetime.fromisoformat("2025-09-27T12:00:00+00:00")

            from typing import cast

            from pydantic import HttpUrl

            item = RssBucketItem(
                id="abc",
                group="bbc",
                name="top",
                url=cast(HttpUrl, "https://example.com/rss"),
                status=RssBucketStatus.registered,
                saved_at=saved_at,
            )

            assert item.is_registered()

            error_item = item.model_copy(update={"status": RssBucketStatus.error})
            assert error_item.is_error()
