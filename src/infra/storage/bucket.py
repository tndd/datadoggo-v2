"""ローカルファイルシステムにバイナリオブジェクトを保存・読み込むユーティリティ"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from src.infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    compress_text_to_zstd,
    decompress_zstd_to_text,
    generate_timestamp,
    sanitize_storage_key,
)
from src.infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("storage/data")
SHARD_PREFIX_LENGTH = 2
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH


@dataclass(frozen=True)
class LocalStorageOptions:
    """ローカルストレージ保存時のオプション設定"""

    storage_root: Path | str = DEFAULT_STORAGE_ROOT
    prefix: str = "content"
    object_extension: str = ".zst"


def save_object_bytes(
    payload: bytes,
    bucket_name: str,
    *,
    object_key: Optional[str] = None,
    source_identifier: Optional[str] = None,
    options: Optional[LocalStorageOptions] = None,
) -> str:
    """バイト列をローカルファイルに保存する"""

    try:
        opts = options or LocalStorageOptions()

        resolved_key = _resolve_storage_key(object_key, source_identifier, opts.prefix)
        target_path = _build_object_path(
            bucket_name, resolved_key, opts.storage_root, opts.object_extension
        )

        save_bytes_to_file(payload, target_path)
        print(f"\nオブジェクトを {target_path} に保存しました。")
        return resolved_key
    except Exception as error:
        print(f"オブジェクト保存エラー: {error}")
        return ""


def save_text_content(
    content: str,
    bucket_name: str,
    *,
    object_key: Optional[str] = None,
    source_identifier: Optional[str] = None,
    options: Optional[LocalStorageOptions] = None,
) -> str:
    """テキストを圧縮して保存するためのヘルパー"""

    compressed = compress_text_to_zstd(content)
    return save_object_bytes(
        compressed,
        bucket_name,
        object_key=object_key,
        source_identifier=source_identifier,
        options=options,
    )


def load_object_bytes(
    bucket_name: str,
    object_key: str,
    *,
    options: Optional[LocalStorageOptions] = None,
) -> bytes:
    """ローカルファイルからバイナリを読み込む"""

    try:
        opts = options or LocalStorageOptions()
        target_path = _build_object_path(
            bucket_name, object_key, opts.storage_root, opts.object_extension
        )

        if not target_path.exists():
            print(f"オブジェクトが見つかりません: {target_path}")
            return b""

        compressed_data = load_bytes(target_path)
        return compressed_data
    except Exception as error:
        print(f"オブジェクト読み込みエラー: {error}")
        return b""


def load_text_content(
    bucket_name: str,
    object_key: str,
    *,
    options: Optional[LocalStorageOptions] = None,
) -> str:
    """圧縮済みテキストを読み込み復元するヘルパー"""

    data = load_object_bytes(bucket_name, object_key, options=options)
    if not data:
        return ""
    return decompress_zstd_to_text(data)


def search_object_keys(
    bucket_name: str,
    prefix: str = "",
    *,
    options: Optional[LocalStorageOptions] = None,
) -> list[str]:
    """指定バケット内のオブジェクトキー一覧を取得する"""

    try:
        opts = options or LocalStorageOptions()
        bucket_dir = _resolve_bucket_dir(bucket_name, opts.storage_root)
        if not bucket_dir.exists():
            return []

        keys: list[str] = []
        for file_path in _iter_object_files(bucket_dir, opts.object_extension):
            key = _extract_key_from_path(file_path, opts.object_extension)
            if prefix and not key.startswith(prefix):
                continue
            keys.append(key)
        return keys
    except Exception as error:
        print(f"オブジェクト検索エラー: {error}")
        return []


def _resolve_storage_key(
    object_key: Optional[str],
    source_identifier: Optional[str],
    prefix: str,
) -> str:
    """保存用オブジェクトキーを決定する"""

    candidate = object_key or source_identifier
    if candidate:
        return sanitize_storage_key(candidate, max_length=MAX_SAFE_KEY_LENGTH)

    timestamp = generate_timestamp()
    return f"{prefix}_{timestamp}"


def _build_object_path(
    bucket_name: str,
    object_key: str,
    storage_root: Path | str,
    object_extension: str,
) -> Path:
    """オブジェクトキーから保存先パスを構築する"""

    root = Path(storage_root)
    shard = object_key[:SHARD_PREFIX_LENGTH] or "00"
    normalized_extension = _normalize_extension(object_extension)
    file_name = (
        f"{object_key}{normalized_extension}"
        if not object_key.endswith(normalized_extension)
        else object_key
    )

    return root / bucket_name / shard / file_name


def _resolve_bucket_dir(bucket_name: str, storage_root: Path | str) -> Path:
    """バケットディレクトリを解決する"""

    return Path(storage_root) / bucket_name


def _iter_object_files(bucket_dir: Path, object_extension: str) -> Iterable[Path]:
    """バケット配下のオブジェクトファイルを列挙する"""

    normalized_extension = _normalize_extension(object_extension)
    return bucket_dir.rglob(f"*{normalized_extension}")


def _extract_key_from_path(file_path: Path, object_extension: str) -> str:
    """ファイル名からオブジェクトキーを取り出す"""

    name = file_path.name
    normalized_extension = _normalize_extension(object_extension)
    if name.endswith(normalized_extension):
        return name[: -len(normalized_extension)]
    return name


def _normalize_extension(object_extension: str) -> str:
    """先頭にドットを付与した拡張子表記を返す"""

    if object_extension.startswith("."):
        return object_extension
    return f".{object_extension}"


class Tests:
    def test_save_and_load_text_content(self, tmp_path: Path) -> None:
        """
        docs:
            目的: テキストを圧縮して保存し復元できることを確認する。
            検証観点:
                - 圧縮ユーティリティを利用して保存できる。
                - 保存したキーを用いて元テキストが復元できる。
        """

        text = "テキストデータの保存テスト"
        storage_root = tmp_path / "storage" / "data"
        options = LocalStorageOptions(storage_root=storage_root)

        key = save_text_content(text, bucket_name="objects", options=options)
        assert key != ""
        saved_path = _build_object_path(
            "objects", key, storage_root, options.object_extension
        )
        assert saved_path.exists()

        loaded = load_text_content("objects", key, options=options)
        assert loaded == text

    def test_search_object_keys(self, tmp_path: Path) -> None:
        """
        docs:
            目的: 保存済みオブジェクトの一覧取得を確認する。
            検証観点:
                - バケット内ファイルがキーとして検出される。
                - プレフィックス指定で絞り込みが行われる。
        """

        storage_root = tmp_path / "storage"
        options = LocalStorageOptions(storage_root=storage_root)

        compressed = compress_text_to_zstd("obj1")
        key1 = save_object_bytes(
            compressed,
            bucket_name="objects",
            source_identifier="id-a",
            options=options,
        )
        key2 = save_object_bytes(
            compress_text_to_zstd("obj2"),
            bucket_name="objects",
            source_identifier="id-b",
            options=options,
        )

        keys = search_object_keys("objects", options=options)
        assert set(keys) == {key1, key2}

        filtered = search_object_keys("objects", prefix=key1, options=options)
        assert filtered == [key1]

    def test_error_handling(self, tmp_path: Path) -> None:
        """
        docs:
            目的: 未保存データに対するエラーハンドリングを確認する。
            検証観点:
                - 存在しないキー読み込み時に空文字列を返す。
                - 存在しないバケット検索時に空リストを返す。
        """

        storage_root = tmp_path / "storage"
        options = LocalStorageOptions(storage_root=storage_root)

        result = load_text_content("objects", "missing", options=options)
        assert result == ""

        keys = search_object_keys("objects", options=options)
        assert keys == []
