"""ローカルファイルシステムに文字列オブジェクトを圧縮保存・読み込むユーティリティ"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from infra.app_log import get_logger
from infra.compute import (
    compress_text_to_zstd,
    decompress_zstd_to_text,
    hash_text_sha256,
)
from infra.generate import generate_timestamp
from infra.runtime import get_worker_count
from infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("data/bucket")
DEFAULT_OBJECT_EXTENSION = ".zst"
SHARD_PREFIX_LENGTH = 2

# ストレージキー検証関連の定数
SAFE_STORAGE_KEY_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
DEFAULT_MAX_STORAGE_KEY_LENGTH = 128
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH
SHA256_HEX_LENGTH = 64

_log = get_logger()


def is_safe_storage_key(
    value: str,
    *,
    max_length: int = DEFAULT_MAX_STORAGE_KEY_LENGTH,
) -> bool:
    """ファイルシステムで安全に扱えるキーかを判定する"""

    if not value or len(value) > max_length:
        return False

    return all(char in SAFE_STORAGE_KEY_ALLOWED_CHARS for char in value)


def sanitize_storage_key(
    value: str,
    *,
    max_length: int = DEFAULT_MAX_STORAGE_KEY_LENGTH,
) -> str:
    """ストレージキーを安全な形式に正規化する"""

    normalized = value.strip()
    if is_safe_storage_key(normalized, max_length=max_length):
        return normalized

    return hash_text_sha256(normalized)


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

    worker_count = get_worker_count(parallel)

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


class TestMod:
    def test_is_safe_storage_key(self) -> None:
        """
        docs:
            目的: is_safe_storage_key の判定ロジックを確認する。
            検証観点:
                - 許可文字のみかつ長さ内のキーがTrueになる。
                - 禁止文字や長過ぎるキーはFalseになる。
        """

        assert is_safe_storage_key("abc-123")
        assert not is_safe_storage_key("abc/123")
        assert not is_safe_storage_key("", max_length=5)
        assert not is_safe_storage_key("a" * (DEFAULT_MAX_STORAGE_KEY_LENGTH + 1))

    def test_sanitize_storage_key(self) -> None:
        """
        docs:
            目的: sanitize_storage_key の正規化挙動を確認する。
            検証観点:
                - 安全なキーは入力をそのまま返す。
                - 危険なキーはハッシュ化された値を返す。
        """

        assert sanitize_storage_key(" safe_key ") == "safe_key"
        hashed = sanitize_storage_key("https://example.com/path?id=1")
        assert len(hashed) == SHA256_HEX_LENGTH

    def test_save_and_load_text(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: テキストを圧縮して保存し復元できることを確認する。
            検証観点:
                - save_object がテキスト入力を受け付ける。
                - load_object で元テキストが復元できる。
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

        loaded = load_object("objects", key, storage_root=storage_root)
        assert loaded == text

    def test_search_object_keys(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 保存済みオブジェクトの一覧取得を確認する。
            検証観点:
                - バケット内ファイルがキーとして検出される。
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

    def test_error_handling(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 未保存データに対するエラーハンドリングを確認する。
            検証観点:
                - 存在しないキー読み込み時にNoneを返す。
                - 存在しないバケット検索時に空リストを返す。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        result = load_object("objects", "missing", storage_root=storage_root)
        assert result is None

        keys = search_object_keys("objects", storage_root=storage_root)
        assert keys == []

    def test_load_objects_returns_multiple_objects(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 複数のオブジェクトを一括取得できることを確認する。
            検証観点:
                - 複数のkeyを指定して対応するオブジェクトが取得できる。
                - 返り値がdict[str, str | None]である。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        # 複数オブジェクトを保存
        test_keys = ["key1", "key2", "key3"]
        save_object("content1", "test", "key1", storage_root=storage_root)
        save_object("content2", "test", "key2", storage_root=storage_root)
        save_object("content3", "test", "key3", storage_root=storage_root)

        # 一括取得
        results = load_objects("test", test_keys, storage_root=storage_root)

        assert len(results) == len(test_keys)
        assert results["key1"] == "content1"
        assert results["key2"] == "content2"
        assert results["key3"] == "content3"

    def test_load_objects_handles_missing_keys(self, fs: FakeFilesystem) -> None:
        """
        docs:
            目的: 一部のkeyが存在しない場合、Noneが返ることを確認する。
            検証観点:
                - 存在しないkeyにはNoneが設定される。
                - 存在するkeyは正常に取得できる。
        """

        fs.create_dir("/data")
        storage_root = Path("/data/bucket")

        # 一部のみ保存
        save_object("exists", "test", "exists", storage_root=storage_root)

        # 存在するkey/しないkeyを混在させて取得
        test_keys = ["exists", "missing"]
        results = load_objects("test", test_keys, storage_root=storage_root)

        assert len(results) == len(test_keys)
        assert results["exists"] == "exists"
        assert results["missing"] is None

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

        results = load_objects("test", [], storage_root=storage_root)
        assert results == {}
