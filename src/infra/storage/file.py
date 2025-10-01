# file.py
from enum import Enum
from inspect import currentframe
from pathlib import Path
from types import FrameType
from typing import Optional, Union

from infra.logging import get_logger
from infra.naming import generate_timestamped_filename

PathLike = Union[str, Path]

_log = get_logger()


class SaveFormat(Enum):
    """保存対象ファイルの形式"""

    TEXT = "txt"
    HTML = "html"


def load_file(path: PathLike) -> str:
    """ファイルを読み込む"""
    try:
        target_path = _resolve_any_path(path)
        content = target_path.read_text(encoding="utf-8")
        byte_length = len(content.encode("utf-8"))
        _log.info(
            "ファイルを読み込みました",
            path=str(target_path),
            bytes=byte_length,
        )
        return content
    except Exception as error:
        _log.exception(
            "ファイル読み込みに失敗しました",
            path=str(path),
            error=str(error),
        )
        return ""


def save_content_to_file(
    content: str,
    format: SaveFormat = SaveFormat.HTML,
    filepath: Optional[PathLike] = None,
    output_dir: str = "mock",
) -> str:
    """コンテンツをファイルに保存する"""

    try:
        resolved_path = _prepare_output_path(filepath, format, output_dir)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(content, encoding="utf-8")
        byte_length = len(content.encode("utf-8"))
        _log.info(
            "テキストコンテンツを保存しました",
            path=str(resolved_path),
            bytes=byte_length,
            format=format.value,
        )
        return str(resolved_path)
    except Exception as error:
        _log.exception(
            "テキストコンテンツの保存に失敗しました",
            path=str(filepath),
            error=str(error),
        )
        return ""


def save_bytes_to_file(content: bytes, filepath: PathLike) -> str:
    """バイナリコンテンツをファイルに保存する"""

    try:
        target_path = _to_path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        _log.info(
            "バイナリコンテンツを保存しました",
            path=str(target_path),
            bytes=len(content),
        )
        return str(target_path)
    except Exception as error:
        _log.exception(
            "バイナリコンテンツの保存に失敗しました",
            path=str(filepath),
            error=str(error),
        )
        return ""


def load_bytes(path: PathLike) -> bytes:
    """バイナリファイルを読み込む"""

    try:
        target_path = _resolve_any_path(path)
        payload = target_path.read_bytes()
        _log.info(
            "バイナリを読み込みました",
            path=str(target_path),
            bytes=len(payload),
        )
        return payload
    except Exception as error:
        _log.exception(
            "バイナリ読み込みに失敗しました",
            path=str(path),
            error=str(error),
        )
        return b""


def _resolve_any_path(path: PathLike) -> Path:
    """str/Pathの双方を受け取って実パスに解決する"""

    if isinstance(path, Path):
        return path
    return _resolve_path(path, _stack_skip=3)


def _resolve_path(path: str, *, _stack_skip: int = 2) -> Path:
    """読み込み対象のパスを解決する"""

    if path.startswith("."):
        frame = currentframe()
        caller: Optional[FrameType] = None
        try:
            caller = frame
            steps = _stack_skip
            while steps > 0 and caller:
                caller = caller.f_back
                steps -= 1
            caller_file = (
                Path(caller.f_code.co_filename).resolve()
                if caller
                else Path(__file__).resolve()
            )
        finally:
            del frame
            del caller
        base_dir = caller_file.parent
        return (base_dir / Path(path)).resolve()

    project_root = _find_project_root()
    return (project_root / Path(path)).resolve()


def _find_project_root() -> Path:
    """プロジェクトルートを探索する"""

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent


class TestMod:
    def test_load_file(self) -> None:
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

    def test_save_content_to_file(self, tmp_path: Path) -> None:
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

    def test_save_and_load_bytes(self, tmp_path: Path) -> None:
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


def _prepare_output_path(
    filepath: Optional[PathLike], format: SaveFormat, output_dir: str
) -> Path:
    """保存先パスを決定する"""

    if filepath is not None:
        return _to_path(filepath)

    generated = generate_timestamped_filename(
        prefix="out", extension=format.value, output_dir=output_dir
    )
    return Path(generated)


def _to_path(path: PathLike) -> Path:
    """PathLikeからPathへの変換"""

    return path if isinstance(path, Path) else Path(path)
