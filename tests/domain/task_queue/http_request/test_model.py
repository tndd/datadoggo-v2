"""domain.task_queue.http_request.model のテスト"""

from datetime import datetime, timezone

import pytest
from pydantic import HttpUrl, ValidationError

from domain.task_queue.http_request.model import (
    SUCCESS_STATUS_CODE,
    HttpRequestTask,
    validate_group_format,
)

"""このモジュールのテストコレクション"""


def test_validate_group_format_accepts_valid_format() -> None:
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


def test_validate_group_format_rejects_invalid_format() -> None:
    """
    docs:
    目的:
        validate_group_format が不正な形式のgroupを拒否することを確認する。
    検証観点:
        - コロンなしの文字列を拒否する。
        - 空の要素を含む形式を拒否する。
        - コロンが2つ以上ある形式を拒否する。
    """


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


def test_validate_group_format_rejects_whitespace_edge_cases() -> None:
    """
    docs:
    目的:
        validate_group_format が空白を含む不正な形式を拒否することを確認する。
    検証観点:
        - 前後に空白を含む要素を拒否する（正規化は行わない）。
        - 空白のみの要素を拒否する。
    """

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


def test_is_success_and_backlog() -> None:
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


def test_http_request_task_raises_on_invalid_group() -> None:
    """
    docs:
    目的:
        HttpRequestTaskが不正なgroup値でインスタンス化された際に
        ValueErrorが発生することを確認する。
    検証観点:
        - 不正なgroup形式でValidationErrorが発生する。
        - エラーメッセージに例が含まれる。
    """

    base_time = datetime(2025, 9, 29, 0, 0, tzinfo=timezone.utc)
    url_value = HttpUrl("https://example.com/rss")

    # コロンなしの不正な形式
    try:
        HttpRequestTask(
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
        HttpRequestTask(
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
        HttpRequestTask(
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
