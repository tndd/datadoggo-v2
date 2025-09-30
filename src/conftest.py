"""pytest共通フィクスチャ"""

from __future__ import annotations

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


@pytest.fixture(scope="function", autouse=True)
def reset_db_engine():
    """各テスト実行前にDBエンジンキャッシュをクリア"""
    import infra.storage.rds

    # テスト間でエンジンがキャッシュされている場合にクリア
    if hasattr(infra.storage.rds, "_test_engine"):
        infra.storage.rds._test_engine = None
    yield
