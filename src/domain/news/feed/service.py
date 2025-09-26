"""Feed向け共通サービスユーティリティ"""

from __future__ import annotations

from pydantic import HttpUrl, TypeAdapter

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列/HttpUrl入力をHttpUrlとして検証する"""

    return HTTP_URL_ADAPTER.validate_python(value)
