"""RDS(SQLite)接続まわりのユーティリティ関数群"""

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from infra.logging import get_logger

DEFAULT_DATABASE_URL = "sqlite:///data/datadoggo.db"

LOG = get_logger()


def create_sqlite_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """SQLite向けのSQLAlchemyエンジンを生成する"""

    database_url = url or DEFAULT_DATABASE_URL
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
