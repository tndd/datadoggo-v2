"""ログ設定ユーティリティ"""

from __future__ import annotations

import inspect
import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import zstandard as zstd
from loguru import logger as _logger

if TYPE_CHECKING:
    from loguru import Logger

DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_NAME = "app.log"
_LOG_STATE: dict[str, int | None] = {"sink_id": None}
_LABEL_SEGMENT_LIMIT = 2


def configure_logging(
    *,
    log_path: Path | None = None,
    serialize: bool = True,
    enqueue: bool = True,
    label: str | None = None,
) -> None:
    """loguruの設定を初期化する"""

    sink_id = _LOG_STATE["sink_id"]
    if sink_id is not None:
        _logger.remove(sink_id)
        _LOG_STATE["sink_id"] = None

    _logger.remove()

    target_path = _resolve_log_path(log_path=log_path, label=label)
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


def _resolve_log_path(*, log_path: Path | None, label: str | None) -> Path:
    if log_path is not None:
        return log_path

    if label:
        return DEFAULT_LOG_DIR / f"{label}.log"

    return DEFAULT_LOG_DIR / DEFAULT_LOG_NAME


def get_logger(
    *,
    component: str | None = None,
    label: str | None = None,
) -> "Logger":
    """ロガーにコンポーネント情報を付与して取得する"""

    target_component = component or _resolve_caller_component()
    target_label = label or _derive_label(target_component)

    base = _logger
    if target_label:
        base = base.bind(label=target_label)
    return base.bind(component=target_component)


def _resolve_caller_component() -> str:
    frame = inspect.currentframe()
    if frame is None:
        return "unknown"

    try:
        caller_frame = frame.f_back
        if caller_frame is None:
            return "unknown"
        module = inspect.getmodule(caller_frame)
        if module is None:
            return "unknown"
        return _normalize_module_name(module.__name__)
    finally:
        del frame


@lru_cache(maxsize=256)
def _normalize_module_name(name: str) -> str:
    if name.startswith("src."):
        return name
    return name


def _derive_label(component: str) -> str:
    parts = component.split(".")
    filtered = [part for part in parts if part and part != "src"]
    if not filtered:
        return ""
    if len(filtered) >= _LABEL_SEGMENT_LIMIT:
        return ".".join(filtered[:_LABEL_SEGMENT_LIMIT])
    return filtered[0]


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
