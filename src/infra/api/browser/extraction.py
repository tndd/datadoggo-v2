"""ブラウザから記事コンテンツを抽出するロジック"""

import asyncio

# コンテンツ抽出に利用する閾値
MIN_CONTENT_LENGTH = 100  # 十分なコンテンツがあると判断する最小文字数
MIN_TEXT_LENGTH = 50  # テキストとして有効と判断する最小文字数

# Bot排除を推測するキーワード一覧
BOT_BLOCKED_KEYWORDS = [
    "Access Denied",
    "Blocked",
    "403",
    "Forbidden",
    "Captcha",
]


async def extract_article_text(tab, body_element) -> str:
    """記事コンテンツからテキストを抽出する"""

    print("JavaScriptコンテンツの読み込みを待機中...")
    await asyncio.sleep(3)

    article_selectors = [
        "article",
        "[data-content-type='article']",
        ".content",
        ".article-body",
        ".post-content",
        "main",
        "p",
    ]

    content = ""
    try:
        for selector in article_selectors:
            elements = await tab.query(
                selector,
                timeout=2,
                find_all=True,
                raise_exc=False,
            )
            if not elements:
                continue

            text_parts = []
            for element in elements:
                try:
                    element_text = await element.text
                except Exception:
                    continue

                if element_text and element_text.strip():
                    text_parts.append(element_text.strip())

            if text_parts:
                content = "\n\n".join(text_parts)
                if len(content) > MIN_CONTENT_LENGTH:
                    break
    except Exception as error:
        print(f"記事要素の取得でエラー発生: {error}")

    if not content or len(content) < MIN_TEXT_LENGTH:
        try:
            body_text = await body_element.text
        except Exception as error:
            print(f"body要素からのテキスト取得に失敗: {error}")
            return content

        if body_text and len(body_text) > len(content):
            content = body_text

    return content


class TestsExtraction:
    # docs:
    #   目的: 記事要素に十分なテキストがある場合に本文が優先されるか確認
    #   検証観点: MIN_CONTENT_LENGTHがarticle抽出結果の採用条件になるか
    def test_prefers_article_content_when_sufficient(self) -> None:
        article_texts = ["本文" * 40, "続き" * 40]
        tab = self._make_tab(
            {"article": [self._make_element(text) for text in article_texts]}
        )
        body = self._make_element("ボディフォールバック")

        content = self._run_extract(tab, body)

        expected = "\n\n".join(article_texts)
        assert content == expected

    # docs:
    #   目的: 記事要素が空の場合にbodyテキストへフォールバックできるか確認
    #   検証観点: 空文字列でもbody.textが採用されるか
    def test_falls_back_to_body_when_article_insufficient(self) -> None:
        tab = self._make_tab(
            {"article": [self._make_element("   "), self._make_element("")]}
        )
        body_text = "ボディテキスト" * 10
        body = self._make_element(body_text)

        content = self._run_extract(tab, body)

        assert content == body_text

    # docs:
    #   目的: 要素取得で例外が出ても処理継続しフォールバックできるか確認
    #   検証観点: 要素.text失敗時にスキップしbodyテキストを返すか
    def test_ignores_element_errors_and_uses_body(self) -> None:
        tab = self._make_tab(
            {"article": [self._make_element("本文", should_raise=True)]}
        )
        body_text = "例外時フォールバック" * 5
        body = self._make_element(body_text)

        content = self._run_extract(tab, body)

        assert content == body_text

    @staticmethod
    def _make_element(text_value: str, *, should_raise: bool = False):
        """テキスト取得用のモック要素を生成する"""

        async def _get_text() -> str:
            if should_raise:
                raise RuntimeError("テキスト取得に失敗")
            return text_value

        element_type = type(
            "MockElement",
            (),
            {"text": property(lambda self: _get_text())},
        )
        return element_type()

    @staticmethod
    def _make_tab(elements_map):
        """query応答を制御するモックタブを生成する"""

        async def _query(self, selector, timeout=2, find_all=True, raise_exc=False):
            return elements_map.get(selector, [])

        tab_type = type("MockTab", (), {"query": _query})
        return tab_type()

    @staticmethod
    def _run_extract(tab, body) -> str:
        """extract_article_textの実行ラッパ"""

        return asyncio.run(extract_article_text(tab, body))
