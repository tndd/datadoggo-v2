"""pytest共通フィクスチャ"""

from __future__ import annotations

from pathlib import Path

import pytest

from infra.app_log import configure_logging, reset_logging


@pytest.fixture
def app_logging(fs):
    """
    テスト用にloguruを仮想ファイルシステムへ設定する

    Note:
        pyfakefsの`fs` fixtureに依存するため、使用時は両方を指定する:
        def test_example(fs, app_logging): ...
    """

    log_path = Path("/logs/app.log")
    configure_logging(log_path=log_path, enqueue=False)
    yield log_path
    reset_logging()


@pytest.fixture(autouse=True)
def _auto_reset_test_db():
    """
    各テスト実行前に自動的にDBをリセットし、テーブルを初期化する

    Note:
        autouseのため全テストで実行されるが、実際にDBを使わないテストでは
        エンジン生成・テーブル作成が遅延実行されるためオーバーヘッドは最小限。
        テーブル作成はメモリDB上で軽量なので、全テスト実行でも問題ない。
    """
    from infra.storage.rds import initialize_database, reset_test_engine

    reset_test_engine()
    initialize_database()
