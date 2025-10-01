"""タイムスタンプベースの命名ユーティリティのテスト"""

from pathlib import Path

from infra.naming import (
    generate_timestamp,
    generate_timestamped_filename,
    generate_timestamped_key,
)


def test_generate_timestamp() -> None:
    """
    docs:
        目的: タイムスタンプ生成の正常性を確認する。
        検証観点:
            - YYYYMMDD_HHMMSS形式で生成される。
            - 15文字の長さである。
    """
    timestamp = generate_timestamp()
    TIMESTAMP_LENGTH = 15  # YYYYMMDD_HHMMSS
    assert len(timestamp) == TIMESTAMP_LENGTH
    assert "_" in timestamp
    # 基本的な日付形式チェック
    assert timestamp[:8].isdigit()  # YYYYMMDD
    assert timestamp[9:].isdigit()  # HHMMSS


def test_generate_timestamped_filename() -> None:
    """
    docs:
        目的: タイムスタンプ付きファイル名生成の正常性を確認する。
        検証観点:
            - プレフィックス、サフィックス、拡張子が正しく反映される。
            - ディレクトリパスが正しく結合される。
    """
    # デフォルト: タイムスタンプのみ
    filename = generate_timestamped_filename()
    assert Path(filename).parent == Path(".")
    assert Path(filename).suffix == ""

    # カスタム設定
    filename = generate_timestamped_filename(
        prefix="test",
        suffix="data",
        extension="html",
        output_dir="output",
    )
    assert filename.startswith("output/test_")
    assert "data" in Path(filename).stem
    assert filename.endswith(".html")


def test_generate_timestamped_key() -> None:
    """
    docs:
        目的: タイムスタンプ付きオブジェクトキー生成の正常性を確認する。
        検証観点:
            - プレフィックス、サフィックス、拡張子が正しく反映される。
            - パス区切り文字が含まれない。
    """
    # デフォルト: タイムスタンプのみ
    key = generate_timestamped_key()
    assert "/" not in key
    assert key.count("_") == 1  # YYYYMMDD_HHMMSS

    # カスタム設定
    key = generate_timestamped_key(
        prefix="scrape",
        suffix="page",
        extension="json.gz",
    )
    assert key.startswith("scrape_")
    assert "page" in key
    assert key.endswith(".json.gz")
