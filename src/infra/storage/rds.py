"""RDS(SQLite)接続まわりのユーティリティ関数群"""

import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from infra.app_log import get_logger

DEFAULT_DATABASE_URL = "sqlite:///data/datadoggo.db"

LOG = get_logger()

# pytest実行時にインメモリDBエンジンをキャッシュ（テスト内で同一インスタンスを共有）
_test_engine: Engine | None = None


def get_database_url() -> str:
    """
    データベースURLを取得する

    - pytest実行時: インメモリDB
    - それ以外: 本番DB (data/datadoggo.db)
    """

    if "pytest" in sys.modules:
        return "sqlite:///:memory:"

    return DEFAULT_DATABASE_URL


def create_sqlite_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """SQLite向けのSQLAlchemyエンジンを生成する"""

    global _test_engine  # noqa: PLW0603

    database_url = url or get_database_url()

    # pytest実行時かつ明示的なURL指定がない場合のみキャッシュを使用
    # （環境変数で別DBを指定する特殊なテストケースに対応）
    if "pytest" in sys.modules and url is None and database_url == "sqlite:///:memory:":
        if _test_engine is None:
            _test_engine = _create_engine(database_url, echo)
        return _test_engine

    return _create_engine(database_url, echo)


def _create_engine(database_url: str, echo: bool) -> Engine:
    """エンジンを実際に作成する内部関数"""

    _ensure_sqlite_directory(database_url)
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(database_url, echo=echo, connect_args=connect_args)


def get_session_factory(engine: Engine | None = None) -> Callable[[], Session]:
    """`Session`インスタンスを生成するファクトリ関数を返す"""

    target_engine = engine or create_sqlite_engine()

    def _factory() -> Session:
        return Session(target_engine)

    return _factory


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """トランザクション制御付きで`Session`を管理するコンテキストマネージャ"""

    target_engine = engine or create_sqlite_engine()
    session = Session(target_engine)
    try:
        yield session
        session.commit()
    except Exception as error:
        LOG.exception(
            "セッション処理中に例外が発生したためロールバックします",
            error=str(error),
        )
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database(engine: Engine | None = None) -> None:
    """SQLModelのメタデータを用いてテーブルを作成する"""

    target_engine = engine or create_sqlite_engine()
    SQLModel.metadata.create_all(target_engine)


def reset_test_engine() -> None:
    """テスト用エンジンキャッシュをクリアする（テスト分離用）"""

    global _test_engine  # noqa: PLW0603
    _test_engine = None


def _ensure_sqlite_directory(database_url: str) -> None:
    """SQLiteファイルの親ディレクトリを事前に作成する"""

    if not database_url.startswith("sqlite"):
        return

    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:":
        return

    db_path = Path(database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)


class TestMod:
    def test_ensure_sqlite_directory_creates_parent(self, fs) -> None:
        """
        docs:
            目的:
                SQLiteファイル保存時に親ディレクトリが自動生成されることを確認する。
            検証観点:
                - _ensure_sqlite_directory が存在しないディレクトリを作成する。
                - 相対パスも絶対パスも正しく処理される。
        """

        # 絶対パス
        _ensure_sqlite_directory("sqlite:////test/dir/test.db")
        assert fs.exists("/test/dir")

        # 相対パス（カレントディレクトリ基準）
        _ensure_sqlite_directory("sqlite:///relative/path/test.db")
        assert fs.exists("relative/path")
