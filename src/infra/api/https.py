"""HTTPS経由でコンテンツを取得するクライアント"""

from __future__ import annotations

from collections.abc import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element

from infra.parse import parse_rss

DEFAULT_TIMEOUT = 10.0
DEFAULT_ENCODING = "utf-8"
DEFAULT_USER_AGENT = "datadoggo-v2/https-client"

FetchResult = tuple[bytes, str | None]
Fetcher = Callable[[str, float], FetchResult]


class HttpsClient:
    """シンプルなHTTPSクライアント。モック差し替え可能な構成"""

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        default_timeout: float = DEFAULT_TIMEOUT,
        default_encoding: str = DEFAULT_ENCODING,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._fetcher = fetcher or self._default_fetcher(user_agent=user_agent)
        self._default_timeout = default_timeout
        self._default_encoding = default_encoding

    def fetch_text(
        self,
        url: str,
        *,
        timeout: float | None = None,
        encoding: str | None = None,
    ) -> str:
        """指定URLからテキストを取得する"""

        actual_timeout = timeout if timeout is not None else self._default_timeout
        try:
            payload, charset = self._fetcher(url, actual_timeout)
        except URLError as exc:
            # pragma: no cover - 通常テストではネットワークエラーを再現しない
            raise RuntimeError("HTTP取得に失敗しました") from exc

        detected_encoding = encoding or charset or self._default_encoding
        return payload.decode(detected_encoding, errors="replace")

    def fetch_rss_root(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> Element:
        """指定URLのRSSを取得しElementツリーに変換する"""

        text = self.fetch_text(url, timeout=timeout)
        return parse_rss(text)

    @staticmethod
    def _default_fetcher(*, user_agent: str) -> Fetcher:
        """urllibを使ったデフォルトフェッチャを生成する"""

        def _fetch(url: str, timeout: float) -> FetchResult:
            request = Request(url, headers={"User-Agent": user_agent})
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
                charset = response.headers.get_content_charset()  # type: ignore[no-untyped-call]
            return payload, charset

        return _fetch


class Tests:
    def test_fetch_text_uses_injected_fetcher(self) -> None:
        """
        docs:
            目的:
                fetch_text が注入フェッチャー経由で文字列を取得することを確認する。
            検証観点:
                - 指定したURLとタイムアウトがフェッチャーに渡される。
                - charset の情報でデコードされる。
        """

        calls: list[tuple[str, float]] = []

        def fake_fetch(url: str, timeout: float) -> FetchResult:
            calls.append((url, timeout))
            return "こんにちは".encode("shift_jis"), "shift_jis"

        client = HttpsClient(fetcher=fake_fetch, default_timeout=1.0)

        text = client.fetch_text("https://example.com/feed")

        assert text == "こんにちは"
        assert calls == [("https://example.com/feed", 1.0)]

    def test_fetch_text_falls_back_to_default_encoding(self) -> None:
        """
        docs:
            目的:
                charset 不明でも既定エンコーディングでデコードできることを確認する。
            検証観点:
                - charset=None の場合に default_encoding でデコードされる。
        """

        def fake_fetch(_: str, __: float) -> FetchResult:
            return "テスト".encode("utf-8"), None

        client = HttpsClient(fetcher=fake_fetch, default_encoding="utf-8")

        text = client.fetch_text("https://example.com/rss")

        assert text == "テスト"

    def test_fetch_rss_root_returns_element(self) -> None:
        """
        docs:
            目的:
                fetch_rss_root が RSS を取得して Element を返すことを確認する。
            検証観点:
                - RSS文字列が parse_rss で解析される。
                - ルートタグが rss である。
        """

        rss = """
            <rss version="2.0">
                <channel>
                    <item>
                        <title>Example</title>
                        <link>https://example.com</link>
                        <pubDate>Mon, 22 Sep 2025 09:00:00 GMT</pubDate>
                    </item>
                </channel>
            </rss>
        """

        def fake_fetch(_: str, __: float) -> FetchResult:
            return rss.encode("utf-8"), "utf-8"

        client = HttpsClient(fetcher=fake_fetch)

        root = client.fetch_rss_root("https://example.com/rss")

        assert root.tag.endswith("rss")
        channel = root.find("channel")
        assert channel is not None
