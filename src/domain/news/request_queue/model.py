"""Feedドメインモデル群"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

SUCCESS_STATUS_CODE = 200


class HttpRequest(BaseModel):
    """HttpRequestテーブルの要素のドメイン表現"""

    id: str
    url: HttpUrl
    description: str | None
    group: str
    status_code: int | None = None
    created_at: datetime
    updated_at: datetime

    def is_success(self) -> bool:
        """成功通信を表す"""
        return self.status_code == SUCCESS_STATUS_CODE

    def is_backlog(self) -> bool:
        """通信未実行または通信失敗を表す"""
        return self.status_code is not SUCCESS_STATUS_CODE


class HttpRequestRecord(SQLModel, table=True):
    """SQLModelによるHttpRequestテーブル定義"""

    __tablename__: ClassVar[Any] = "http_request_queue"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    description: str | None = SQLField(default=None, nullable=True)
    group: str = SQLField(nullable=False)
    status_code: int | None = SQLField(default=None, nullable=True)
    created_at: datetime = SQLField(nullable=False)
    updated_at: datetime = SQLField(nullable=False)


class TestMod:
    """このモジュールのテストコレクション"""

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

        success = HttpRequest(
            id="abc",
            url=url_value,
            description="example",
            group="test:source",
            status_code=SUCCESS_STATUS_CODE,
            created_at=base_time,
            updated_at=base_time,
        )
        assert success.is_success()

        backlog = success.model_copy(update={"status_code": None})
        assert backlog.is_backlog()
