"""Articleドメインのエントリーポイント"""

from .command import mark_fetch_failed, save_article_content
from .fetch import fetch_article_content
from .model import (
    Article,
    ArticleBucketMetadata,
    ArticleBucketMetadataRecord,
    ArticleContent,
    ArticleFetchStatus,
)
from .search import ArticleSearchQuery, find_article_by_id, search_article_metadata

__all__ = [
    "Article",
    "ArticleBucketMetadata",
    "ArticleBucketMetadataRecord",
    "ArticleContent",
    "ArticleFetchStatus",
    "ArticleSearchQuery",
    "mark_fetch_failed",
    "fetch_article_content",
    "find_article_by_id",
    "save_article_content",
    "search_article_metadata",
]
