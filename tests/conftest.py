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
def real_project_root() -> Path:
    """実ファイルシステム上のプロジェクトルートを返す（mockディレクトリアクセス用）"""
    return Path(__file__).parent.parent


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
    from contextlib import contextmanager
    from typing import Iterator
    from sqlmodel import Session, SQLModel

    # 各テスト前にテーブルをクリーンアップ
    SQLModel.metadata.drop_all(test_db_engine)
    SQLModel.metadata.create_all(test_db_engine)

    # create_sqlite_engineをモックしてtest_db_engineを返すようにする
    def mock_create_engine(url=None, echo=False):
        return test_db_engine

    # session_scopeもモックして常にtest_db_engineを使う
    @contextmanager
    def mock_session_scope(engine=None) -> Iterator[Session]:
        session = Session(test_db_engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(infra.storage.rds, "create_sqlite_engine", mock_create_engine)
    monkeypatch.setattr(infra.storage.rds, "session_scope", mock_session_scope)


@pytest.fixture
def project_root(fs: FakeFilesystem) -> Path:
    """プロジェクトルートディレクトリを仮想FS上に作成して返す"""
    root = Path("/project")
    if not fs.exists(str(root)):
        fs.create_dir(str(root))
    return root


@pytest.fixture(autouse=True)
def setup_common_dirs(request, fs: FakeFilesystem, real_project_root: Path):
    """テストで頻繁に使用されるディレクトリを事前作成"""
    # fs fixtureを使わないテストはスキップ
    if "no_fs" in request.keywords:
        return

    common_dirs = ["/tmp", "/data", str(real_project_root)]
    for dir_path in common_dirs:
        if not fs.exists(dir_path):
            fs.create_dir(dir_path)

    # src/infra/storage/file.pyをマップ（_find_project_root検索用）
    file_py = real_project_root / "src" / "infra" / "storage" / "file.py"
    if file_py.exists():
        fs.add_real_file(file_py, read_only=True)

    # pyproject.tomlをマップしてプロジェクトルート検索を可能にする
    pyproject_file = real_project_root / "pyproject.toml"
    if pyproject_file.exists():
        fs.add_real_file(pyproject_file, read_only=True)

    # mockディレクトリを実ファイルシステムから仮想FSにマップ
    mock_dir = real_project_root / "mock"
    if mock_dir.exists():
        fs.add_real_directory(mock_dir, read_only=True)

    # デフォルトの作業ディレクトリをプロジェクトルートに設定
    import os
    os.chdir(str(real_project_root))
