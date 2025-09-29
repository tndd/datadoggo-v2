"""RSSリンクに関するドメインモデル"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError


class RssItem(BaseModel):
    """links.yml に定義された RSS リンクのエントリ"""

    model_config = ConfigDict(frozen=True)

    group: str
    name: str
    url: str


class Tests:
    class Test_RssItem:
        def test_rss_item_is_immutable(self) -> None:
            """
            docs:
                目的: RssItem がイミュータブルに扱われることを確認する。
                検証観点:
                    - frozen 設定により属性更新が禁止される。
            """

            item = RssItem(group="bbc", name="top", url="https://example.com/rss")

            with pytest.raises(ValidationError):
                item.group = "cnn"
