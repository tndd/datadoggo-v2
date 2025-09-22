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
