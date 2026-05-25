"""Loaders for the JSONL audit logs and structured trace artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd


def load_jsonl(file_path: str | Path) -> pd.DataFrame:
    """Load a JSONL file into a DataFrame. Empty/missing files return empty DataFrame."""
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[trace_loader] skipping {path.name}:{line_no} ({e})")
                continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def load_action_events(file_path: str | Path) -> pd.DataFrame:
    """Load an action_events JSONL and ensure expected columns exist."""
    df = load_jsonl(file_path)
    if df.empty:
        return df

    expected = [
        "event_id", "timestamp", "actor", "task_id", "phase", "operation",
        "target", "declared_intent", "expected_next_action", "scope_reason",
        "risk_level", "approval_required", "approved", "human_feedback",
        "outcome_label", "outcome_notes",
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = pd.NA
    return df.sort_values("timestamp").reset_index(drop=True)


def load_approval_events(file_path: str | Path) -> pd.DataFrame:
    return load_jsonl(file_path)


def load_inbox(file_path: str | Path, inbox_name: str | None = None) -> pd.DataFrame:
    """Load an inbox_*.jsonl. Schema is free-form; we ensure a few columns exist
    so the dashboard can rely on them."""
    df = load_jsonl(file_path)
    if df.empty:
        return df
    for col in ("id", "from", "to", "type", "content", "needs_review", "read_at"):
        if col not in df.columns:
            df[col] = pd.NA
    if inbox_name is not None:
        df["inbox"] = inbox_name
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def load_task_events(file_path: str | Path) -> pd.DataFrame:
    return load_jsonl(file_path)


def load_trace_json(file_path: str | Path) -> Optional[dict]:
    path = Path(file_path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_available_logs(audit_dir: str | Path) -> list[str]:
    """All JSONL files in the audit directory."""
    path = Path(audit_dir)
    if not path.exists():
        return []
    return sorted(str(p) for p in path.glob("*.jsonl"))


def get_available_traces(traces_dir: str | Path) -> list[str]:
    path = Path(traces_dir)
    if not path.exists():
        return []
    return sorted(str(p) for p in path.glob("*.json"))


# Back-compat shim — the previous app.py imported this name.
def load_trace_events(file_path: str | Path) -> pd.DataFrame:
    return load_action_events(file_path)
