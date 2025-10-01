"""infra.storage.rds のテスト"""

from infra.storage.rds import _ensure_sqlite_directory


def test_ensure_sqlite_directory_creates_parent(fs) -> None:
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

    # 相対パス(カレントディレクトリ基準)
    _ensure_sqlite_directory("sqlite:///relative/path/test.db")
    assert fs.exists("relative/path")
