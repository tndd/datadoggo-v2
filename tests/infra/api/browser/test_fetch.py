"""infra.api.browser.fetch のテスト"""

import pytest

from infra.api.browser.fetch import fetch_page_content


@pytest.mark.asyncio
@pytest.mark.online
async def test_fetch_page_content() -> None:
    """外部公開関数のテスト"""
    url = "https://example.com"
    page_content = await fetch_page_content(url)
    assert page_content.html is not None
