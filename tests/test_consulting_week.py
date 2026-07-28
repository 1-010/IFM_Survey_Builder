import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from consulting_week_core import (
    aggregate_responses,
    anonymized_rows,
    calculate_retrospective_expectation,
    is_valid_respondent_id,
    load_event_config,
    validate_response_batch,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "consulting_week_2026.json"


@pytest.fixture
def config():
    return load_event_config(CONFIG_PATH)


def _entry(**overrides):
    payload = {
        "session_id": "part1-01",
        "expectation_score": 0,
        "actual_score": 10,
        "skipped": False,
        "client_updated_at": "2026-07-28T06:10:00+00:00",
        "expectation_updated_at": "2026-07-28T06:00:00+00:00",
        "actual_updated_at": "2026-07-28T06:10:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_event_config_has_expected_date_order_and_part_sizes(config):
    assert config["event_id"] == "consulting-week-2026"
    assert config["event_date"] == "2026-07-28"
    assert [session["order"] for session in config["sessions"]] == list(
        range(1, 17)
    )
    assert [session["part"] for session in config["sessions"]].count(1) == 5
    assert [session["part"] for session in config["sessions"]].count(2) == 5
    assert [session["part"] for session in config["sessions"]].count(3) == 6


def test_tbc_sessions_are_explicitly_marked(config):
    for session in config["sessions"]:
        if session["title"] == "TBC":
            assert session["title_status"] == "tbc"


def test_zero_is_a_valid_answer_and_null_remains_distinct(config):
    zero = validate_response_batch([_entry()], config)[0]
    unanswered = validate_response_batch(
        [
            _entry(
                expectation_score=None,
                expectation_updated_at=None,
                actual_score=None,
                actual_updated_at=None,
            )
        ],
        config,
    )[0]
    assert zero["expectation_score"] == 0
    assert unanswered["expectation_score"] is None


@pytest.mark.parametrize("score", [-1, 11, 1.5, "4", True])
def test_invalid_scores_are_rejected(config, score):
    with pytest.raises(ValueError):
        validate_response_batch([_entry(expectation_score=score)], config)


def test_unknown_or_duplicate_session_ids_are_rejected(config):
    with pytest.raises(ValueError):
        validate_response_batch([_entry(session_id="not-a-session")], config)
    with pytest.raises(ValueError):
        validate_response_batch([_entry(), _entry()], config)


def test_batch_is_bounded_to_sixteen_sessions(config):
    entries = []
    for session in config["sessions"]:
        entries.append(_entry(session_id=session["session_id"]))
    assert len(validate_response_batch(entries, config)) == 16
    with pytest.raises(ValueError):
        validate_response_batch(entries + [_entry()], config)


def test_skipped_answers_are_normalized_to_null(config):
    result = validate_response_batch([_entry(skipped=True)], config)[0]
    assert result["skipped"] is True
    assert result["expectation_score"] is None
    assert result["actual_score"] is None


def test_expectation_after_actual_is_retrospective():
    result = calculate_retrospective_expectation(
        previous_expectation=None,
        previous_retrospective=False,
        expectation_score=5,
        expectation_updated_at=datetime(
            2026, 7, 28, 6, 10, tzinfo=timezone.utc
        ),
        actual_score=7,
        actual_updated_at=datetime(2026, 7, 28, 6, 9, tzinfo=timezone.utc),
        session_end_at=datetime(2026, 7, 28, 6, 14, tzinfo=timezone.utc),
    )
    assert result is True


def test_first_expectation_after_session_end_is_retrospective():
    result = calculate_retrospective_expectation(
        previous_expectation=None,
        previous_retrospective=False,
        expectation_score=5,
        expectation_updated_at=datetime(
            2026, 7, 28, 6, 15, tzinfo=timezone.utc
        ),
        actual_score=None,
        actual_updated_at=None,
        session_end_at=datetime(2026, 7, 28, 6, 14, tzinfo=timezone.utc),
    )
    assert result is True


def test_aggregate_excludes_skips_and_derives_total_and_gap(config):
    records = [
        {
            "respondent_id_hash": "a" * 64,
            "session_id": "part1-01",
            "expectation_score": 3,
            "actual_score": 8,
            "skipped": False,
            "retrospective_expectation": False,
            "client_updated_at": "2026-07-28T06:13:00+00:00",
        },
        {
            "respondent_id_hash": "b" * 64,
            "session_id": "part1-01",
            "expectation_score": None,
            "actual_score": None,
            "skipped": True,
            "retrospective_expectation": False,
            "client_updated_at": "2026-07-28T06:13:01+00:00",
        },
    ]
    row = aggregate_responses(records, config)[0]
    assert row["expectation_average"] == 3
    assert row["actual_average"] == 8
    assert row["total_average"] == 11
    assert row["gap_average"] == 5
    assert row["expectation_count"] == 1
    assert row["actual_count"] == 1
    assert row["skipped_count"] == 1


def test_anonymous_export_never_contains_full_hash_or_raw_uuid():
    full_hash = "a" * 64
    rows = anonymized_rows(
        [
            {
                "respondent_id_hash": full_hash,
                "session_id": "part1-01",
                "expectation_score": 3,
                "actual_score": 8,
                "skipped": False,
                "retrospective_expectation": False,
                "client_updated_at": "2026-07-28T06:13:00+00:00",
            }
        ]
    )
    assert rows[0]["anonymized_respondent_key"] == "a" * 12
    assert full_hash not in json.dumps(rows)


def test_uuid_validation_accepts_v4_and_rejects_other_values():
    assert is_valid_respondent_id("c310f030-6f10-46a8-bd2d-1a3cdf72679b")
    assert not is_valid_respondent_id("not-a-uuid")
    assert not is_valid_respondent_id("00000000-0000-1000-8000-000000000000")


def test_route_runs_before_legacy_question_loader():
    source = (ROOT / "autodesk_assessment.py").read_text(encoding="utf-8")
    assert source.index('if _query_param("event") == "consulting-week-2026"') < (
        source.index("q_df, active_survey_id, client_name = get_default_questions()")
    )
    deployed_entrypoint = (ROOT / "ifm_dashboard.py").read_text(
        encoding="utf-8"
    )
    assert deployed_entrypoint.index(
        'if event_param == "consulting-week-2026"'
    ) < deployed_entrypoint.index("import pandas as pd")
    assert "configure_page=False" in deployed_entrypoint


def test_event_collection_is_separate_from_existing_ifm_collections():
    source = (ROOT / "consulting_week.py").read_text(encoding="utf-8")
    assert 'COLLECTION_NAME = "event_responses_consulting_week_2026"' in source
    assert 'db.collection("responses")' not in source
    assert 'db.collection("surveys")' not in source


def test_frontend_uses_local_storage_debounce_and_batched_dirty_entries():
    source = (
        ROOT / "components" / "consulting_week_form" / "main.js"
    ).read_text(encoding="utf-8")
    assert 'RESPONDENT_KEY = "consulting_week_2026_respondent_id"' in source
    assert "MIN_SYNC_INTERVAL_MS = 5000" in source
    assert "SYNC_DEBOUNCE_MS = 1000" in source
    assert "dirtyEntries" in source
    assert "visibilitychange" in source
    assert 'window.addEventListener("online"' in source
    assert "advanceToNextIncomplete" in source


def test_frontend_explains_submitless_completion_and_uses_official_logo():
    source = (
        ROOT / "components" / "consulting_week_form" / "main.js"
    ).read_text(encoding="utf-8")
    assert "Submitボタンはありません" in source
    assert "画面を閉じて大丈夫です" in source
    assert 'alt="Autodesk"' in source
    assert (ROOT / "data" / "images" / "autodesk_logo_white.svg").exists()
    backend = (ROOT / "consulting_week.py").read_text(encoding="utf-8")
    assert "ご回答を一時送信中" in backend
    assert "sending_notice.empty()" in backend
