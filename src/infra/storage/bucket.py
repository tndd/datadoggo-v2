"""ローカルファイルシステムにHTMLコンテンツを保存・読み込みするユーティリティ"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import zstandard as zstd

from src.infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    generate_timestamp,
    sanitize_storage_key,
)
from src.infra.storage.file import load_bytes, save_bytes_to_file

DEFAULT_STORAGE_ROOT = Path("storage/data")
DEFAULT_BUCKET_NAME = "html"
SHARD_PREFIX_LENGTH = 2
HTML_OBJECT_EXTENSION = ".html.zst"
MAX_SAFE_KEY_LENGTH = DEFAULT_MAX_STORAGE_KEY_LENGTH


@dataclass(frozen=True)
class LocalStorageOptions:
    """ローカルストレージ保存時のオプション設定"""

    storage_root: Path | str = DEFAULT_STORAGE_ROOT
    prefix: str = "content"
    compression_level: int = 3


def save_html_content(
    content: str,
    bucket_name: str = DEFAULT_BUCKET_NAME,
    *,
    object_key: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[LocalStorageOptions] = None,
) -> str:
    """HTMLコンテンツをzstd圧縮してローカルファイルに保存する"""

    try:
        opts = options or LocalStorageOptions()

        resolved_key = _resolve_storage_key(object_key, source_url, opts.prefix)
        target_path = _build_object_path(bucket_name, resolved_key, opts.storage_root)

        compressor = zstd.ZstdCompressor(level=opts.compression_level)
        compressed_data = compressor.compress(content.encode("utf-8"))

        save_bytes_to_file(compressed_data, target_path)
        print(f"\nHTMLコンテンツを {target_path} に保存しました。")
        return resolved_key
    except Exception as error:
        print(f"HTML保存エラー: {error}")
        return ""


def load_html_content(
    bucket_name: str,
    object_key: str,
    *,
    options: Optional[LocalStorageOptions] = None,
) -> str:
    """ローカルファイルからzstd圧縮されたHTMLコンテンツを読み込む"""

    try:
        opts = options or LocalStorageOptions()
        target_path = _build_object_path(bucket_name, object_key, opts.storage_root)

        if not target_path.exists():
            print(f"HTMLファイルが見つかりません: {target_path}")
            return ""

        compressed_data = load_bytes(target_path)
        if not compressed_data:
            return ""

        decompressor = zstd.ZstdDecompressor()
        decompressed_data = decompressor.decompress(compressed_data)
        return decompressed_data.decode("utf-8")
    except Exception as error:
        print(f"HTML読み込みエラー: {error}")
        return ""


def search_html_objects(
    bucket_name: str,
    prefix: str = "",
    *,
    options: Optional[LocalStorageOptions] = None,
) -> list[str]:
    """指定バケット内のHTMLオブジェクト一覧を取得する"""

    try:
        opts = options or LocalStorageOptions()
        bucket_dir = _resolve_bucket_dir(bucket_name, opts.storage_root)
        if not bucket_dir.exists():
            return []

        keys: list[str] = []
        for file_path in _iter_object_files(bucket_dir):
            key = _extract_key_from_path(file_path)
            if prefix and not key.startswith(prefix):
                continue
            keys.append(key)
        return keys
    except Exception as error:
        print(f"HTMLオブジェクト検索エラー: {error}")
        return []


def _resolve_storage_key(
    object_key: Optional[str],
    source_url: Optional[str],
    prefix: str,
) -> str:
    """保存用オブジェクトキーを決定する"""

    candidate = object_key or source_url
    if candidate:
        return sanitize_storage_key(candidate, max_length=MAX_SAFE_KEY_LENGTH)

    timestamp = generate_timestamp()
    return f"{prefix}_{timestamp}"


def _build_object_path(
    bucket_name: str,
    object_key: str,
    storage_root: Path | str,
) -> Path:
    """オブジェクトキーから保存先パスを構築する"""

    root = Path(storage_root)
    shard = object_key[:SHARD_PREFIX_LENGTH] or "00"
    file_name = (
        f"{object_key}{HTML_OBJECT_EXTENSION}"
        if not object_key.endswith(HTML_OBJECT_EXTENSION)
        else object_key
    )

    return root / bucket_name / shard / file_name


def _resolve_bucket_dir(bucket_name: str, storage_root: Path | str) -> Path:
    """バケットディレクトリを解決する"""

    return Path(storage_root) / bucket_name


def _iter_object_files(bucket_dir: Path) -> Iterable[Path]:
    """バケット配下のオブジェクトファイルを列挙する"""

    return bucket_dir.rglob(f"*{HTML_OBJECT_EXTENSION}")


def _extract_key_from_path(file_path: Path) -> str:
    """ファイル名からオブジェクトキーを取り出す"""

    name = file_path.name
    if name.endswith(HTML_OBJECT_EXTENSION):
        return name[: -len(HTML_OBJECT_EXTENSION)]
    return name


class Tests:
    def test_save_and_load_html_content(self, tmp_path: Path) -> None:
        """
        docs:
            目的: HTML保存と読み込みの一連動作を確認する。
            検証観点:
                - コンテンツがzstd圧縮で保存される。
                - 保存したキーを用いて元HTMLが復元できる。
        """

        html = "<html><body><h1>テスト</h1></body></html>"
        storage_root = tmp_path / "storage" / "data"
        options = LocalStorageOptions(storage_root=storage_root)

        key = save_html_content(
            html,
            bucket_name="html",
            source_url="https://example.com/test",
            options=options,
        )
        assert key != ""
        saved_path = _build_object_path("html", key, storage_root)
        assert saved_path.exists()

        loaded = load_html_content("html", key, options=options)
        assert loaded == html

    def test_search_html_objects(self, tmp_path: Path) -> None:
        """
        docs:
            目的: 保存済みオブジェクトの一覧取得を確認する。
            検証観点:
                - バケット内ファイルがキーとして検出される。
                - プレフィックス指定で絞り込みが行われる。
        """

        html = "<html><body>Content</body></html>"
        storage_root = tmp_path / "storage"
        options = LocalStorageOptions(storage_root=storage_root)

        key1 = save_html_content(
            html,
            bucket_name="html",
            source_url="https://example.com/a",
            options=options,
        )
        key2 = save_html_content(
            html,
            bucket_name="html",
            source_url="https://example.com/b",
            options=options,
        )

        keys = search_html_objects("html", options=options)
        assert set(keys) == {key1, key2}

        filtered = search_html_objects("html", prefix=key1, options=options)
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

        result = load_html_content("html", "missing", options=options)
        assert result == ""

        keys = search_html_objects("html", options=options)
        assert keys == []
