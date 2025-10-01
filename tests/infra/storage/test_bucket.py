"""infra.storage.bucket のテスト"""

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from infra.storage.bucket import (
    DEFAULT_OBJECT_EXTENSION,
    _build_object_path,
    load_object,
    load_objects,
    save_object,
    search_object_keys,
)


def test_save_and_load_text(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: テキストを圧縮して保存し復元できることを確認する。
        検証観点:
            - save_object がテキスト入力を受け付ける。
            - load_object で元テキストが復元できる。
    """

    text = "テキストデータの保存テスト"
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


def test_search_object_keys(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 保存済みオブジェクトの一覧取得を確認する。
        検証観点:
            - バケット内ファイルがキーとして検出される。
    """

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


def test_error_handling(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 未保存データに対するエラーハンドリングを確認する。
        検証観点:
            - 存在しないキー読み込み時にNoneを返す。
            - 存在しないバケット検索時に空リストを返す。
    """

    storage_root = Path("/data/bucket")

    result = load_object("objects", "missing", storage_root=storage_root)
    assert result is None

    keys = search_object_keys("objects", storage_root=storage_root)
    assert keys == []


def test_load_objects_returns_multiple_objects(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 複数のオブジェクトを一括取得できることを確認する。
        検証観点:
            - 複数のkeyを指定して対応するオブジェクトが取得できる。
            - 返り値がdict[str, str | None]である。
    """

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


def test_load_objects_handles_missing_keys(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: 一部のkeyが存在しない場合、Noneが返ることを確認する。
        検証観点:
            - 存在しないkeyにはNoneが設定される。
            - 存在するkeyは正常に取得できる。
    """

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
    fs: FakeFilesystem,
) -> None:
    """
    docs:
        目的: 空リストを渡した場合、空dictが返ることを確認する。
        検証観点:
            - object_keys=[] で空dictが返る。
    """

    storage_root = Path("/data/bucket")

    results = load_objects("test", [], storage_root=storage_root)
    assert results == {}
