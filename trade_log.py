"""
Reusable, schema-flexible CSV audit logging.

Strategy-agnostic: the field list for both event and trade logs is passed in
by the caller (or uses the lean defaults below for exchange-client-level
order/fill/error events). Any strategy built later can define its own richer
field list and get the same auto-migrating-header append behavior.
"""

from __future__ import annotations

import csv
import os
import time
from datetime import datetime, timezone

# Lean, order/fill/error-lifecycle-only fields used internally by binance_client.py.
# A strategy module can define its own (richer, strategy-specific) field list and
# construct a separate CsvLogger for its own higher-level events (entries, exits, etc.).
DEFAULT_EVENT_FIELDS = [
    "timestamp",
    "unix_time",
    "event",
    "dry_run",
    "symbol",
    "side",
    "type",
    "quantity",
    "price",
    "reduce_only",
    "time_in_force",
    "order_id",
    "status",
    "executed_qty",
    "reason",
    "error_type",
    "status_code",
    "response_body",
    "request_csv",
    "response_csv",
]

# Minimal generic trade-summary fields; extend/replace per strategy as needed.
DEFAULT_TRADE_FIELDS = [
    "entry_time",
    "exit_time",
    "duration_sec",
    "exit_reason",
    "pnl_pct",
    "pnl_usd",
]


class CsvLogger:
    """Appends rows to a CSV file with a fixed header, auto-migrating the header
    (rewriting existing rows) if the field list has changed since the file was created."""

    def __init__(self, path: str, fields: list[str]):
        self.path = path
        self.fields = fields

    def _migrate_if_needed(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, newline="") as existing:
            reader = csv.reader(existing)
            header = next(reader, [])
            if header == self.fields:
                return
            rows = list(reader)
            migrated = [dict(zip(header, row)) for row in rows]
            temporary_path = self.path + ".tmp"
            with open(temporary_path, "w", newline="") as replacement:
                writer = csv.DictWriter(replacement, fieldnames=self.fields)
                writer.writeheader()
                writer.writerows({field: row.get(field, "") for field in self.fields} for row in migrated)
            os.replace(temporary_path, self.path)

    def log(self, event: str | None = None, **fields) -> None:
        """Write one row. If constructed with an event-log field list, pass event=... ;
        for a plain trade-summary log, just pass the row fields as kwargs."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._migrate_if_needed()
        record = dict(fields)
        if event is not None:
            record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            record.setdefault("unix_time", time.time())
            record["event"] = event
        row = {field: record.get(field, "") for field in self.fields}
        is_new = not os.path.exists(self.path)
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            if is_new:
                writer.writeheader()
            writer.writerow(row)


def load_day_pnl(path: str, pnl_field: str = "pnl_usd", time_field: str = "entry_time") -> float:
    """Sum pnl_field for rows whose time_field falls on today's UTC date. Used to make a
    daily loss-stop restart-safe (re-derived from the log instead of kept only in memory)."""
    if not os.path.exists(path):
        return 0.0
    today = datetime.now(timezone.utc).date()
    total = 0.0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                row_date = datetime.fromtimestamp(float(row[time_field]), timezone.utc).date()
                if row_date == today:
                    total += float(row.get(pnl_field, 0) or 0)
            except (KeyError, TypeError, ValueError):
                continue
    return total
