"""Articleコンテンツの保存コマンド"""

from __future__ import annotations

from infra.storage.bucket import save_object

from .model import Article

BUCKET_NAME = "article"


def save_article_content(article: Article) -> str:
    """記事のHTMLコンテンツをバケットに保存する"""

    saved_key = save_object(
        payload=article.html_content,
        bucket_name=BUCKET_NAME,
        object_key=article.id,
    )
    if not saved_key:
        raise RuntimeError(f"記事HTMLの保存に失敗しました: feed_id={article.id}")

    return saved_key


# 取得失敗はFeedItemのstatus_codeで管理されるため、この関数は不要


class Tests:
    class Test_save_article_content:
        def test_save_article_content_saves_html(self, fs) -> None:
            """
            docs:
                目的: Article のHTMLコンテンツがバケットに保存されることを確認する。
                検証観点:
                    - バケットにHTMLが保存される。
                    - 正しいobject_keyが返される。
            """

            import os
            from datetime import datetime, timezone
            from pathlib import Path
            from typing import cast

            from pydantic import HttpUrl

            from infra.storage.bucket import load_object

            project_root = Path(__file__).resolve().parents[4]
            if not fs.exists(str(project_root)):
                fs.create_dir(str(project_root))
            os.chdir(project_root)

            article = Article(
                id="abc",
                url=cast(HttpUrl, "https://example.com/article"),
                title="サンプル",
                pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                html_content="<html>body</html>",
            )

            saved_key = save_article_content(article)

            assert saved_key == article.id
            stored_html = load_object(
                bucket_name=BUCKET_NAME,
                object_key=article.id,
                as_text=True,
            )
            assert stored_html == "<html>body</html>"

        def test_save_article_content_raises_on_save_failure(
            self, fs, monkeypatch
        ) -> None:
            """
            docs:
                目的: バケット保存失敗時に例外が送出されることを確認する。
                検証観点:
                    - save_object が空文字を返した場合に RuntimeError が発生する。
            """

            from datetime import datetime, timezone
            from typing import cast

            from pydantic import HttpUrl

            article = Article(
                id="xyz",
                url=cast(HttpUrl, "https://example.com/failure"),
                title="失敗",
                pub_date=datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc),
                html_content="<html>failure</html>",
            )

            import sys

            def fake_save_object(**kwargs):  # type: ignore[no-untyped-def]
                return ""

            module = sys.modules[__name__]
            monkeypatch.setattr(module, "save_object", fake_save_object)

            try:
                save_article_content(article)
                raise AssertionError("例外が発生しませんでした")
            except RuntimeError:
                pass
