from inspect import currentframe
from pathlib import Path
from types import FrameType
from typing import Optional


def load_file(path: str) -> str:
    """ファイルを読み込む"""
    try:
        target_path = _resolve_path(path)
        return target_path.read_text(encoding="utf-8")
    except Exception as error:
        print(f"ファイル読み込みエラー: {error}")
        return ""


def _resolve_path(path: str) -> Path:
    """読み込み対象のパスを解決する"""

    # "." 始まりは呼び出し元ファイルからの相対パスとして解釈する
    if path.startswith("."):
        frame = currentframe()
        caller: Optional[FrameType] = None
        try:
            # load_file -> _resolve_path の呼び出しなので、2階層上の呼び出し元を取得
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

        # 相対パスの読み込み
        text = load_file("./fixture/sample.txt")
        assert text == "sample text"
        # 絶対パスの読み込
        text = load_file("README.md")
        assert text.startswith("# Datadoggo")
