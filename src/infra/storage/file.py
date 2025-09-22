"""ファイル出力に関するユーティリティ"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class SaveFormat(Enum):
    """保存対象ファイルの形式"""

    TEXT = "txt"
    HTML = "html"


def generate_timestamped_filename(format: SaveFormat, output_dir: str = "mock") -> str:
    """タイムスタンプ付きファイルパスを生成する"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"out_{timestamp}.{format.value}"
    return str(Path(output_dir) / filename)


def save_content_to_file(
    content: str,
    format: SaveFormat = SaveFormat.HTML,
    filepath: Optional[str] = None,
    output_dir: str = "mock",
) -> str:
    """コンテンツをファイルに保存する"""

    try:
        resolved_path = filepath or generate_timestamped_filename(format, output_dir)
        target_path = Path(resolved_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        print(f"\nコンテンツを {target_path} に保存しました。")
        return str(target_path)
    except Exception as error:
        print(f"ファイル保存エラー: {error}")
        return ""
