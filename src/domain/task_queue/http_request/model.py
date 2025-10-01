"""HttpRequestTaskドメインモデル群"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

SUCCESS_STATUS_CODE = 200


class HttpRequestTask(BaseModel):
    """http_request_queueテーブルの要素を表すドメインモデル"""

    id: str
    url: HttpUrl
    description: str | None
    group: str | None
    status_code: int | None = None
    created_at: datetime
    updated_at: datetime

    def is_success(self) -> bool:
        """成功通信を表す"""
        return self.status_code == SUCCESS_STATUS_CODE

    def is_backlog(self) -> bool:
        """通信未実行または通信失敗を表す"""
        return not self.is_success()


class HttpRequestTaskRecord(SQLModel, table=True):
    """SQLModelによるhttp_request_queueテーブル定義"""

    __tablename__: str = "http_request_queue"  # pyright: ignore[reportIncompatibleVariableOverride]

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    description: str | None = SQLField(default=None, nullable=True)
    group: str | None = SQLField(default=None, nullable=True)
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
                - 200 の場合 is_success が True、is_backlog が False。
                - 200 以外または None の場合 is_backlog が True、
                  is_success が False。
                - is_success と is_backlog が相互排他的。
                - group が nullable であることを確認する。
        """

        from datetime import datetime, timezone

        from pydantic import HttpUrl

        base_time = datetime(2025, 9, 29, 0, 0, tzinfo=timezone.utc)

        url_value = HttpUrl("https://example.com/rss")

        # status_code=200 の場合
        success = HttpRequestTask(
            id="abc",
            url=url_value,
            description="example",
            group="test:source",
            status_code=SUCCESS_STATUS_CODE,
            created_at=base_time,
            updated_at=base_time,
        )
        assert success.is_success()
        assert not success.is_backlog()

        # status_code=None の場合
        backlog_none = success.model_copy(update={"status_code": None})
        assert backlog_none.is_backlog()
        assert not backlog_none.is_success()

        # status_code=404 の場合
        backlog_error = success.model_copy(update={"status_code": 404})
        assert backlog_error.is_backlog()
        assert not backlog_error.is_success()

        # group が None でも生成可能
        no_group = HttpRequestTask(
            id="xyz",
            url=url_value,
            description="no group",
            group=None,
            status_code=SUCCESS_STATUS_CODE,
            created_at=base_time,
            updated_at=base_time,
        )
        assert no_group.group is None
