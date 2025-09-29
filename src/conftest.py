"""pytest共通フィクスチャ"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from infra.logging import configure_logging, reset_logging


@pytest.fixture
def app_logging(fs: FakeFilesystem):
    """テスト用にloguruを仮想ファイルシステムへ設定する"""

    log_path = Path("/logs/app.log")
    configure_logging(log_path=log_path, enqueue=False)
    yield log_path
    reset_logging()


@pytest.fixture
def test_db_env():
    """テスト用DB環境変数を設定・復元する"""

    # 元の環境変数を保存
    original_db_url = os.environ.get("FEED_DATABASE_URL")

    # インメモリDBに設定
    os.environ["FEED_DATABASE_URL"] = "sqlite:///:memory:"

    yield "sqlite:///:memory:"

    # 環境変数を復元
    if original_db_url is not None:
        os.environ["FEED_DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("FEED_DATABASE_URL", None)
