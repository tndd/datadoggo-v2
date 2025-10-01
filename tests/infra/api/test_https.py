"""infra.api.https のテスト"""

import pytest

from infra.api.https import HTTP_STATUS_OK, HttpsClient, RecordingFetcher


def test_get_uses_injected_fetcher() -> None:
    """
    docs:
        目的:
            GET の呼び出しがモックフェッチャー経由で実行されることを確認する。
        検証観点:
            - HTTPメソッドやURL、ヘッダーが記録される。
            - text() が適切なエンコーディングでデコードする。
    """

    fetcher = RecordingFetcher(
        response_text="こんにちは",
        encoding="shift_jis",
        headers={"Content-Type": "text/plain; charset=shift_jis"},
    )
    client = HttpsClient(fetcher=fetcher, default_timeout=1.0)

    response = client.get("https://example.com/feed")

    assert response.status_code == fetcher.status_code
    assert response.text() == "こんにちは"
    assert fetcher.calls == [
        (
            "GET",
            "https://example.com/feed",
            {},
            None,
            1.0,
        )
    ]


def test_post_encodes_form_mapping() -> None:
    """
    docs:
        目的:
            POSTで辞書データを送信するとapplication/x-www-form-urlencodedでエンコードされることを確認する。
        検証観点:
            - dataがbytesに変換される。
            - Content-Typeヘッダーが自動付与される。
    """

    fetcher = RecordingFetcher(response_text="ok")
    client = HttpsClient(fetcher=fetcher)

    response = client.post(
        "https://example.com/form",
        data={"q": "python", "page": "1"},
    )

    assert response.text() == "ok"
    method, url, headers, body, _timeout = fetcher.calls[0]
    assert method == "POST"
    assert url == "https://example.com/form"
    assert body == b"q=python&page=1"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_post_respects_bytes_payload() -> None:
    """
    docs:
        目的:
            POSTにバイナリデータを渡した場合にそのまま送信されることを確認する。
        検証観点:
            - dataが変換されない。
            - Content-Typeは自動付与されない。
    """

    fetcher = RecordingFetcher(response_text="done")
    client = HttpsClient(fetcher=fetcher)

    payload = b'{"key": "value"}'
    response = client.post(
        "https://example.com/json",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    _, _, headers, body, _ = fetcher.calls[0]
    assert body == payload
    assert headers["Content-Type"] == "application/json"
    assert response.text() == "done"


def test_clone_creates_equivalent_client() -> None:
    """
    docs:
        目的:
            clone が同一設定の新しいクライアントを生成することを確認する。
        検証観点:
            - 取得先URLごとに同じフェッチャーが呼び出される。
            - タイムアウト設定が複製される。
    """

    fetcher = RecordingFetcher(
        response_text="ok",
        encoding="utf-8",
    )
    client = HttpsClient(fetcher=fetcher, default_timeout=2.5)

    clone = client.clone()

    assert clone is not client

    client.get("https://example.com/a")
    clone.get("https://example.com/b")

    assert fetcher.calls == [
        (
            "GET",
            "https://example.com/a",
            {},
            None,
            2.5,
        ),
        (
            "GET",
            "https://example.com/b",
            {},
            None,
            2.5,
        ),
    ]


def test_request_raises_runtime_error_on_fetch_failure() -> None:
    """
    docs:
        目的:
            フェッチャーがURLErrorを送出した場合にRuntimeErrorへラップされることを確認する。
        検証観点:
            - RecordingFetcher.raise_error=TrueでRuntimeErrorが発生する。
    """

    fetcher = RecordingFetcher(raise_error=True)
    client = HttpsClient(fetcher=fetcher)

    with pytest.raises(RuntimeError):
        client.get("https://example.com/error")


@pytest.mark.online
def test_get_real_request() -> None:
    """
    docs:
        目的:
            実ネットワークで GET が成功することを確認する。
        検証観点:
            - 本文が空でない。
            - ステータスコードが 200 系である。
    """

    client = HttpsClient()

    response = client.get("https://example.com", timeout=5.0)

    assert response.status_code == HTTP_STATUS_OK
    assert "Example Domain" in response.text()
