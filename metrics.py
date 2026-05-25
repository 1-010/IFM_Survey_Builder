"""Behavioral metrics for traceable AI collaboration.

All metrics are computed from a single action_events DataFrame (one task at a time
recommended; pass the full DF if you want cross-task aggregates).

Label hierarchy:
  reviewed_outcome — authoritative, human/benchmark-reviewed. Use for statistics.
  algorithmic_signals — list of behavioral signals. Use for exploration only, not for claims.
"""

from __future__ import annotations

import pandas as pd

USEFUL_LABELS = {"useful", "recovery", "resolution_step"}
DETOUR_LABELS = {"detour", "wrong_door"}


def _outcome_col(df: pd.DataFrame) -> str | None:
    """Return the best available outcome column name."""
    if "reviewed_outcome" in df.columns:
        return "reviewed_outcome"
    return None


def _empty_metrics() -> dict:
    return {
        "total_events": 0,
        "reviewed_events": 0,
        "first_correct_door_latency": 0,
        "detour_ratio": 0.0,
        "wrong_door_count": 0,
        "detour_count": 0,
        "backtrack_count": 0,
        "scope_explosion_score": 0,
        "human_rescue_delta": 0.0,
        "human_rescues": 0,
        "approval_friction_score": 0.0,
        "signal_counts": {},
    }


def first_correct_door_latency(df: pd.DataFrame) -> int:
    """1-based index of the first event whose reviewed_outcome is useful/recovery/resolution_step.
    Returns 0 if no such event exists."""
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0
    mask = df[col].isin(USEFUL_LABELS)
    if not mask.any():
        return 0
    pos = mask.to_numpy().argmax()
    return int(pos) + 1


def detour_counts(df: pd.DataFrame) -> tuple[int, int]:
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0, 0
    wrong_door = int((df[col] == "wrong_door").sum())
    detour = int((df[col] == "detour").sum())
    return wrong_door, detour


def detour_ratio(df: pd.DataFrame) -> float:
    """Detour ratio computed only over reviewed events (not total events)."""
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0.0
    reviewed = df[col].notna() & (df[col] != "")
    reviewed_count = int(reviewed.sum())
    if reviewed_count == 0:
        return 0.0
    wd, d = detour_counts(df)
    return (wd + d) / reviewed_count


def backtrack_count(df: pd.DataFrame) -> int:
    """Transitions from a detour/wrong_door state back into the useful path."""
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0
    count = 0
    in_detour = False
    for label in df[col].fillna(""):
        if label in DETOUR_LABELS:
            in_detour = True
        elif in_detour and label in USEFUL_LABELS:
            count += 1
            in_detour = False
    return count


def scope_explosion_score(df: pd.DataFrame) -> int:
    """Signal-based: count events with scope_broadened or broad_search_started signals."""
    if df.empty:
        return 0
    if "algorithmic_signals" in df.columns:
        score = 0
        for signals in df["algorithmic_signals"].dropna():
            if isinstance(signals, list):
                if "scope_broadened" in signals or "broad_search_started" in signals:
                    score += 1
        return score
    # Fallback to old heuristic for legacy data
    if "target" not in df.columns:
        return 0
    score = 0
    prev_depth = None
    for _, row in df.iterrows():
        t_val = row.get("target")
        target = "" if pd.isna(t_val) else str(t_val)
        o_val = row.get("operation")
        op = "" if pd.isna(o_val) else str(o_val)
        if op not in ("search", "read_file"):
            prev_depth = None
            continue
        if "**/*" in target or target.endswith("/*") or target.count("*") >= 2:
            score += 1
            prev_depth = target.count("/")
            continue
        depth = target.count("/")
        if prev_depth is not None and depth < prev_depth - 1:
            score += 1
        prev_depth = depth
    return score


def signal_counts(df: pd.DataFrame) -> dict:
    """Count occurrences of each algorithmic signal across all events."""
    counts: dict = {}
    if df.empty or "algorithmic_signals" not in df.columns:
        return counts
    for signals in df["algorithmic_signals"].dropna():
        if isinstance(signals, list):
            for s in signals:
                counts[s] = counts.get(s, 0) + 1
    return counts


def human_rescue_delta(df: pd.DataFrame) -> float:
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0.0
    rescue_mask = (df[col] == "rejected") & df.get(
        "human_feedback", pd.Series([None] * len(df))
    ).notna()
    if not rescue_mask.any():
        return 0.0
    last_rescue_pos = int(rescue_mask.to_numpy().argmax()) if rescue_mask.sum() == 1 else int(
        len(df) - 1 - rescue_mask[::-1].to_numpy().argmax()
    )
    before = df.iloc[:last_rescue_pos]
    after = df.iloc[last_rescue_pos + 1:]
    if len(after) == 0:
        return 0.0
    before_rate = (before[col].isin(USEFUL_LABELS).mean() if len(before) else 0.0)
    after_rate = after[col].isin(USEFUL_LABELS).mean()
    return float(after_rate - before_rate)


def human_rescues(df: pd.DataFrame) -> int:
    col = _outcome_col(df)
    if df.empty or col is None:
        return 0
    mask = (df[col] == "rejected")
    if "human_feedback" in df.columns:
        mask = mask & df["human_feedback"].notna()
    return int(mask.sum())


def approval_friction_score(df: pd.DataFrame) -> float:
    col = _outcome_col(df)
    if df.empty or "approval_required" not in df.columns or col is None:
        return 0.0
    requests = int(df["approval_required"].fillna(False).astype(bool).sum())
    useful_approved = int(
        ((df.get("approved", pd.Series([False] * len(df))).fillna(False).astype(bool))
         & df[col].isin(USEFUL_LABELS)).sum()
    )
    if useful_approved == 0:
        return float(requests)
    return requests / useful_approved


def calculate_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return _empty_metrics()
    col = _outcome_col(df)
    reviewed_count = int(df[col].notna().sum()) if col else 0
    wd, d = detour_counts(df)
    return {
        "total_events": int(len(df)),
        "reviewed_events": reviewed_count,
        "first_correct_door_latency": first_correct_door_latency(df),
        "detour_ratio": float(detour_ratio(df)),
        "wrong_door_count": wd,
        "detour_count": d,
        "backtrack_count": backtrack_count(df),
        "scope_explosion_score": scope_explosion_score(df),
        "human_rescue_delta": human_rescue_delta(df),
        "human_rescues": human_rescues(df),
        "approval_friction_score": approval_friction_score(df),
        "signal_counts": signal_counts(df),
    }


