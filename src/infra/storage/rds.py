"""RDS(SQLite)接続まわりのユーティリティ関数群"""

import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypeVar

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from infra.logger import get_logger

T = TypeVar("T", bound=SQLModel)

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


def save_record(record: T, *, engine: Engine | None = None) -> T:
    """SQLModelレコードを保存し、最新状態を返す

    - session.merge でupsert
    - flush + refresh で最新状態を取得
    - トランザクション管理を自動化

    Args:
        record: 保存するSQLModelレコード
        engine: 使用するエンジン (Noneの場合はデフォルト)

    Returns:
        保存後の最新状態のレコード
    """
    with session_scope(engine) as session:
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        session.expunge(merged)  # セッションから切り離してDetachedにならないようにする
        return merged


def save_records(records: list[T], *, engine: Engine | None = None) -> list[T]:
    """複数のSQLModelレコードを一括保存し、最新状態のリストを返す

    Args:
        records: 保存するSQLModelレコードのリスト
        engine: 使用するエンジン (Noneの場合はデフォルト)

    Returns:
        保存後の最新状態のレコードリスト
    """
    if not records:
        return []

    with session_scope(engine) as session:
        results: list[T] = []
        for record in records:
            merged = session.merge(record)
            session.flush()
            session.refresh(merged)
            # セッションから切り離してDetachedにならないようにする
            session.expunge(merged)
            results.append(merged)
        return results


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

    def test_save_record_saves_and_returns_refreshed(self) -> None:
        """
        docs:
            目的:
                save_record が正しく保存し最新状態を返すことを確認する。
            検証観点:
                - レコードがDBに保存される
                - 返り値が最新状態 (flush + refresh 済み)
        """
        from datetime import datetime, timezone

        from infra.web.queue.model import RequestTaskRecord

        # テーブル作成（モデルimport後に実行が必要）
        initialize_database()

        # pytestにより自動的にインメモリDBが使用される
        record = RequestTaskRecord(
            id="test_id",
            url="https://example.com/test",
            description="Test Record",
            group="test:save",
            status_code=200,
            created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )

        saved = save_record(record)

        assert saved.id == record.id
        assert saved.description == "Test Record"
        assert saved.group == "test:save"

        # DBに保存されていることを確認
        with session_scope() as session:
            from sqlmodel import select

            statement = select(RequestTaskRecord).where(
                RequestTaskRecord.id == "test_id"
            )
            fetched = session.exec(statement).first()
            assert fetched is not None
            assert fetched.description == "Test Record"

    def test_save_records_saves_multiple_records(self) -> None:
        """
        docs:
            目的:
                save_records が複数レコードを一括保存できることを確認する。
            検証観点:
                - 全レコードが保存される
                - トランザクションが共有される
        """
        from datetime import datetime, timezone

        from infra.web.queue.model import RequestTaskRecord

        # テーブル作成（モデルimport後に実行が必要）
        initialize_database()

        # pytestにより自動的にインメモリDBが使用される
        base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        records = [
            RequestTaskRecord(
                id="test_id_1",
                url="https://example.com/1",
                description="Record 1",
                group="test:batch",
                status_code=200,
                created_at=base_time,
                updated_at=base_time,
            ),
            RequestTaskRecord(
                id="test_id_2",
                url="https://example.com/2",
                description="Record 2",
                group="test:batch",
                status_code=200,
                created_at=base_time,
                updated_at=base_time,
            ),
            RequestTaskRecord(
                id="test_id_3",
                url="https://example.com/3",
                description="Record 3",
                group="test:batch",
                status_code=200,
                created_at=base_time,
                updated_at=base_time,
            ),
        ]

        saved_records = save_records(records)

        expected_count = 3
        assert len(saved_records) == expected_count
        assert saved_records[0].id == "test_id_1"
        assert saved_records[1].id == "test_id_2"
        assert saved_records[2].id == "test_id_3"

        # DBに保存されていることを確認
        with session_scope() as session:
            from sqlmodel import select

            statement = select(RequestTaskRecord).where(
                RequestTaskRecord.group == "test:batch"
            )
            fetched = session.exec(statement).all()
            assert len(fetched) == expected_count

    def test_save_records_returns_empty_list_for_empty_input(self) -> None:
        """
        docs:
            目的:
                save_records が空リスト入力時に空リストを返すことを確認する。
            検証観点:
                - 空リスト入力で空リストが返る
                - エラーが発生しない
        """
        result = save_records([])
        assert result == []
