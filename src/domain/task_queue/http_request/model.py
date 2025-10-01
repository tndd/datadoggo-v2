"""HttpRequestTaskドメインモデル群"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

SUCCESS_STATUS_CODE = 200
_EXPECTED_GROUP_PARTS = 2


def validate_group_format(value: str | None) -> str | None:
    """groupフィールドの形式を検証する

    形式: "{source}:{category}" (例: "bbc:world")
    注意: 前後の空白や空の要素は不正として扱う。正規化は行わない。

    Args:
        value: 検証対象のgroup値

    Returns:
        検証済みのgroup値

    Raises:
        ValueError: groupが"{source}:{category}"形式でない場合
    """
    if value is None:
        return None

    error_msg = (
        f"groupは'{{source}}:{{category}}'形式である必要があります "
        f"(例: 'bbc:world'): {value}"
    )

    # 前後の空白を検出（正規化は行わない）
    if value != value.strip():
        raise ValueError(error_msg)

    if ":" not in value:
        raise ValueError(error_msg)

    parts = value.split(":")
    if len(parts) != _EXPECTED_GROUP_PARTS:
        raise ValueError(error_msg)

    # 各要素が空でなく、前後に空白がないことを確認
    if not all(part and part == part.strip() for part in parts):
        raise ValueError(error_msg)

    return value


class HttpRequestTask(BaseModel):
    """http_request_queueテーブルの要素を表すドメインモデル

    Attributes:
        group: RSS配信元のグループ識別子。
               形式は "{source}:{category}" (例: "bbc:world")。
               RSS以外から生成された場合や分類不能な場合はNoneも許容。
    """

    id: str
    url: HttpUrl
    description: str | None
    group: str | None
    status_code: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("group")
    @classmethod
    def _validate_group(cls, value: str | None) -> str | None:
        """groupフィールドの形式を検証"""
        return validate_group_format(value)

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
