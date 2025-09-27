# RSSリンク関連の書き込みなどの状態変化を伴う処理

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from xml.etree.ElementTree import Element, tostring

from infra.parse import parse_rss
from infra.storage.bucket import DEFAULT_STORAGE_ROOT, load_object, save_object


def save_rss_elements_to_bucket(
    elements: Sequence[Element],
    *,
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
) -> list[str]:
    """RSS要素をZstandard圧縮で保存しキー一覧を返す"""

    saved_keys: list[str] = []

    for element in elements:
        payload = _element_to_bytes(element, encoding=encoding)
        checksum = sha256(payload).hexdigest()
        key = save_object(
            payload,
            bucket_name=bucket_name,
            object_key=checksum,
            storage_root=storage_root,
            encoding=encoding,
        )
        if key:
            saved_keys.append(key)

    return saved_keys


def _element_to_bytes(element: Element, *, encoding: str) -> bytes:
    """RSS要素を指定エンコーディングでシリアライズする"""

    return tostring(element, encoding=encoding)


class Tests:
    class save_rss_elements_to_bucket:
        def test_save_rss_elements_to_bucket_persists_payload(self, tmp_path) -> None:
            """
            docs:
                目的:
                    RSS要素をバケットへ保存しZstandard圧縮で復元できることを確認する。
                検証観点:
                    - 保存キーが SHA256 ハッシュと一致する。
                    - 保存したデータが展開後に元のXMLと一致する。
            """

            storage_root = tmp_path / "bucket"
            rss_documents = [
                b"<rss version='2.0'><channel><title>Alpha</title></channel></rss>",
                b"<rss version='2.0'><channel><title>Beta</title></channel></rss>",
            ]
            elements = [parse_rss(document) for document in rss_documents]

            keys = save_rss_elements_to_bucket(
                elements,
                storage_root=storage_root,
            )

            assert len(keys) == len(rss_documents)

            for key, original in zip(keys, rss_documents, strict=True):
                assert key == sha256(original).hexdigest()
                loaded = load_object(
                    "rss", key, storage_root=storage_root, as_text=False
                )
                assert loaded == original

        def test_save_rss_elements_to_bucket_accepts_empty(self, tmp_path) -> None:
            """
            docs:
                目的:
                    保存対象が空の場合でもエラー無く空リストを返すことを確認する。
                検証観点:
                    - 空シーケンス入力で戻り値が空リストとなる。
                    - バケット配下にファイルが作成されない。
            """

            storage_root = tmp_path / "bucket"

            keys = save_rss_elements_to_bucket(
                [],
                storage_root=storage_root,
            )

            assert keys == []
            assert not any(storage_root.glob("**/*"))
