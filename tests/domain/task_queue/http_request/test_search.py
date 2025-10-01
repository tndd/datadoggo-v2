"""domain.task_queue.http_request.search のテスト"""

from datetime import datetime

from domain.task_queue.http_request.command import store_http_request
from domain.task_queue.http_request.model import HttpRequestTaskRecord
from domain.task_queue.http_request.search import (
    HttpRequestQuery,
    find_http_request_by_id,
    search_http_requests,
)
from domain.task_queue.http_request.service import create_http_request


def test_find_http_request_by_id_returns_item() -> None:
    """
    docs:
        目的:
            find_http_request_by_id が既存レコードを取得できることを確認する。
        検証観点:
            - store_http_request で保存したIDを指定すると HttpRequestTask が返る。
            - 取得した HttpRequestTask の属性が保存時と一致する。
            - created_at / updated_at が取得結果でも保持される。
    """

    # pytestにより自動的にインメモリDBが使用される
    request = create_http_request(
        url="https://example.com/find",
        description="Find Target",
        group="test:find",
        status_code=200,
        created_at=datetime(2024, 2, 1, 8, 0, 0),
    )
    stored = store_http_request(request)

    fetched = find_http_request_by_id(request.id)
    assert fetched is not None
    assert fetched.id == request.id
    assert fetched.description == "Find Target"
    assert fetched.created_at == stored.created_at
    assert fetched.updated_at == stored.updated_at


def test_find_http_request_by_id_returns_none_when_missing() -> None:
    """
    docs:
        目的:
            存在しないIDで find_http_request_by_id を呼び出した際に
            None が返ることを確認する。
        検証観点:
            - 例外が発生しない。
            - 戻り値が None になる。
    """

    # pytestにより自動的にインメモリDBが使用される
    missing = find_http_request_by_id("non-existent")
    assert missing is None


def test_search_http_requests_filters_and_order() -> None:
    """
    docs:
        目的:
            search_http_requests が条件指定と並び替えを正しく行うことを確認する。
        検証観点:
            - created_atの降順で並ぶ。
            - limit/offset が期待どおり機能する。
            - description/status_code/created_at範囲/url/group 条件で絞り込める。
    """

    # pytestにより自動的にインメモリDBが使用される
    request_success = create_http_request(
        url="https://example.com/success",
        description="Daily Success Report",
        group="test:success",
        status_code=200,
        created_at=datetime(2024, 1, 10, 8, 0, 0),
    )
    request_failure = create_http_request(
        url="https://example.com/failure",
        description="Weekly Failure Recap",
        group="test:failure",
        status_code=500,
        created_at=datetime(2024, 1, 5, 8, 0, 0),
    )
    request_other = create_http_request(
        url="https://example.org/other",
        description="Daily Other News",
        group="other:news",
        status_code=200,
        created_at=datetime(2024, 1, 12, 12, 0, 0),
    )

    for req in (request_success, request_failure, request_other):
        store_http_request(req)

    expected_count = 2
    result = search_http_requests(HttpRequestQuery(limit=expected_count, offset=0))
    assert len(result) == expected_count
    assert result[0].created_at > result[1].created_at

    description_filtered = search_http_requests(
        HttpRequestQuery(description="Daily", limit=10)
    )
    assert {item.id for item in description_filtered} == {
        request_success.id,
        request_other.id,
    }

    status_filtered = search_http_requests(
        HttpRequestQuery(status_code=500, limit=10)
    )
    assert [item.id for item in status_filtered] == [request_failure.id]

    range_filtered = search_http_requests(
        HttpRequestQuery(
            created_at_from=datetime(2024, 1, 6, 0, 0, 0),
            created_at_to=datetime(2024, 1, 11, 23, 59, 59),
            limit=10,
        )
    )
    assert [item.id for item in range_filtered] == [request_success.id]

    url_filtered = search_http_requests(
        HttpRequestQuery(url="https://example.org/other", limit=10)
    )
    assert [item.id for item in url_filtered] == [request_other.id]

    group_filtered = search_http_requests(HttpRequestQuery(group="test", limit=10))
    assert {item.id for item in group_filtered} == {
        request_success.id,
        request_failure.id,
    }
