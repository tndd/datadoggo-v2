"""domain.news.article.command のテスト"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from pydantic import HttpUrl
from pyfakefs.fake_filesystem import FakeFilesystem

from domain.news.article.command import BUCKET_NAME, save_article_content
from domain.news.article.model import Article
from infra.storage.bucket import load_object


def test_save_article_content_saves_html(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: Article のHTMLコンテンツがバケットに保存されることを確認する。
        検証観点:
            - バケットにHTMLが保存される。
            - 正しいobject_keyが返される。
    """

    project_root = Path(__file__).parent.parent.parent.parent
    if not fs.exists(str(project_root)):
        fs.create_dir(str(project_root))
    os.chdir(project_root)

    base_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
    article = Article(
        id="abc",
        url=cast(HttpUrl, "https://example.com/article"),
        content="<html>body</html>",
        group="test:command",
        created_at=base_time,
        updated_at=base_time,
        description="サンプル",
    )

    saved_key = save_article_content(article)

    assert saved_key == article.id
    stored_html = load_object(bucket_name=BUCKET_NAME, object_key=article.id)
    assert stored_html == "<html>body</html>"


def test_save_article_content_raises_on_save_failure(
    fs: FakeFilesystem, monkeypatch
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

    base_time = datetime(2025, 9, 29, 9, 0, tzinfo=timezone.utc)
    article = Article(
        id="xyz",
        url=cast(HttpUrl, "https://example.com/failure"),
        content="<html>failure</html>",
        group="test:failure",
        created_at=base_time,
        updated_at=base_time,
        description="失敗",
    )

    import sys

    def fake_save_object(**kwargs):  # type: ignore[no-untyped-def]
        return ""

    module = sys.modules["domain.news.article.command"]
    monkeypatch.setattr(module, "save_object", fake_save_object)

    try:
        save_article_content(article)
        raise AssertionError("例外が発生しませんでした")
    except RuntimeError:
        pass
