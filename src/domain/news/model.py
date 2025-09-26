from datetime import datetime

from pydantic import BaseModel, HttpUrl


class FeedItem(BaseModel):
    """Feedテーブルの要素のドメイン表現"""

    id: str
    url: HttpUrl
    title: str
    status_code: int
    pub_date: datetime
