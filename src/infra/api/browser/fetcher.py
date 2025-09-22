"""ブラウザからコンテンツを取得する高レベルAPI"""

import asyncio
from typing import Tuple

from pydoll.browser.chromium import Chrome

from infra.storage.file import SaveFormat, save_content_to_file

from .core import (
    BrowserInitError,
    ContentFetchError,
    FetchFormat,
    fetch_current_url,
    fetch_title,
    find_body_element,
    get_browser_options,
    navigate_to_url,
    retrieve_content,
    start_browser_tab,
)
from .extraction import BOT_BLOCKED_KEYWORDS


async def fetch_page_content(url: str, page_timeout: int = 15) -> Tuple[str, str, str]:
    """指定URLからコンテンツ、タイトル、現在のURLを取得する"""

    try:
        options = get_browser_options()

        async with Chrome(options=options) as browser:
            tab = await start_browser_tab(browser)
            await navigate_to_url(tab, url)

            body_element = await tab.find(
                tag_name="body",
                timeout=page_timeout,
                raise_exc=False,
            )
            if body_element is None:
                raise ContentFetchError("body要素が見つかりませんでした")

            print("ページが読み込まれました")

            content_text = await body_element.text

            try:
                title_element = await tab.find("title", timeout=2, raise_exc=False)
                title = await title_element.text if title_element else "Unknown"
            except Exception:
                title = "Unknown"

            try:
                current_url = await tab.get_url()
            except Exception:
                current_url = url

            print(f"コンテンツ長: {len(content_text)}文字")
            print(f"タイトル: {title}")
            print(f"最初の100文字: {content_text[:100]}")

            return content_text, title, current_url

    except Exception as error:
        if "Chrome" in str(error) or "browser" in str(error).lower():
            raise BrowserInitError(f"ブラウザ初期化エラー: {error}") from error
        raise ContentFetchError(f"コンテンツ取得エラー: {error}") from error


async def fetch_page_content_unified(
    url: str,
    format: FetchFormat = FetchFormat.HTML,
    page_timeout: int = 15,
) -> Tuple[str, str, str]:
    """指定URLからコンテンツを出力形式に応じて取得する"""

    options = get_browser_options()

    try:
        async with Chrome(options=options) as browser:
            tab = await start_browser_tab(browser)
            await navigate_to_url(tab, url)

            body_element = await find_body_element(tab, page_timeout)
            print("ページが読み込まれました")

            content = await retrieve_content(tab, body_element, format)
            title = await fetch_title(tab)
            current_url = await fetch_current_url(tab, url)

            print(f"タイトル: {title}")
            print(f"最初の100文字: {content[:100]}")

            return content, title, current_url
    except ContentFetchError:
        raise
    except BrowserInitError:
        raise
    except Exception as error:
        if "Chrome" in str(error) or "browser" in str(error).lower():
            raise BrowserInitError(f"ブラウザ初期化エラー: {error}") from error
        raise ContentFetchError(f"コンテンツ取得エラー: {error}") from error


def analyze_content(
    content: str,
    title: str,
    original_url: str,
    current_url: str,
) -> Tuple[str, bool, bool]:
    """取得コンテンツを整形し、リダイレクト／Bot排除を判定する"""

    redirect_success = current_url != original_url
    is_bot_blocked = any(keyword in content for keyword in BOT_BLOCKED_KEYWORDS)

    formatted_content = f"タイトル: {title}\n"
    formatted_content += f"URL: {current_url}\n"
    formatted_content += f"リダイレクト成功: {redirect_success}\n"
    formatted_content += f"Bot排除: {is_bot_blocked}\n"
    formatted_content += f"コンテンツ:\n{content}"

    return formatted_content, redirect_success, is_bot_blocked


def handle_fetch_error(error: Exception) -> Tuple[str, bool, bool]:
    """取得処理の失敗を整形して返す"""

    error_message = f"エラー: {error}"
    print(f"処理中にエラーが発生しました: {error_message}")
    return error_message, False, True


async def fetch_news_content(
    url: str,
    format: FetchFormat = FetchFormat.HTML,
    page_timeout: int = 15,
) -> Tuple[str, bool, bool]:
    """ニュースコンテンツを取得し、Bot排除状況を返す"""

    try:
        content, _, current_url = await fetch_page_content_unified(
            url,
            format,
            page_timeout,
        )
        redirect_success = current_url != url
        is_bot_blocked = any(keyword in content for keyword in BOT_BLOCKED_KEYWORDS)
        return content, redirect_success, is_bot_blocked
    except (BrowserInitError, ContentFetchError) as error:
        return handle_fetch_error(error)
    except Exception as error:
        return handle_fetch_error(error)


async def fetch_and_save_content(
    url: str,
    format: FetchFormat = FetchFormat.HTML,
    output_dir: str = "mock",
    page_timeout: int = 15,
) -> str:
    """コンテンツ取得とファイル出力を一括で行う"""

    print(f"コンテンツを取得中... ({format.value}形式)")

    content, redirect_success, bot_blocked = await fetch_news_content(
        url,
        format,
        page_timeout,
    )

    print("=== 取得結果 ===")
    print(f"形式: {format.value}")
    print(f"文字数: {len(content)}文字")
    print(f"最初の100文字: {content[:100]}")
    print("\n=== 検証結果 ===")
    print(f"リダイレクト成功: {redirect_success}")
    print(f"Bot排除: {bot_blocked}")

    save_format = SaveFormat.HTML if format == FetchFormat.HTML else SaveFormat.TEXT
    filepath = save_content_to_file(content, save_format, None, output_dir)
    return filepath


async def main():
    """簡易動作確認用のメイン関数"""

    google_news_url = (
        "https://news.google.com/read/CBMidkFVX3lxTFBBQmZUaVRZalQwVkh4OUhpdHBfZlh3OVE4"
        "UVFCNldUVk81N1RLN2gyMkYyejREWUREU3BubGlibXA3SWVmWG1KcHNtSUtKVGcwc0VyTFlfY3ky"
        "ekxXR3Y0UzRKS2VxWlNnZzE5dTd1RjRPOFRjU2c?hl=ja&gl=JP&ceid=JP%3Aja"
    )

    html_filepath = await fetch_and_save_content(
        google_news_url,
        FetchFormat.HTML,
        "mock",
    )
    print(f"\nHTML形式で保存完了: {html_filepath}")

    text_filepath = await fetch_and_save_content(
        google_news_url,
        FetchFormat.TEXT,
        "mock",
    )
    print(f"TEXT形式で保存完了: {text_filepath}")


if __name__ == "__main__":
    asyncio.run(main())
