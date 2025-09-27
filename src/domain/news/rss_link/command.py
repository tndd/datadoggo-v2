# RSSリンク関連の書き込みなどの状態変化を伴う処理

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from xml.etree.ElementTree import Element, tostring

from infra.parse import parse_rss
from infra.storage.bucket import DEFAULT_STORAGE_ROOT, load_object, save_object
from infra.storage.rds import initialize_database, session_scope

from .convert import record_to_rss_bucket, rss_bucket_to_record
from .model import RssBucketItem, RssBucketStatus, RssItem
from .service import create_rss_bucket_item


def save_rss_element_to_bucket(
    element: Element,
    *,
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
    payload: bytes | None = None,
) -> str:
    """RSS要素を単体で保存しキーを返す"""

    payload_bytes = payload or _element_to_bytes(element, encoding=encoding)
    checksum = sha256(payload_bytes).hexdigest()
    return save_object(
        payload_bytes,
        bucket_name=bucket_name,
        object_key=checksum,
        storage_root=storage_root,
        encoding=encoding,
    )


def save_rss_elements_to_bucket(
    elements: Sequence[Element],
    *,
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
    encoding: str = "utf-8",
) -> list[str]:
    """RSS要素のシーケンスを保存しキー一覧を返す"""

    saved_keys: list[str] = []

    for element in elements:
        key = save_rss_element_to_bucket(
            element,
            bucket_name=bucket_name,
            storage_root=storage_root,
            encoding=encoding,
        )
        if key:
            saved_keys.append(key)

    return saved_keys


def _element_to_bytes(element: Element, *, encoding: str) -> bytes:
    """RSS要素を指定エンコーディングでシリアライズする"""

    return tostring(element, encoding=encoding)


def store_rss_bucket_payload(
    rss_item: RssItem,
    element: Element,
    *,
    bucket_name: str = "rss",
    storage_root: str | Path = DEFAULT_STORAGE_ROOT,
    status: RssBucketStatus | str = RssBucketStatus.registered,
) -> RssBucketItem:
    """バケット保存とメタデータ永続化を一貫処理する"""

    encoding = "utf-8"
    payload_bytes = _element_to_bytes(element, encoding=encoding)
    key = save_rss_element_to_bucket(
        element,
        bucket_name=bucket_name,
        storage_root=storage_root,
        encoding=encoding,
        payload=payload_bytes,
    )
    if not key:
        raise RuntimeError("バケット保存に失敗しました")

    bucket_item = create_rss_bucket_item(
        bucket_key=key,
        rss_item=rss_item,
        status=status,
        content_length=len(payload_bytes),
    )

    initialize_database()
    with session_scope() as session:
        record = rss_bucket_to_record(bucket_item)
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return record_to_rss_bucket(merged)


class Tests:
    class Test_save_rss_element_to_bucket:
        def test_save_rss_element_to_bucket_persists_payload(self, tmp_path) -> None:
            """
            docs:
                目的:
                    RSS要素を単体で保存しZstandard圧縮で復元できることを確認する。
                検証観点:
                    - 保存キーが SHA256 ハッシュと一致する。
                    - 展開後のXMLが ElementTree のシリアライズ結果と一致する。
            """

            storage_root = tmp_path / "bucket"
            rss_document = (
                b"<rss version='2.0'><channel><title>Alpha</title></channel></rss>"
            )
            element = parse_rss(rss_document)

            key = save_rss_element_to_bucket(
                element,
                storage_root=storage_root,
            )

            serialized = _element_to_bytes(element, encoding="utf-8")
            expected_checksum = sha256(serialized).hexdigest()
            assert key == expected_checksum

            loaded = load_object("rss", key, storage_root=storage_root, as_text=False)
            assert loaded == serialized

    class Test_save_rss_elements_to_bucket:
        def test_save_rss_elements_to_bucket_persists_payload(self, tmp_path) -> None:
            """
            docs:
                目的:
                    複数のRSS要素を保存しZstandard圧縮で復元できることを確認する。
                検証観点:
                    - 保存キーが SHA256 ハッシュと一致する。
                    - 展開後のXMLが ElementTree のシリアライズ結果と一致する。
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

            for key, element, _original in zip(
                keys, elements, rss_documents, strict=True
            ):
                serialized = _element_to_bytes(element, encoding="utf-8")
                expected_checksum = sha256(serialized).hexdigest()
                assert key == expected_checksum
                loaded = load_object(
                    "rss", key, storage_root=storage_root, as_text=False
                )
                assert loaded == serialized

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

    class Test_store_rss_bucket_payload:
        def test_store_rss_bucket_payload_persists_metadata(self, tmp_path) -> None:
            """
            docs:
                目的:
                    store_rss_bucket_payload がバケットと DB へ保存することを確認する。
                検証観点:
                    - rss_bucket テーブルにレコードが保存される。
                    - content_length が保存したペイロード長と一致する。
            """

            import os

            from sqlmodel import select

            from .model import RssBucketRecord

            rss_document = (
                b"<rss version='2.0'><channel><title>Meta</title>"
                b"<link>https://example.com/meta</link>"
                b"<item><title>A</title></item></channel></rss>"
            )
            element = parse_rss(rss_document)
            rss_item = RssItem(group="bbc", name="top", url="https://example.com/meta")

            storage_root = tmp_path / "bucket"
            db_path = tmp_path / "rss_bucket.db"
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

            try:
                result = store_rss_bucket_payload(
                    rss_item,
                    element,
                    storage_root=storage_root,
                )

                assert result.id
                assert result.content_length == len(rss_document)
                assert result.is_registered()
                assert result.saved_at.tzinfo is not None

                with session_scope() as session:
                    statement = select(RssBucketRecord).where(
                        RssBucketRecord.id == result.id
                    )
                    record = session.exec(statement).first()
                    assert record is not None
                    assert record.group == "bbc"
                    assert record.saved_at.replace(
                        tzinfo=None
                    ) == result.saved_at.replace(tzinfo=None)
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)

        def test_store_rss_bucket_payload_accepts_status_string(self, tmp_path) -> None:
            """
            docs:
                目的:
                    文字列ステータス指定で保存できることを確認する。
                検証観点:
                    - status="overridden" 指定で StrEnum に変換される。
                    - 再保存でレコードが上書きされる。
            """

            import os

            from sqlmodel import select

            from .model import RssBucketRecord, RssBucketStatus

            rss_document = (
                b"<rss version='2.0'><channel><title>Override</title>"
                b"<link>https://example.com/override</link>"
                b"</channel></rss>"
            )
            element = parse_rss(rss_document)
            rss_item = RssItem(
                group="guardian",
                name="world",
                url="https://example.com/override",
            )

            storage_root = tmp_path / "bucket"
            db_path = tmp_path / "rss_bucket_override.db"
            os.environ["FEED_DATABASE_URL"] = f"sqlite:///{db_path}"

            try:
                first = store_rss_bucket_payload(
                    rss_item,
                    element,
                    storage_root=storage_root,
                )

                second = store_rss_bucket_payload(
                    rss_item,
                    element,
                    storage_root=storage_root,
                    status="overridden",
                )

                assert second.status is RssBucketStatus.overridden
                assert second.saved_at >= first.saved_at

                with session_scope() as session:
                    statement = select(RssBucketRecord).where(
                        RssBucketRecord.id == second.id
                    )
                    record = session.exec(statement).first()
                    assert record is not None
                    assert record.status == "overridden"
            finally:
                os.environ.pop("FEED_DATABASE_URL", None)
