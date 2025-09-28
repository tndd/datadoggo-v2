"""ログ設定ユーティリティ"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import zstandard as zstd
from loguru import logger as _logger

DEFAULT_LOG_PATH = Path("logs/rss_errors.log")
_LOG_STATE: dict[str, int | None] = {"sink_id": None}


def configure_logging(
    *,
    log_path: Path | None = None,
    serialize: bool = True,
    enqueue: bool = True,
) -> None:
    """loguruの設定を初期化する"""

    sink_id = _LOG_STATE["sink_id"]
    if sink_id is not None:
        _logger.remove(sink_id)
        _LOG_STATE["sink_id"] = None

    _logger.remove()

    target_path = log_path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    _LOG_STATE["sink_id"] = _logger.add(
        target_path,
        rotation="10 MB",
        retention=10,
        compression=_compress_to_zst,
        enqueue=enqueue,
        backtrace=True,
        diagnose=False,
        serialize=serialize,
        level="INFO",
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def reset_logging() -> None:
    """loguruの設定を標準出力のみの状態に戻す"""

    _logger.remove()
    _LOG_STATE["sink_id"] = _logger.add(sys.stderr, level="INFO")
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def _compress_to_zst(path: str) -> None:
    """loguruから呼び出されるzstd圧縮処理"""

    source_path = Path(path)
    target_path = source_path.with_suffix(source_path.suffix + ".zst")

    compressor = zstd.ZstdCompressor()
    with source_path.open("rb") as source, target_path.open("wb") as target:
        with compressor.stream_writer(target) as writer:
            for chunk in iter(lambda: source.read(1024 * 128), b""):
                writer.write(chunk)

    source_path.unlink(missing_ok=True)


class InterceptHandler(logging.Handler):
    """標準loggingログをloguruへ転送するハンドラ"""

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()

        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        log = _logger.bind(logger_name=record.name)
        log.opt(depth=6, exception=record.exc_info, colors=False).log(level, message)


logger = _logger
