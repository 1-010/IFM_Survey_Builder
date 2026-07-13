import json
from pathlib import Path

from ifm_guardrails import get_secret_password, validate_questions


ROOT = Path(__file__).resolve().parents[1]


def test_all_question_sets_have_complete_levels_and_unique_ids():
    payload = json.loads((ROOT / "data" / "ifm_questions.json").read_text(encoding="utf-8"))
    all_errors = []
    for name, questions in payload.items():
        if isinstance(questions, list):
            all_errors.extend(f"{name}: {error}" for error in validate_questions(questions))
    assert all_errors == []


def test_passwords_fail_closed():
    assert get_secret_password({}, "sales_admin") is None
    assert get_secret_password({"sales_admin": {"password": "  "}}, "sales_admin") is None
    assert get_secret_password({"sales_admin": {"password": "configured"}}, "sales_admin") == "configured"
