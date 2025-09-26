"""RDS(SQLite)接続まわりのユーティリティ関数群"""

import os
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///data/feed.db"
DATABASE_ENV_VAR = "FEED_DATABASE_URL"


def get_database_url() -> str:
    """環境変数から接続URLを取得する。未設定時はデフォルトのSQLiteファイルを用いる"""

    return os.getenv(DATABASE_ENV_VAR, DEFAULT_DATABASE_URL)


def create_sqlite_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """SQLite向けのSQLAlchemyエンジンを生成する"""

    database_url = url or get_database_url()
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
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database(engine: Engine | None = None) -> None:
    """SQLModelのメタデータを用いてテーブルを作成する"""

    target_engine = engine or create_sqlite_engine()
    SQLModel.metadata.create_all(target_engine)
