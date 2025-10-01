"""pytest共通フィクスチャ（tests配下用）"""

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


@pytest.fixture(autouse=True)
def initialize_test_db():
    """各テスト実行前に自動的にDBを初期化"""
    import infra.storage.rds
    from infra.storage.rds import initialize_database

    # テスト開始前にエンジンキャッシュをクリア
    if hasattr(infra.storage.rds, "_test_engine"):
        infra.storage.rds._test_engine = None

    # DBを初期化（新しいエンジンでテーブル作成）
    initialize_database()


@pytest.fixture
def project_root(fs: FakeFilesystem) -> Path:
    """プロジェクトルートディレクトリを仮想FS上に作成して返す"""
    root = Path("/project")
    if not fs.exists(str(root)):
        fs.create_dir(str(root))
    return root


@pytest.fixture(autouse=True)
def setup_common_dirs(fs: FakeFilesystem):
    """テストで頻繁に使用されるディレクトリを事前作成"""
    common_dirs = ["/tmp", "/data"]
    for dir_path in common_dirs:
        if not fs.exists(dir_path):
            fs.create_dir(dir_path)
