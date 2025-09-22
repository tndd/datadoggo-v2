"""ブラウザ操作に関する共通ロジック"""

import os
from enum import Enum
from typing import Any

from pydoll.browser.options import ChromiumOptions

from .extraction import extract_article_text


class ContentFetchError(Exception):
    """コンテンツ取得時のエラー"""

    pass


class BrowserInitError(Exception):
    """ブラウザ初期化時のエラー"""

    pass


class FetchFormat(Enum):
    """ブラウザ取得時の出力形式"""

    TEXT = "txt"
    HTML = "html"


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


async def retrieve_content(tab, body_element, format: FetchFormat) -> str:
    """出力形式に応じたコンテンツ取得を行う"""

    if format == FetchFormat.HTML:
        try:
            content = await tab.page_source
        except Exception as error:
            raise ContentFetchError(f"HTML取得に失敗しました: {error}") from error
        print(f"HTML長: {len(content)}文字")
        return content

    try:
        content = await extract_article_text(tab, body_element)
    except Exception as error:
        raise ContentFetchError(f"テキスト抽出に失敗しました: {error}") from error

    print(f"テキスト長: {len(content)}文字")
    return content


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
