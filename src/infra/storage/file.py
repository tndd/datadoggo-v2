from enum import Enum
from inspect import currentframe
from pathlib import Path
from types import FrameType
from typing import Optional

from src.infra.compute import generate_timestamped_filename


class SaveFormat(Enum):
    """保存対象ファイルの形式"""

    TEXT = "txt"
    HTML = "html"


def load_file(path: str) -> str:
    """ファイルを読み込む"""
    try:
        target_path = _resolve_path(path)
        return target_path.read_text(encoding="utf-8")
    except Exception as error:
        print(f"ファイル読み込みエラー: {error}")
        return ""


def save_content_to_file(
    content: str,
    format: SaveFormat = SaveFormat.HTML,
    filepath: Optional[str] = None,
    output_dir: str = "mock",
) -> str:
    """コンテンツをファイルに保存する"""

    try:
        resolved_path = (
            Path(filepath)
            if filepath
            else Path(
                generate_timestamped_filename(
                    prefix="out", extension=format.value, output_dir=output_dir
                )
            )
        )
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(content, encoding="utf-8")
        print(f"\nコンテンツを {resolved_path} に保存しました。")
        return str(resolved_path)
    except Exception as error:
        print(f"ファイル保存エラー: {error}")
        return ""


def _resolve_path(path: str) -> Path:
    """読み込み対象のパスを解決する"""

    if path.startswith("."):
        frame = currentframe()
        caller: Optional[FrameType] = None
        try:
            caller = frame.f_back.f_back if frame and frame.f_back else None
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


class Tests:
    def test_load_file(self) -> None:
        """
        docs:
            目的: load_file のパス解決挙動を確認する。
            検証観点:
                - '.' 始まりの相対パスは呼び出しファイル基準で読む。
                - それ以外はプロジェクトルート基準で読む。
        """

        text = load_file("./fixture/sample.txt")
        assert text == "sample text"
        text = load_file("README.md")
        assert text.startswith("# Datadoggo")

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
