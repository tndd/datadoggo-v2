"""ローカルファイルシステムにバイナリオブジェクトを保存・読み込むユーティリティ"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Union

from pyfakefs.fake_filesystem import FakeFilesystem

from src.infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    compress_bytes_to_zstd,
    compress_text_to_zstd,
    decompress_zstd_to_bytes,
    decompress_zstd_to_text,
    generate_timestamp,
    sanitize_storage_key,
)
from src.infra.logging import get_logger
from src.infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("data/bucket")
DEFAULT_OBJECT_EXTENSION = ".zst"
SHARD_PREFIX_LENGTH = 2
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH

_log = get_logger()


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
    as_text: bool = False,
    encoding: str = "utf-8",
) -> Union[bytes, str]:
    """保存済みオブジェクトを読み込む"""

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
            return "" if as_text else b""

        compressed_data = load_bytes(target_path)
        if not compressed_data:
            _log.warning(
                "圧縮データが空のため読み込みに失敗しました",
                bucket=bucket_name,
                object_key=object_key,
            )
            return "" if as_text else b""

        if as_text:
            result = decompress_zstd_to_text(compressed_data, encoding=encoding)
            text_bytes = len(result.encode(encoding))
            _log.info(
                "テキストオブジェクトを読み込みました",
                bucket=bucket_name,
                object_key=object_key,
                bytes=text_bytes,
            )
            return result
        result_bytes = decompress_zstd_to_bytes(compressed_data)
        _log.info(
            "バイナリオブジェクトを読み込みました",
            bucket=bucket_name,
            object_key=object_key,
            bytes=len(result_bytes),
        )
        return result_bytes
    except Exception as error:
        _log.exception(
            "オブジェクトの読み込みに失敗しました",
            bucket=bucket_name,
            object_key=object_key,
            error=str(error),
        )
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
        _log.exception(
            "オブジェクトキーの検索に失敗しました",
            bucket=bucket_name,
            prefix=prefix,
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


def _to_compressed_bytes(
    payload: Union[bytes, str], *, encoding: str = "utf-8"
) -> bytes:
    """入力データをZstandard圧縮済みバイト列に変換する"""

    if isinstance(payload, bytes):
        return compress_bytes_to_zstd(payload)
    return compress_text_to_zstd(payload, encoding=encoding)


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
    as_text: bool = False,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
) -> dict[str, Union[bytes, str]]:
    """複数のオブジェクトを並列取得する。keyごとに成功/失敗の結果を返す"""

    if not object_keys:
        return {}

    worker_count = _normalize_parallel(parallel, len(object_keys))

    # 逐次実行
    if worker_count <= 1:
        results: dict[str, Union[bytes, str]] = {}
        for key in object_keys:
            results[key] = load_object(
                bucket_name=bucket_name,
                object_key=key,
                storage_root=storage_root,
                as_text=as_text,
            )
        return results

    # 並列実行
    results_dict: dict[str, Union[bytes, str]] = {}

    def load_single(key: str) -> tuple[str, Union[bytes, str]]:
        content = load_object(
            bucket_name=bucket_name,
            object_key=key,
            storage_root=storage_root,
            as_text=as_text,
        )
        return (key, content)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(load_single, key): key for key in object_keys}

        for future in as_completed(futures):
            key, content = future.result()
            results_dict[key] = content

    return results_dict


class TestMod:
    def test_save_and_load_text(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: テキストを圧縮して保存し復元できることを確認する。
            検証観点:
                - save_object がテキスト入力を受け付ける。
                - load_object(as_text=True) で元テキストが復元できる。
        """

        text = "テキストデータの保存テスト"
        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

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

    def test_save_and_load_bytes(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: バイト列を圧縮して保存し復元できることを確認する。
            検証観点:
                - save_object がバイト列入力を受け付ける。
                - load_object(as_text=False) で元バイト列が復元できる。
        """

        payload = b"binary-data" * 4
        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

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

    def test_search_object_keys(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 保存済みオブジェクトの一覧取得を確認する。
            検証観点:
                - バケット内ファイルがキーとして検出される。
                - プレフィックス指定で絞り込みが行われる。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

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

    def test_error_handling(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 未保存データに対するエラーハンドリングを確認する。
            検証観点:
                - 存在しないキー読み込み時に空文字列を返す。
                - 存在しないバケット検索時に空リストを返す。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        result = load_object(
            "objects", "missing", storage_root=storage_root, as_text=True
        )
        assert result == ""

        keys = search_object_keys("objects", storage_root=storage_root)
        assert keys == []

    def test_load_objects_returns_multiple_objects(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 複数のオブジェクトを一括取得できることを確認する。
            検証観点:
                - 複数のkeyを指定して対応するオブジェクトが取得できる。
                - 返り値がdict[str, Union[bytes, str]]である。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        # 複数オブジェクトを保存
        test_keys = ["key1", "key2", "key3"]
        save_object("content1", "test", "key1", storage_root=storage_root)
        save_object("content2", "test", "key2", storage_root=storage_root)
        save_object("content3", "test", "key3", storage_root=storage_root)

        # 一括取得
        results = load_objects(
            "test", test_keys, storage_root=storage_root, as_text=True
        )

        assert len(results) == len(test_keys)
        assert results["key1"] == "content1"
        assert results["key2"] == "content2"
        assert results["key3"] == "content3"

    def test_load_objects_handles_missing_keys(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 一部のkeyが存在しない場合、空文字列が返ることを確認する。
            検証観点:
                - 存在しないkeyには空文字列（as_text=True時）が設定される。
                - 存在するkeyは正常に取得できる。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        # 一部のみ保存
        save_object("exists", "test", "exists", storage_root=storage_root)

        # 存在するkey/しないkeyを混在させて取得
        test_keys = ["exists", "missing"]
        results = load_objects(
            "test", test_keys, storage_root=storage_root, as_text=True
        )

        assert len(results) == len(test_keys)
        assert results["exists"] == "exists"
        assert results["missing"] == ""

    def test_load_objects_returns_empty_dict_for_empty_list(
        self, fs: FakeFilesystem
    ) -> None:
        """
        docs:
            目的: 空リストを渡した場合、空dictが返ることを確認する。
            検証観点:
                - object_keys=[] で空dictが返る。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        results = load_objects("test", [], storage_root=storage_root, as_text=True)
        assert results == {}
