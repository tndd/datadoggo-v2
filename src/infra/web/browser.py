"""
pydollを使ったコンテンツ取得
動的サイトやbot対策がなされたサイトに対して使う
"""

import asyncio
import os

from pydantic import BaseModel
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

from infra.logger import get_logger

LOG = get_logger()

# TODO: 戻り値のクラスの形は再考が必要


class PageContent(BaseModel):
    """ブラウザから取得したページ素材"""

    url: str
    title: str
    html: str


async def fetch_page_content(url: str) -> PageContent:
    """指定URLからHTMLとメタ情報を取得する"""
    options = _get_browser_options()

    async with Chrome(options=options) as browser:
        return await _operate_browser(browser, url)


async def _operate_browser(browser, url: str) -> PageContent:
    """ブラウザを操作しURLからコンテンツを取得する"""
    TIMEOUT = 3
    tab = await browser.start()
    await tab.go_to(url)

    # body要素が読み込まれるまで待機（エラー時は続行）
    try:
        await tab.find("body", timeout=TIMEOUT)
    except Exception as error:
        LOG.warning(
            "body要素の読み込み待機に失敗しました",
            url=url,
            timeout=TIMEOUT,
            error=str(error),
        )
    LOG.info("ページを読み込みました", url=url)

    html = await tab.page_source
    title = await _fetch_title(tab)

    LOG.info(
        "ページコンテンツを取得しました",
        url=url,
        title=title,
        html_length=len(html),
        preview=html[:100],
    )

    return PageContent(url=url, title=title, html=html)


def _get_browser_options() -> ChromiumOptions:
    """Chromium起動オプションを構築する"""

    options = ChromiumOptions()
    default_chromium_path = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    chromium_path = os.getenv("CHROMIUM_PATH", default_chromium_path)
    options.binary_location = chromium_path
    return options


async def _fetch_title(tab) -> str:
    """ページタイトルを取得する"""

    try:
        title_element = await tab.find(tag_name="title", timeout=2, raise_exc=False)
        return await title_element.text if title_element else "Unknown"
    except Exception as error:
        LOG.warning("タイトル取得に失敗しました", error=str(error))
        return "Unknown"


class TestMod:
    """外部公開関数のテスト"""

    import pytest

    @pytest.mark.asyncio
    @pytest.mark.online
    async def test_fetch_page_content(self) -> None:
        url = "https://example.com"
        page_content = await fetch_page_content(url)
        assert page_content.html is not None


# 廃止
async def main() -> None:
    pass
    # """簡易動作確認用のメイン関数"""

    # # test_url = "https://news.google.com/rss/articles/CBMitAFBVV95cUxOazVjXzdVWjB2OEI3NURoWHJqaWlxRnluWkZxTkJwbkNVZjRtODNZWEZXd0tmSnE4UF9QZ29YNnYwN1pISF84NlhfcU5HdDdjNFFjZTN4b3ozM2pITXlfN2lVM0VGbU5od3RTN19WY3lObEZEZnFVQnc2Sy1kUnRXMXFRRXJUTWpNZ2M2U1VwRDlveUk3eExVSlEzRGg4cnRxM1VPRWh5bDA1T0dPcVlPRUNJaG8?oc=5"
    # test_url = "https://example.com"
    # page_content = await fetch_page_content(test_url)
    # print(page_content.html[:100])


# 廃止
if __name__ == "__main__":
    asyncio.run(main())
