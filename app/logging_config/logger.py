import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from ..config.settings import settings
from ..config.yaml_config import yaml_config


class StackTraceFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if record.exc_info:
            tb_lines = traceback.format_exception(*record.exc_info)
            limit = yaml_config.get("logging", "stack_trace_limit", 10)
            tb_text = "".join(tb_lines[-limit:]) if limit else "".join(tb_lines)
            formatted = f"{formatted}\nStack Trace:\n{tb_text}"
        return formatted


def setup_logger(name: str = "ship_ops") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, settings.app.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    fmt = StackTraceFormatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True, parents=True)

    file_handler = logging.FileHandler(
        log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


logger = setup_logger()


def log_exception(e: Exception, context: Optional[dict] = None) -> None:
    ctx_str = f" | Context: {context}" if context else ""
    logger.error(f"Exception occurred: {type(e).__name__}: {e}{ctx_str}", exc_info=True)


def save_failed_waveform(
    task_uuid: str,
    waveform_data: bytes,
    metadata: Optional[dict] = None,
) -> Optional[str]:
    try:
        base_dir = yaml_config.get("logging", "failed_waveform_dir", "./data/failed_waveforms")
        save_dir = Path(base_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_uuid}_{timestamp}.bin"
        filepath = save_dir / filename

        with open(filepath, "wb") as f:
            f.write(waveform_data)

        meta_path = save_dir / f"{task_uuid}_{timestamp}_meta.txt"
        if metadata:
            with open(meta_path, "w", encoding="utf-8") as f:
                for k, v in metadata.items():
                    f.write(f"{k}: {v}\n")

        logger.info(f"Failed waveform saved to: {filepath}")
        return str(filepath)
    except Exception as save_err:
        logger.error(f"Failed to save failed waveform: {save_err}", exc_info=True)
        return None
