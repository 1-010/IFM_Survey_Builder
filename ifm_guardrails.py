"""Shared fail-closed validation and authentication helpers for IFM apps."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


REQUIRED_LEVELS = ("L1", "L2", "L3", "L4", "L5")


def validate_questions(questions: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return human-readable schema errors without leaking survey contents."""
    errors: list[str] = []
    seen: set[str] = set()
    for index, question in enumerate(questions, start=1):
        qid = str(question.get("question_id", "")).strip()
        label = qid or f"row-{index}"
        if not qid:
            errors.append(f"{label}: question_id is required")
        elif qid in seen:
            errors.append(f"{label}: duplicate question_id")
        seen.add(qid)
        for field in ("department", "phase", "question_text"):
            if not str(question.get(field, "")).strip():
                errors.append(f"{label}: {field} is required")
        levels = question.get("levels")
        if not isinstance(levels, Mapping):
            errors.append(f"{label}: levels must be an object")
            continue
        for level in REQUIRED_LEVELS:
            if not str(levels.get(level, "")).strip():
                errors.append(f"{label}: {level} is required")
    return errors


def get_secret_password(secrets: Mapping[str, Any], section: str) -> str | None:
    """Read an admin password and fail closed when the secret is absent/blank."""
    try:
        value = secrets.get(section, {}).get("password")
    except (AttributeError, TypeError):
        return None
    value = str(value).strip() if value is not None else ""
    return value or None


def dedupe_response_rows(rows: Any) -> Any:
    """De-duplicate row-shaped response data when a backup source overlaps."""
    if rows is None or getattr(rows, "empty", True):
        return rows
    keys = [
        key
        for key in ("timestamp", "respondent", "email", "survey_id", "question_id")
        if key in rows.columns
    ]
    return rows.drop_duplicates(subset=keys, keep="first") if keys else rows.drop_duplicates()
