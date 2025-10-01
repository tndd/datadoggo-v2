"""HTTPS経由でコンテンツを取得する最小限のクライアント"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from infra.logging import get_logger

DEFAULT_TIMEOUT = 10.0
DEFAULT_ENCODING = "utf-8"
DEFAULT_USER_AGENT = "datadoggo-v2/https-client"
HTTP_STATUS_OK = 200

RequestData = bytes | str | Mapping[str, str | Sequence[str]] | None


class HttpResponse(BaseModel):
    """HTTPレスポンスを表現するオブジェクト"""

    model_config = ConfigDict(frozen=True)

    url: str
    method: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    encoding: str | None = None

    def text(self, *, encoding: str | None = None, errors: str = "replace") -> str:
        """本文を文字列へ変換する"""

        actual_encoding = encoding or self.encoding
        if actual_encoding is None:
            raise ValueError("エンコーディングが未設定のためテキストへ変換できません")
        return self.body.decode(actual_encoding, errors=errors)


Fetcher = Callable[[str, str, dict[str, str], bytes | None, float], HttpResponse]

LOG = get_logger()


class HttpsClient:
    """GET/POSTを提供するシンプルなHTTPクライアント"""

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        default_timeout: float = DEFAULT_TIMEOUT,
        default_encoding: str = DEFAULT_ENCODING,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._user_agent = user_agent
        self._is_custom_fetcher = fetcher is not None
        self._fetcher = fetcher or self._default_fetcher(user_agent=user_agent)
        self._default_timeout = default_timeout
        self._default_encoding = default_encoding

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """HTTP GET を実行する"""

        return self._request("GET", url, headers=headers, data=None, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        data: RequestData = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        encoding: str | None = None,
    ) -> HttpResponse:
        """HTTP POST を実行する"""

        request_headers = dict(headers or {})
        payload = self._prepare_data(data, encoding)

        if data is not None and not self._has_header(request_headers, "content-type"):
            if isinstance(data, Mapping):
                request_headers["Content-Type"] = "application/x-www-form-urlencoded"

        return self._request(
            "POST",
            url,
            headers=request_headers,
            data=payload,
            timeout=timeout,
        )

    def clone(self) -> "HttpsClient":
        """同一設定を持つ新しい HttpsClient を生成する"""

        if self._is_custom_fetcher:
            fetcher = self._fetcher
        else:
            fetcher = self._default_fetcher(user_agent=self._user_agent)

        return HttpsClient(
            fetcher=fetcher,
            default_timeout=self._default_timeout,
            default_encoding=self._default_encoding,
            user_agent=self._user_agent,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        data: bytes | None,
        timeout: float | None,
    ) -> HttpResponse:
        actual_timeout = timeout if timeout is not None else self._default_timeout
        header_dict = dict(headers or {})

        try:
            response = self._fetcher(method, url, header_dict, data, actual_timeout)
        except URLError as exc:
            # pragma: no cover - ネットワークエラーは通常モックで再現しない
            LOG.error(
                "HTTPリクエストに失敗しました",
                method=method,
                url=url,
                timeout=actual_timeout,
                error=str(exc),
            )
            raise RuntimeError("HTTPリクエストに失敗しました") from exc

        if response.encoding is None:
            response = response.model_copy(update={"encoding": self._default_encoding})

        LOG.debug(
            "HTTPレスポンスを受信しました",
            method=method,
            url=url,
            status_code=response.status_code,
            bytes=len(response.body),
        )

        return response

    def _prepare_data(self, data: RequestData, encoding: str | None) -> bytes | None:
        if data is None:
            return None

        if isinstance(data, bytes):
            return data

        actual_encoding = encoding or self._default_encoding

        if isinstance(data, str):
            return data.encode(actual_encoding)

        if isinstance(data, Mapping):
            items: list[tuple[str, Any]] = []
            for key, value in data.items():
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    for inner in value:
                        items.append((key, inner))
                else:
                    items.append((key, value))
            return urlencode(items).encode(actual_encoding)

        raise TypeError("サポートされていないデータ型です")

    @staticmethod
    def _has_header(headers: Mapping[str, str], target: str) -> bool:
        return any(key.lower() == target.lower() for key in headers)

    @staticmethod
    def _default_fetcher(*, user_agent: str) -> Fetcher:
        """urllibを使ったフェッチャ実装"""

        def _fetch(
            method: str,
            url: str,
            headers: dict[str, str],
            data: bytes | None,
            timeout: float,
        ) -> HttpResponse:
            request_headers = dict(headers)
            if not any(key.lower() == "user-agent" for key in request_headers):
                request_headers["User-Agent"] = user_agent

            request = Request(url, data=data, headers=request_headers, method=method)
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
                status = getattr(response, "status", None) or response.getcode() or 0
                encoding = response.headers.get_content_charset()  # type: ignore[no-untyped-call]
                header_map = dict(response.headers.items())
                return HttpResponse(
                    url=response.geturl() or url,
                    method=method,
                    status_code=status,
                    headers=header_map,
                    body=payload,
                    encoding=encoding,
                )

        return _fetch


@dataclass
class RecordingFetcher:
    """テスト用のフェッチャーモック"""

    response_text: str | None = ""
    response_body: bytes | None = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    encoding: str | None = None
    raise_error: bool = False
    calls: list[tuple[str, str, dict[str, str], bytes | None, float]] = field(
        default_factory=list
    )

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes | None,
        timeout: float,
    ) -> HttpResponse:
        self.calls.append((method, url, dict(headers), data, timeout))
        if self.raise_error:
            raise URLError("mock failure")

        if self.response_body is not None:
            body = self.response_body
        else:
            text = self.response_text or ""
            body = text.encode(self.encoding or DEFAULT_ENCODING)

        response_headers = dict(self.headers)
        return HttpResponse(
            url=url,
            method=method,
            status_code=self.status_code,
            headers=response_headers,
            body=body,
            encoding=self.encoding,
        )


