from __future__ import annotations

import time
from datetime import datetime
from typing import Optional


class PipelineLogger:
    """Structured logger for pipeline stages. Outputs to stdout (visible in Databricks notebook cell output)."""

    def __init__(self, stage: str, run_id: Optional[str] = None) -> None:
        self.stage = stage
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._stage_start: float = time.time()

    def _prefix(self, level: str) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        return f"[{ts}][{self.run_id}][{self.stage}][{level}]"

    def info(self, msg: str) -> None:
        print(f"{self._prefix('INFO')} {msg}")

    def warning(self, msg: str) -> None:
        print(f"{self._prefix('WARN')} {msg}")

    def error(self, msg: str) -> None:
        print(f"{self._prefix('ERROR')} {msg}")

    def debug(self, msg: str) -> None:
        print(f"{self._prefix('DEBUG')} {msg}")

    def stage_start(self) -> None:
        self._stage_start = time.time()
        self.info(f"Stage started")

    def stage_end(self, rows_written: Optional[int] = None) -> None:
        elapsed = round(time.time() - self._stage_start, 1)
        suffix = f" | rows_written={rows_written}" if rows_written is not None else ""
        self.info(f"Stage completed in {elapsed}s{suffix}")

    def rows(self, table: str, count: int) -> None:
        self.info(f"Table '{table}' → {count:,} rows")
