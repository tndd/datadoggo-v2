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


@pytest.fixture(scope="session")
def test_db_engine():
    """テスト用インメモリDBエンジンを提供（セッションスコープ）"""
    from infra.storage.rds import create_sqlite_engine, initialize_database

    # テーブル定義をインポート（テーブル作成に必要）
    import domain.task_queue.http_request.model  # noqa: F401

    # インメモリDBエンジンを作成してテーブル初期化
    engine = create_sqlite_engine(url="sqlite:///:memory:")
    initialize_database(engine)
    return engine


@pytest.fixture(autouse=True)
def setup_test_db(test_db_engine, monkeypatch):
    """テスト用DBをグローバルに設定"""
    import infra.storage.rds

    # create_sqlite_engineをモックしてtest_db_engineを返すようにする
    def mock_create_engine(url=None, echo=False):
        return test_db_engine

    monkeypatch.setattr(infra.storage.rds, "create_sqlite_engine", mock_create_engine)


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
    from pathlib import Path

    common_dirs = ["/tmp", "/data"]
    for dir_path in common_dirs:
        if not fs.exists(dir_path):
            fs.create_dir(dir_path)

    # mockディレクトリを実ファイルシステムから仮想FSにマップ
    project_root = Path(__file__).parent.parent
    mock_dir = project_root / "mock"
    if mock_dir.exists():
        fs.add_real_directory(mock_dir, read_only=True)
