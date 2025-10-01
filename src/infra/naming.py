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
    normalized_extension = _normalize_extension(extension)
    return f"{base_name}{normalized_extension}"


def _normalize_extension(extension: str | None) -> str:
    """拡張子をプレフィックス付きの形式に整形する"""

    if not extension:
        return ""
    return extension if extension.startswith(".") else f".{extension}"
