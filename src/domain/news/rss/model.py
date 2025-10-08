"""RSSリンクに関するドメインモデル"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# TODO: RssLinkに改名
class RssItem(BaseModel):
    """links.yml に定義された RSS リンクのエントリ"""

    model_config = ConfigDict(frozen=True)

    group: str
    name: str
    url: str


# TODO: LoadRssLinkQueryに改名しsearchへ移動
class RssItemQuery(BaseModel):
    """links.yml のフィルタ条件を表現するクエリ"""

    model_config = ConfigDict(frozen=True)

    group: str | None = None
    name: str | None = None
    path: str = "./links.yml"
