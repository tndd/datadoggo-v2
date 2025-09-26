"""ローカルファイルシステムにバイナリオブジェクトを保存・読み込むユーティリティ"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from src.infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    compress_bytes_to_zstd,
    compress_text_to_zstd,
    decompress_zstd_to_bytes,
    decompress_zstd_to_text,
    generate_timestamp,
    sanitize_storage_key,
)
from src.infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("data/bucket")
DEFAULT_OBJECT_EXTENSION = ".zst"
SHARD_PREFIX_LENGTH = 2
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH


def save_object(
    payload: Union[bytes, str],
    bucket_name: str,
    object_key: str,
    *,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
) -> str:
    """オブジェクトを圧縮して保存する"""

    try:
        resolved_key = _resolve_storage_key(object_key)
        target_path = _build_object_path(
            bucket_name, resolved_key, storage_root, DEFAULT_OBJECT_EXTENSION
        )

        payload_bytes = _to_compressed_bytes(payload, encoding=encoding)
        save_bytes_to_file(payload_bytes, target_path)
        print(f"\nオブジェクトを {target_path} に保存しました。")
        return resolved_key
    except Exception as error:
        print(f"オブジェクト保存エラー: {error}")
        return ""


def load_object(
    bucket_name: str,
    object_key: str,
    *,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
    as_text: bool = False,
    encoding: str = "utf-8",
) -> Union[bytes, str]:
    """保存済みオブジェクトを読み込む"""

    try:
        target_path = _build_object_path(
            bucket_name, object_key, storage_root, DEFAULT_OBJECT_EXTENSION
        )

        if not target_path.exists():
            print(f"オブジェクトが見つかりません: {target_path}")
            return "" if as_text else b""

        compressed_data = load_bytes(target_path)
        if not compressed_data:
            return "" if as_text else b""

        if as_text:
            return decompress_zstd_to_text(compressed_data, encoding=encoding)
        return decompress_zstd_to_bytes(compressed_data)
    except Exception as error:
        print(f"オブジェクト読み込みエラー: {error}")
        return "" if as_text else b""


def search_object_keys(
    bucket_name: str,
    prefix: str = "",
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
            if prefix and not key.startswith(prefix):
                continue
            keys.append(key)
        return keys
    except Exception as error:
        print(f"オブジェクト検索エラー: {error}")
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


def _to_compressed_bytes(
    payload: Union[bytes, str], *, encoding: str = "utf-8"
) -> bytes:
    """入力データをZstandard圧縮済みバイト列に変換する"""

    if isinstance(payload, bytes):
        return compress_bytes_to_zstd(payload)
    return compress_text_to_zstd(payload, encoding=encoding)


class Tests:
    def test_save_and_load_text(self, tmp_path: Path) -> None:
        """
        docs:
            目的: テキストを圧縮して保存し復元できることを確認する。
            検証観点:
                - save_object がテキスト入力を受け付ける。
                - load_object(as_text=True) で元テキストが復元できる。
        """

        text = "テキストデータの保存テスト"
        storage_root = tmp_path / "data" / "bucket"

        key = save_object(
            text,
            bucket_name="objects",
            object_key="test_key",
            storage_root=storage_root,
        )
        assert key != ""
        saved_path = _build_object_path(
            "objects", key, storage_root, DEFAULT_OBJECT_EXTENSION
        )
        assert saved_path.exists()

        loaded = load_object("objects", key, storage_root=storage_root, as_text=True)
        assert loaded == text

    def test_save_and_load_bytes(self, tmp_path: Path) -> None:
        """
        docs:
            目的: バイト列を圧縮して保存し復元できることを確認する。
            検証観点:
                - save_object がバイト列入力を受け付ける。
                - load_object(as_text=False) で元バイト列が復元できる。
        """

        payload = b"binary-data" * 4
        storage_root = tmp_path / "data" / "bucket"

        key = save_object(
            payload,
            bucket_name="bin",
            object_key="bytes",
            storage_root=storage_root,
        )
        assert key == "bytes"

        loaded = load_object("bin", key, storage_root=storage_root)
        assert isinstance(loaded, bytes)
        assert loaded == payload

    def test_search_object_keys(self, tmp_path: Path) -> None:
        """
        docs:
            目的: 保存済みオブジェクトの一覧取得を確認する。
            検証観点:
                - バケット内ファイルがキーとして検出される。
                - プレフィックス指定で絞り込みが行われる。
        """

        storage_root = tmp_path / "data" / "bucket"

        key1 = save_object(
            "obj1",
            bucket_name="objects",
            object_key="id-a",
            storage_root=storage_root,
        )
        key2 = save_object(
            "obj2",
            bucket_name="objects",
            object_key="id-b",
            storage_root=storage_root,
        )

        keys = search_object_keys("objects", storage_root=storage_root)
        assert set(keys) == {key1, key2}

        filtered = search_object_keys("objects", prefix=key1, storage_root=storage_root)
        assert filtered == [key1]

    def test_error_handling(self, tmp_path: Path) -> None:
        """
        docs:
            目的: 未保存データに対するエラーハンドリングを確認する。
            検証観点:
                - 存在しないキー読み込み時に空文字列を返す。
                - 存在しないバケット検索時に空リストを返す。
        """

        storage_root = tmp_path / "data" / "bucket"

        result = load_object(
            "objects", "missing", storage_root=storage_root, as_text=True
        )
        assert result == ""

        keys = search_object_keys("objects", storage_root=storage_root)
        assert keys == []
