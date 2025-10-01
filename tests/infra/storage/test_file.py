"""infra.storage.file のテスト"""

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from infra.storage.file import (
    SaveFormat,
    load_bytes,
    save_bytes_to_file,
    save_content_to_file,
)


def test_save_content_to_file(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: save_content_to_file の保存動作を確認する。
        検証観点:
            - 指定ディレクトリ配下にコンテンツが保存される。
            - ファイルパス未指定時にタイムスタンプ付きファイル名が生成される。
    """

    output_dir = Path("/tmp/mock")
    fs.create_dir(str(output_dir))
    path_str = save_content_to_file(
        "テストコンテンツ",
        format=SaveFormat.TEXT,
        output_dir=str(output_dir),
    )
    saved_path = Path(path_str)
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == "テストコンテンツ"


def test_save_and_load_bytes(fs: FakeFilesystem) -> None:
    """
    docs:
        目的: save_bytes_to_file / load_bytes のバイナリ入出力を確認する。
        検証観点:
            - 指定パスにバイナリが保存・読み込みできる。
            - 保存時にディレクトリが自動作成される。
    """

    target_path = Path("/tmp/bin/data.bin")
    payload = b"binary-content"

    written = save_bytes_to_file(payload, target_path)
    assert written == str(target_path)
    assert target_path.exists()

    loaded = load_bytes(target_path)
    assert loaded == payload
