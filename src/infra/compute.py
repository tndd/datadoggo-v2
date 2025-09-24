from datetime import datetime
from pathlib import Path


def generate_timestamp() -> str:
    """現在時刻からタイムスタンプ文字列を生成する (YYYYMMDD_HHMMSS)"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_timestamped_filename(
    prefix: str = "out",
    suffix: str = "",
    extension: str = "txt",
    output_dir: str = "mock",
) -> str:
    """タイムスタンプ付きファイルパスを生成する"""
    timestamp = generate_timestamp()
    filename_parts = [prefix, timestamp]

    if suffix:
        filename_parts.append(suffix)

    filename = "_".join(filename_parts) + f".{extension}"
    return str(Path(output_dir) / filename)


def generate_timestamped_key(
    prefix: str = "content",
    suffix: str = "",
    extension: str = "html.zst",
) -> str:
    """タイムスタンプ付きオブジェクトキーを生成する"""
    timestamp = generate_timestamp()
    key_parts = [prefix, timestamp]

    if suffix:
        key_parts.append(suffix)

    return "_".join(key_parts) + f".{extension}"


class Tests:
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
        # デフォルト
        filename = generate_timestamped_filename()
        assert filename.startswith("mock/out_")
        assert filename.endswith(".txt")

        # カスタム設定
        filename = generate_timestamped_filename(
            prefix="test", suffix="data", extension="html", output_dir="output"
        )
        assert filename.startswith("output/test_")
        assert "data" in filename
        assert filename.endswith(".html")

    def test_generate_timestamped_key(self) -> None:
        """
        docs:
            目的: タイムスタンプ付きオブジェクトキー生成の正常性を確認する。
            検証観点:
                - プレフィックス、サフィックス、拡張子が正しく反映される。
                - パス区切り文字が含まれない。
        """
        # デフォルト
        key = generate_timestamped_key()
        assert key.startswith("content_")
        assert key.endswith(".html.zst")
        assert "/" not in key

        # カスタム設定
        key = generate_timestamped_key(
            prefix="scrape", suffix="page", extension="json.gz"
        )
        assert key.startswith("scrape_")
        assert "page" in key
        assert key.endswith(".json.gz")
