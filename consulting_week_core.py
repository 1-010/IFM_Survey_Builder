from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ALLOWED_TITLE_STATUSES = {"confirmed", "tentative", "tbc"}


def parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def datetime_to_iso(value: Any) -> str | None:
    parsed = parse_iso_datetime(value)
    return parsed.isoformat() if parsed else None


def load_event_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_event_config(payload)
    return payload


def validate_event_config(payload: dict[str, Any]) -> None:
    if payload.get("event_id") != "consulting-week-2026":
        raise ValueError("Unexpected event_id")
    if payload.get("timezone") != "Asia/Tokyo":
        raise ValueError("Unexpected timezone")
    if payload.get("status") not in {"active", "closed"}:
        raise ValueError("Event status must be active or closed")

    sessions = payload.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 16:
        raise ValueError("Exactly 16 sessions are required")

    ids: set[str] = set()
    orders: list[int] = []
    part_counts: defaultdict[int, int] = defaultdict(int)
    for session in sessions:
        session_id = session.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Every session requires session_id")
        if session_id in ids:
            raise ValueError(f"Duplicate session_id: {session_id}")
        ids.add(session_id)

        part = session.get("part")
        if part not in {1, 2, 3}:
            raise ValueError(f"Invalid part: {part}")
        part_counts[part] += 1

        order = session.get("order")
        if not isinstance(order, int):
            raise ValueError(f"Invalid order for {session_id}")
        orders.append(order)

        if session.get("title_status") not in ALLOWED_TITLE_STATUSES:
            raise ValueError(f"Invalid title_status for {session_id}")
        if session.get("title") == "TBC" and session.get("title_status") != "tbc":
            raise ValueError(f"TBC title must use title_status=tbc: {session_id}")

        start_at = parse_iso_datetime(session.get("start_at"))
        end_at = parse_iso_datetime(session.get("end_at"))
        if not start_at or not end_at or start_at >= end_at:
            raise ValueError(f"Invalid session time range: {session_id}")

    if sorted(orders) != list(range(1, 17)):
        raise ValueError("Session order must be 1 through 16")
    if dict(part_counts) != {1: 5, 2: 5, 3: 6}:
        raise ValueError("Part sizes must be 5, 5, and 6")


def is_valid_respondent_id(value: Any) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return False
    return parsed.version == 4


def _validated_score(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be an integer from 0 to 10 or null")
    if not float(value).is_integer():
        raise ValueError(f"{field_name} must be an integer from 0 to 10 or null")
    score = int(value)
    if score < 0 or score > 10:
        raise ValueError(f"{field_name} must be an integer from 0 to 10 or null")
    return score


def validate_response_batch(
    entries: Any,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise ValueError("A sync batch must contain 1 to 16 sessions")

    sessions_by_id = {session["session_id"]: session for session in config["sessions"]}
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError("Each response must be an object")
        session_id = raw.get("session_id")
        if session_id not in sessions_by_id:
            raise ValueError(f"Unknown session_id: {session_id}")
        if session_id in seen:
            raise ValueError(f"Duplicate session_id in batch: {session_id}")
        seen.add(session_id)

        skipped = raw.get("skipped")
        if not isinstance(skipped, bool):
            raise ValueError("skipped must be boolean")
        expectation = _validated_score(
            raw.get("expectation_score"),
            "expectation_score",
        )
        actual = _validated_score(raw.get("actual_score"), "actual_score")
        if skipped:
            expectation = None
            actual = None

        client_updated_at = parse_iso_datetime(raw.get("client_updated_at"))
        if not client_updated_at or client_updated_at.tzinfo is None:
            raise ValueError("client_updated_at must be a timezone-aware ISO timestamp")

        expectation_updated_at = parse_iso_datetime(raw.get("expectation_updated_at"))
        actual_updated_at = parse_iso_datetime(raw.get("actual_updated_at"))
        if expectation is not None and (
            not expectation_updated_at or expectation_updated_at.tzinfo is None
        ):
            raise ValueError("Answered expectation requires expectation_updated_at")
        if actual is not None and (
            not actual_updated_at or actual_updated_at.tzinfo is None
        ):
            raise ValueError("Answered actual requires actual_updated_at")

        normalized.append(
            {
                "session_id": session_id,
                "expectation_score": expectation,
                "actual_score": actual,
                "skipped": skipped,
                "client_updated_at": client_updated_at,
                "expectation_updated_at": expectation_updated_at,
                "actual_updated_at": actual_updated_at,
            }
        )
    return normalized


def calculate_retrospective_expectation(
    *,
    previous_expectation: int | None,
    previous_retrospective: bool,
    expectation_score: int | None,
    expectation_updated_at: datetime | None,
    actual_score: int | None,
    actual_updated_at: datetime | None,
    session_end_at: datetime,
) -> bool:
    if previous_retrospective:
        return True
    if previous_expectation is not None or expectation_score is None:
        return False
    if expectation_updated_at is None:
        return False
    if expectation_updated_at > session_end_at:
        return True
    return bool(
        actual_score is not None
        and actual_updated_at is not None
        and actual_updated_at < expectation_updated_at
    )


def _mean(values: list[int | float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def aggregate_responses(
    records: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    by_session: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("session_id"):
            by_session[str(record["session_id"])].append(record)

    result: list[dict[str, Any]] = []
    for session in sorted(config["sessions"], key=lambda item: item["order"]):
        session_records = by_session.get(session["session_id"], [])
        active = [
            record
            for record in session_records
            if not record.get("skipped", False)
        ]
        expectations = [
            record["expectation_score"]
            for record in active
            if record.get("expectation_score") is not None
        ]
        actuals = [
            record["actual_score"]
            for record in active
            if record.get("actual_score") is not None
        ]
        paired = [
            record
            for record in active
            if record.get("expectation_score") is not None
            and record.get("actual_score") is not None
        ]
        totals = [
            record["expectation_score"] + record["actual_score"] for record in paired
        ]
        gaps = [
            record["actual_score"] - record["expectation_score"] for record in paired
        ]
        latest_values = [
            parse_iso_datetime(record.get("updated_at"))
            or parse_iso_datetime(record.get("client_updated_at"))
            for record in session_records
        ]
        latest_values = [value for value in latest_values if value]
        latest = max(latest_values).isoformat() if latest_values else None

        result.append(
            {
                "part": session["part"],
                "order": session["order"],
                "session_id": session["session_id"],
                "presenter": session["presenter"],
                "title": session["title"],
                "title_status": session["title_status"],
                "expectation_average": _mean(expectations),
                "actual_average": _mean(actuals),
                "total_average": _mean(totals),
                "gap_average": _mean(gaps),
                "expectation_count": len(expectations),
                "actual_count": len(actuals),
                "skipped_count": sum(
                    1 for record in session_records if record.get("skipped", False)
                ),
                "retrospective_expectation_count": sum(
                    1
                    for record in active
                    if record.get("retrospective_expectation", False)
                ),
                "last_updated_at": latest,
            }
        )
    return result


def anonymized_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        expectation = record.get("expectation_score")
        actual = record.get("actual_score")
        paired = (
            not record.get("skipped", False)
            and expectation is not None
            and actual is not None
        )
        rows.append(
            {
                "anonymized_respondent_key": str(
                    record.get("respondent_id_hash", "")
                )[:12],
                "session_id": record.get("session_id"),
                "expectation_score": expectation,
                "actual_score": actual,
                "total_score": expectation + actual if paired else None,
                "gap_score": actual - expectation if paired else None,
                "skipped": bool(record.get("skipped", False)),
                "retrospective_expectation": bool(
                    record.get("retrospective_expectation", False)
                ),
                "updated_at": datetime_to_iso(
                    record.get("updated_at") or record.get("client_updated_at")
                ),
            }
        )
    return rows
