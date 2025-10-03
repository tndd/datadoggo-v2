"""タイムスタンプベースの命名ユーティリティ"""

from datetime import datetime
from pathlib import Path


def generate_timestamp() -> str:
    """現在時刻からタイムスタンプ文字列を生成する (YYYYMMDD_HHMMSS)"""

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_timestamped_filename(
    *,
    prefix: str | None = None,
    suffix: str | None = None,
    extension: str | None = None,
    output_dir: str | Path | None = None,
    separator: str = "_",
) -> str:
    """タイムスタンプと任意要素を組み合わせたファイルパスを生成する"""

    filename = _compose_timestamped_name(
        prefix=prefix, suffix=suffix, extension=extension, separator=separator
    )
    if output_dir is None:
        return filename
    return str(Path(output_dir) / filename)


def generate_timestamped_key(
    *,
    prefix: str | None = None,
    suffix: str | None = None,
    extension: str | None = None,
    separator: str = "_",
) -> str:
    """タイムスタンプを含むストレージキーを生成する"""

    return _compose_timestamped_name(
        prefix=prefix, suffix=suffix, extension=extension, separator=separator
    )


def _compose_timestamped_name(
    *,
    prefix: str | None,
    suffix: str | None,
    extension: str | None,
    separator: str,
) -> str:
    """タイムスタンプとオプション要素を結合して一意な名前を作る"""

    timestamp = generate_timestamp()
    elements = [prefix, timestamp, suffix]
    parts = [part for part in elements if part]
    if not parts:
        parts = [timestamp]

    base_name = separator.join(parts)
    if not extension:
        normalized_extension = ""
    elif extension.startswith("."):
        normalized_extension = extension
    else:
        normalized_extension = f".{extension}"
    return f"{base_name}{normalized_extension}"


class TestMod:
    def test_generate_timestamp(self) -> None:
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

    def test_generate_timestamped_filename(self) -> None:
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

    def test_generate_timestamped_key(self) -> None:
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
