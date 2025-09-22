"""ブラウザからコンテンツを取得する"""

import asyncio
import os
from typing import Any

from pydantic import BaseModel
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions


class PageContent(BaseModel):
    """ブラウザから取得したページ素材"""

    url: str
    title: str
    html: str


async def fetch_page_content(
    url: str,
    page_timeout: int = 15,
) -> PageContent:
    """指定URLからHTMLとメタ情報を取得する"""

    try:
        options = get_browser_options()

        async with Chrome(options=options) as browser:
            tab = await start_browser_tab(browser)
            await navigate_to_url(tab, url)

            await find_body_element(tab, page_timeout)
            print("ページが読み込まれました")

            html = await tab.page_source

            try:
                title_element = await tab.find("title", timeout=2, raise_exc=False)
                title = await title_element.text if title_element else "Unknown"
            except Exception:
                title = "Unknown"

            try:
                current_url = await tab.get_url()
            except Exception:
                current_url = url

            print(f"HTML長: {len(html)}文字")
            print(f"タイトル: {title}")
            print(f"最初の100文字: {html[:100]}")

            return PageContent(url=current_url, title=title, html=html)

    except Exception as error:
        if "Chrome" in str(error) or "browser" in str(error).lower():
            raise Exception(f"ブラウザ初期化エラー: {error}") from error
        raise Exception(f"コンテンツ取得エラー: {error}") from error


class ContentFetchError(Exception):
    """コンテンツ取得時のエラー"""

    pass


class BrowserInitError(Exception):
    """ブラウザ初期化時のエラー"""

    pass


def get_browser_options() -> ChromiumOptions:
    """Chromium起動オプションを構築する"""

    options = ChromiumOptions()
    default_chromium_path = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    chromium_path = os.getenv("CHROMIUM_PATH", default_chromium_path)
    options.binary_location = chromium_path
    return options


async def start_browser_tab(browser) -> Any:
    """ブラウザタブを起動する"""

    try:
        return await browser.start()
    except Exception as error:
        raise BrowserInitError(f"ブラウザ起動に失敗しました: {error}") from error


async def navigate_to_url(tab, url: str) -> None:
    """指定URLへ遷移する"""

    try:
        await tab.go_to(url)
    except Exception as error:
        raise ContentFetchError(f"URLへのアクセスに失敗しました: {error}") from error


async def find_body_element(tab, page_timeout: int):
    """body要素を取得する"""

    body_element = await tab.find(
        tag_name="body",
        timeout=page_timeout,
        raise_exc=False,
    )
    if body_element is None:
        raise ContentFetchError("body要素が見つかりませんでした")
    return body_element


async def fetch_title(tab) -> str:
    """ページタイトルを取得する"""

    try:
        title_element = await tab.find(tag_name="title", timeout=2, raise_exc=False)
        return await title_element.text if title_element else "Unknown"
    except Exception as error:
        print(f"タイトル取得エラー: {error}")
        return "Unknown"


async def fetch_current_url(tab, fallback_url: str) -> str:
    """現在のURLを取得する"""

    try:
        return await tab.get_url()
    except Exception as error:
        print(f"URL取得エラー: {error}")
        return fallback_url


async def main() -> None:
    """簡易動作確認用のメイン関数"""

    google_news_url = (
        "https://news.google.com/read/CBMidkFVX3lxTFBBQmZUaVRZalQwVkh4OUhpdHBfZlh3OVE4"
        "UVFCNldUVk81N1RLN2gyMkYyejREWUREU3BubGlibXA3SWVmWG1KcHNtSUtKVGcwc0VyTFlfY3ky"
        "ekxXR3Y0UzRKS2VxWlNnZzE5dTd1RjRPOFRjU2c?hl=ja&gl=JP&ceid=JP%3Aja"
    )
    page_content = await fetch_page_content(google_news_url)
    print(page_content.html[:100])


if __name__ == "__main__":
    asyncio.run(main())
