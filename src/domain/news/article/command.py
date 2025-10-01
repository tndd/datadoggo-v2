"""Articleコンテンツの保存コマンド"""

from __future__ import annotations

from infra.storage.bucket import save_object

from .model import Article

BUCKET_NAME = "article"


def save_article_content(article: Article) -> str:
    """記事のHTMLコンテンツをバケットに保存する"""

    saved_key = save_object(
        payload=article.content,
        bucket_name=BUCKET_NAME,
        object_key=article.id,
    )
    if not saved_key:
        msg = f"記事HTMLの保存に失敗しました: article_id={article.id}"
        raise RuntimeError(msg)

    return saved_key


# 取得失敗はHttpRequestTaskのstatus_codeで管理されるため、この関数は不要
