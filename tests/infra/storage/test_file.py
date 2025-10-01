"""infra.storage.file のテスト"""

from pathlib import Path

from infra.storage.file import (
    SaveFormat,
    load_bytes,
    load_file,
    save_bytes_to_file,
    save_content_to_file,
)


def test_load_file() -> None:
    """
    docs:
        目的: load_file のパス解決挙動を確認する。
        検証観点:
            - '.' 始まりの相対パスは呼び出しファイル基準で読む。
            - それ以外はプロジェクトルート基準で読む。
    """

    # absolute
    text = load_file("mock/sample.txt")
    assert text == "sample text"
    # relative
    text = load_file("./file.py")
    assert text.startswith("# file.py")  # WARN: その場しのぎのテスト


def test_save_content_to_file(tmp_path: Path) -> None:
    """
    docs:
        目的: save_content_to_file の保存動作を確認する。
        検証観点:
            - 指定ディレクトリ配下にコンテンツが保存される。
            - ファイルパス未指定時にタイムスタンプ付きファイル名が生成される。
    """

    output_dir = tmp_path / "mock"
    path_str = save_content_to_file(
        "テストコンテンツ",
        format=SaveFormat.TEXT,
        output_dir=str(output_dir),
    )
    saved_path = Path(path_str)
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == "テストコンテンツ"


def test_save_and_load_bytes(tmp_path: Path) -> None:
    """
    docs:
        目的: save_bytes_to_file / load_bytes のバイナリ入出力を確認する。
        検証観点:
            - 指定パスにバイナリが保存・読み込みできる。
            - 保存時にディレクトリが自動作成される。
    """

    target_path = tmp_path / "bin" / "data.bin"
    payload = b"binary-content"

    written = save_bytes_to_file(payload, target_path)
    assert written == str(target_path)
    assert target_path.exists()

    loaded = load_bytes(target_path)
    assert loaded == payload
