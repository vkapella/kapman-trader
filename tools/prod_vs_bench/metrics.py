from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


def format_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


@dataclass
class EvalMetrics:
    verbose: bool
    heartbeat_every: int
    logger: logging.Logger
    prefix: str = "[EVAL]"
    total_symbols: Optional[int] = None
    symbols_processed: int = 0
    rows_scanned: int = 0
    events_evaluated: int = 0
    forward_windows: int = 0
    csv_files_written: int = 0
    csv_rows_written: Dict[str, int] = field(default_factory=dict)
    start_time: float = field(default_factory=time.monotonic)
    _symbols_seen: Set[str] = field(default_factory=set, init=False)

    def set_total_symbols(self, total: Optional[int]) -> None:
        if total is None:
            return
        self.total_symbols = int(total)

    def set_forward_windows(self, windows: int) -> None:
        if windows <= 0:
            return
        self.forward_windows = max(self.forward_windows, int(windows))

    def tick_rows(self, count: int) -> None:
        if count <= 0:
            return
        self.rows_scanned += int(count)

    def tick_events(self, count: int) -> None:
        if count <= 0:
            return
        self.events_evaluated += int(count)

    def tick_symbol(self, symbol: str) -> bool:
        if not symbol:
            return False
        if symbol in self._symbols_seen:
            return False
        self._symbols_seen.add(symbol)
        self.symbols_processed += 1
        return self._maybe_heartbeat()

    def tick_csv_written(self, filename: str, rows: int) -> None:
        self.csv_files_written += 1
        self.csv_rows_written[filename] = int(rows)

    def _maybe_heartbeat(self) -> bool:
        if not self.verbose:
            return False
        if self.heartbeat_every <= 0:
            return False
        if self.symbols_processed % self.heartbeat_every != 0:
            return False
        elapsed = max(time.monotonic() - self.start_time, 0.0)
        rate = self.symbols_processed / elapsed if elapsed > 0 else 0.0
        total = self.total_symbols if self.total_symbols is not None else "?"
        self.logger.info(
            "%s progress symbols=%s/%s rows=%s events=%s elapsed=%ss rate=%.2f sym/s",
            self.prefix,
            self.symbols_processed,
            total,
            format_count(self.rows_scanned),
            format_count(self.events_evaluated),
            int(elapsed),
            rate,
        )
        return True

    def progress_payload(self) -> dict:
        elapsed = max(time.monotonic() - self.start_time, 0.0)
        return {
            "symbols_processed": self.symbols_processed,
            "rows_scanned": self.rows_scanned,
            "events_evaluated": self.events_evaluated,
            "elapsed": elapsed,
        }

    def log_summary(self) -> None:
        if not self.verbose:
            return
        duration = max(time.monotonic() - self.start_time, 0.0)
        csv_rows = ",".join(f"{k}:{v}" for k, v in sorted(self.csv_rows_written.items()))
        self.logger.info(
            "%s RUN SUMMARY symbols_processed=%s rows_scanned=%s events_evaluated=%s "
            "forward_windows=%s csv_files_written=%s csv_rows_written=%s duration_sec=%s",
            self.prefix,
            self.symbols_processed,
            self.rows_scanned,
            self.events_evaluated,
            self.forward_windows,
            self.csv_files_written,
            csv_rows,
            int(duration),
        )
