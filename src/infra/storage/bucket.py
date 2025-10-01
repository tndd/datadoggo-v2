"""ローカルファイルシステムに文字列オブジェクトを圧縮保存・読み込むユーティリティ"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from infra.compression import compress_text_to_zstd, decompress_zstd_to_text
from infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    sanitize_storage_key,
)
from infra.logging import get_logger
from infra.naming import generate_timestamp
from infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("data/bucket")
DEFAULT_OBJECT_EXTENSION = ".zst"
SHARD_PREFIX_LENGTH = 2
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH

_log = get_logger()


def save_object(
    payload: str,
    bucket_name: str,
    object_key: str,
    *,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
) -> str:
    """文字列オブジェクトを圧縮して保存する"""

    try:
        resolved_key = _resolve_storage_key(object_key)
        target_path = _build_object_path(
            bucket_name, resolved_key, storage_root, DEFAULT_OBJECT_EXTENSION
        )

        payload_bytes = compress_text_to_zstd(payload, encoding=encoding)
        save_bytes_to_file(payload_bytes, target_path)
        _log.info(
            "オブジェクトを保存しました",
            bucket=bucket_name,
            object_key=resolved_key,
            path=str(target_path),
            bytes=len(payload_bytes),
        )
        return resolved_key
    except Exception as error:
        _log.exception(
            "オブジェクトの保存に失敗しました",
            bucket=bucket_name,
            object_key=object_key,
            error=str(error),
        )
        return ""


def load_object(
    bucket_name: str,
    object_key: str,
    *,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
) -> str | None:
    """保存済みオブジェクトを解凍して文字列として読み込む。失敗時はNoneを返す"""

    try:
        target_path = _build_object_path(
            bucket_name, object_key, storage_root, DEFAULT_OBJECT_EXTENSION
        )

        if not target_path.exists():
            _log.warning(
                "オブジェクトが見つかりません",
                bucket=bucket_name,
                object_key=object_key,
                path=str(target_path),
            )
            return None

        compressed_data = load_bytes(target_path)
        if not compressed_data:
            _log.warning(
                "圧縮データが空のため読み込みに失敗しました",
                bucket=bucket_name,
                object_key=object_key,
            )
            return None

        result = decompress_zstd_to_text(compressed_data, encoding=encoding)
        text_bytes = len(result.encode(encoding))
        _log.info(
            "テキストオブジェクトを読み込みました",
            bucket=bucket_name,
            object_key=object_key,
            bytes=text_bytes,
        )
        return result
    except Exception as error:
        _log.exception(
            "オブジェクトの読み込みに失敗しました",
            bucket=bucket_name,
            object_key=object_key,
            error=str(error),
        )
        return None


def search_object_keys(
    bucket_name: str,
    *,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
) -> list[str]:
    """指定バケット内のオブジェクトキー一覧を取得する"""

    try:
        bucket_dir = Path(storage_root) / bucket_name  # バケットのルートディレクトリ
        if not bucket_dir.exists():
            return []

        extension = DEFAULT_OBJECT_EXTENSION
        keys: list[str] = []
        for file_path in bucket_dir.rglob(f"*{extension}"):
            name = file_path.name
            key = name[: -len(extension)] if name.endswith(extension) else name
            keys.append(key)
        return keys
    except Exception as error:
        _log.exception(
            "オブジェクトキーの検索に失敗しました",
            bucket=bucket_name,
            error=str(error),
        )
        return []


def _resolve_storage_key(
    object_key: str,
) -> str:
    """保存用オブジェクトキーを決定する"""

    sanitized = sanitize_storage_key(object_key, max_length=MAX_SAFE_KEY_LENGTH)
    if sanitized:
        return sanitized

    timestamp = generate_timestamp()
    return f"auto_{timestamp}"


def _build_object_path(
    bucket_name: str,
    object_key: str,
    storage_root: Path | str,
    object_extension: str,
) -> Path:
    """オブジェクトキーから保存先パスを構築する"""

    root = Path(storage_root)
    shard = object_key[:SHARD_PREFIX_LENGTH] or "00"
    normalized_extension = (
        object_extension if object_extension.startswith(".") else f".{object_extension}"
    )
    file_name = (
        f"{object_key}{normalized_extension}"
        if not object_key.endswith(normalized_extension)
        else object_key
    )

    return root / bucket_name / shard / file_name


def _normalize_parallel(parallel: bool | int, item_count: int) -> int:
    """並列実行時のワーカー数を決定する"""

    if not parallel:
        return 1

    if parallel is True:
        return max(1, item_count)

    if isinstance(parallel, int):
        if parallel <= 1:
            return 1
        return min(parallel, item_count)

    return 1


def load_objects(
    bucket_name: str,
    object_keys: list[str],
    *,
    parallel: bool | int = False,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
) -> dict[str, str | None]:
    """複数のオブジェクトを並列取得する。失敗したkeyにはNoneを設定"""

    if not object_keys:
        return {}

    worker_count = _normalize_parallel(parallel, len(object_keys))

    # 逐次実行
    if worker_count <= 1:
        results: dict[str, str | None] = {}
        for key in object_keys:
            results[key] = load_object(
                bucket_name=bucket_name,
                object_key=key,
                storage_root=storage_root,
            )
        return results

    # 並列実行
    results_dict: dict[str, str | None] = {}

    def load_single(key: str) -> tuple[str, str | None]:
        content = load_object(
            bucket_name=bucket_name,
            object_key=key,
            storage_root=storage_root,
        )
        return (key, content)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(load_single, key): key for key in object_keys}

        for future in as_completed(futures):
            key, content = future.result()
            results_dict[key] = content

    return results_dict


