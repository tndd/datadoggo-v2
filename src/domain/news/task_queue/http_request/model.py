"""RequestTaskドメインモデル群"""

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


class RequestTask(BaseModel):
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


class RequestTaskRecord(SQLModel, table=True):
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

    def test_validate_group_format_accepts_valid_format(self) -> None:
        """
        docs:
            目的:
                validate_group_format が正しい形式のgroupを受け入れることを確認する。
            検証観点:
                - "{source}:{category}" 形式を受け入れる。
                - None を受け入れる。
        """

        assert validate_group_format("bbc:world") == "bbc:world"
        assert validate_group_format("test:success") == "test:success"
        assert validate_group_format(None) is None

    def test_validate_group_format_rejects_invalid_format(self) -> None:
        """
        docs:
            目的:
                validate_group_format が不正な形式のgroupを拒否することを確認する。
            検証観点:
                - コロンなしの文字列を拒否する。
                - 空の要素を含む形式を拒否する。
                - コロンが2つ以上ある形式を拒否する。
        """

        import pytest

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format("invalid")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format(":")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format("test:")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format(":category")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format("a:b:c")

    def test_validate_group_format_rejects_whitespace_edge_cases(self) -> None:
        """
        docs:
            目的:
                validate_group_format が空白を含む不正な形式を拒否することを確認する。
            検証観点:
                - 前後に空白を含む要素を拒否する（正規化は行わない）。
                - 空白のみの要素を拒否する。
        """

        import pytest

        # 前後に空白を含む場合は拒否
        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format(" bbc:world")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format("bbc:world ")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format(" bbc : world ")

        # 空白のみの要素
        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format(" :world")

        with pytest.raises(ValueError, match="source.*category"):
            validate_group_format("bbc: ")

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
        success = RequestTask(
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
        no_group = RequestTask(
            id="xyz",
            url=url_value,
            description="no group",
            group=None,
            status_code=SUCCESS_STATUS_CODE,
            created_at=base_time,
            updated_at=base_time,
        )
        assert no_group.group is None

    def test_http_request_task_raises_on_invalid_group(self) -> None:
        """
        docs:
            目的:
                RequestTaskが不正なgroup値でインスタンス化された際に
                ValueErrorが発生することを確認する。
            検証観点:
                - 不正なgroup形式でValidationErrorが発生する。
                - エラーメッセージに例が含まれる。
        """

        from datetime import datetime, timezone

        from pydantic import HttpUrl, ValidationError

        base_time = datetime(2025, 9, 29, 0, 0, tzinfo=timezone.utc)
        url_value = HttpUrl("https://example.com/rss")

        # コロンなしの不正な形式
        try:
            RequestTask(
                id="invalid1",
                url=url_value,
                description="invalid",
                group="invalid_format",
                status_code=SUCCESS_STATUS_CODE,
                created_at=base_time,
                updated_at=base_time,
            )
            raise AssertionError("ValidationErrorが発生しませんでした")
        except ValidationError as error:
            error_msg = str(error)
            assert "source" in error_msg
            assert "category" in error_msg
            assert "bbc:world" in error_msg  # 例が含まれることを確認

        # 空の要素を含む形式
        try:
            RequestTask(
                id="invalid2",
                url=url_value,
                description="invalid",
                group="test:",
                status_code=SUCCESS_STATUS_CODE,
                created_at=base_time,
                updated_at=base_time,
            )
            raise AssertionError("ValidationErrorが発生しませんでした")
        except ValidationError:
            pass  # 期待通り

        # 前後に空白を含む形式
        try:
            RequestTask(
                id="invalid3",
                url=url_value,
                description="invalid",
                group=" test:category ",
                status_code=SUCCESS_STATUS_CODE,
                created_at=base_time,
                updated_at=base_time,
            )
            raise AssertionError("ValidationErrorが発生しませんでした")
        except ValidationError:
            pass  # 期待通り
