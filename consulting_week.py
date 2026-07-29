from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import qrcode
import streamlit as st
import streamlit.components.v1 as components
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from consulting_week_core import (
    aggregate_responses,
    anonymized_rows,
    calculate_retrospective_expectation,
    datetime_to_iso,
    is_valid_respondent_id,
    load_event_config,
    parse_iso_datetime,
    validate_response_batch,
)
from db_helper import (
    FIRESTORE_READ_RETRY,
    FIRESTORE_TIMEOUT_SECONDS,
    get_firestore_client,
)
from ifm_guardrails import get_secret_password

try:
    ROOT = Path(__file__).resolve().parent
except NameError:
    ROOT = Path(".").resolve()
EVENT_CONFIG_PATH = ROOT / "data" / "consulting_week_2026.json"
COMPONENT_PATH = ROOT / "components" / "consulting_week_form"
AUTODESK_LOGO_PATH = ROOT / "data" / "images" / "autodesk_logo_white.svg"
COLLECTION_NAME = "event_responses_consulting_week_2026"
PUBLIC_BASE_URL = (
    "https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/"
)
PUBLIC_RESPONSE_URL = f"{PUBLIC_BASE_URL}?event=consulting-week-2026"
PUBLIC_ADMIN_URL = (
    f"{PUBLIC_BASE_URL}?event=consulting-week-2026&view=admin"
)
LOCAL_RESPONSE_URL = "http://localhost:8501/?event=consulting-week-2026"
LOCAL_ADMIN_URL = (
    "http://localhost:8501/?event=consulting-week-2026&view=admin"
)

_consulting_week_component = components.declare_component(
    "consulting_week_session_feedback",
    path=str(COMPONENT_PATH),
)


def _event_config() -> dict[str, Any]:
    return load_event_config(EVENT_CONFIG_PATH)


def _logo_data_uri() -> str:
    encoded = base64.b64encode(AUTODESK_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _event_hmac_key(event_id: str) -> bytes:
    configured = st.secrets.get("consulting_week", {})
    configured_salt = configured.get("respondent_salt") if configured else None
    if configured_salt:
        root_secret = str(configured_salt).encode("utf-8")
    else:
        service_account = st.secrets.get("gserviceaccount", {})
        root_material = (
            str(service_account.get("private_key_id", ""))
            + str(service_account.get("private_key", ""))
        )
        if not root_material:
            raise RuntimeError("匿名回答者IDを保護するサーバー秘密値がありません。")
        root_secret = root_material.encode("utf-8")
    return hmac.new(root_secret, event_id.encode("utf-8"), hashlib.sha256).digest()


def _respondent_hash(respondent_id: str, event_id: str) -> str:
    return hmac.new(
        _event_hmac_key(event_id),
        respondent_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _document_id(respondent_hash: str, session_id: str) -> str:
    return f"{respondent_hash}_{session_id}"


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": record.get("session_id"),
        "expectation_score": record.get("expectation_score"),
        "actual_score": record.get("actual_score"),
        "skipped": bool(record.get("skipped", False)),
        "retrospective_expectation": bool(
            record.get("retrospective_expectation", False)
        ),
        "client_updated_at": datetime_to_iso(record.get("client_updated_at")),
        "expectation_updated_at": datetime_to_iso(
            record.get("expectation_updated_at")
        ),
        "actual_updated_at": datetime_to_iso(record.get("actual_updated_at")),
        "updated_at": datetime_to_iso(record.get("updated_at")),
    }


def _load_records_for_respondent(
    db: firestore.Client,
    respondent_hash: str,
) -> list[dict[str, Any]]:
    docs = (
        db.collection(COLLECTION_NAME)
        .where(filter=FieldFilter("respondent_id_hash", "==", respondent_hash))
        .stream(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
    )
    return [doc.to_dict() for doc in docs]


def _load_all_event_records(db: firestore.Client) -> list[dict[str, Any]]:
    docs = db.collection(COLLECTION_NAME).stream(
        retry=FIRESTORE_READ_RETRY,
        timeout=FIRESTORE_TIMEOUT_SECONDS,
    )
    return [doc.to_dict() for doc in docs]


def _content_matches(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    retrospective: bool,
) -> bool:
    return (
        existing.get("expectation_score") == incoming["expectation_score"]
        and existing.get("actual_score") == incoming["actual_score"]
        and bool(existing.get("skipped", False)) == incoming["skipped"]
        and bool(existing.get("retrospective_expectation", False))
        == retrospective
    )


def _sync_response_batch(
    *,
    db: firestore.Client,
    respondent_hash: str,
    entries: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = validate_response_batch(entries, config)
    references = [
        db.collection(COLLECTION_NAME).document(
            _document_id(respondent_hash, entry["session_id"])
        )
        for entry in normalized
    ]
    existing_records = {
        record["session_id"]: record
        for snapshot in db.get_all(
            references,
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        if snapshot.exists
        for record in [snapshot.to_dict()]
    }
    sessions = {
        session["session_id"]: session for session in config["sessions"]
    }

    batch = db.batch()
    writes = 0
    acknowledgements: list[dict[str, Any]] = []
    response_records = dict(existing_records)
    for incoming in normalized:
        session_id = incoming["session_id"]
        existing = existing_records.get(session_id, {})
        existing_client_time = parse_iso_datetime(
            existing.get("client_updated_at")
        )
        incoming_client_time = incoming["client_updated_at"]

        if (
            existing_client_time
            and incoming_client_time < existing_client_time
        ):
            acknowledgements.append(
                {
                    "session_id": session_id,
                    "client_updated_at": incoming_client_time.isoformat(),
                    "status": "server_newer",
                }
            )
            continue

        session_end_at = parse_iso_datetime(sessions[session_id]["end_at"])
        retrospective = calculate_retrospective_expectation(
            previous_expectation=existing.get("expectation_score"),
            previous_retrospective=bool(
                existing.get("retrospective_expectation", False)
            ),
            expectation_score=incoming["expectation_score"],
            expectation_updated_at=incoming["expectation_updated_at"],
            actual_score=incoming["actual_score"],
            actual_updated_at=incoming["actual_updated_at"],
            session_end_at=session_end_at,
        )

        status = "unchanged"
        if not _content_matches(existing, incoming, retrospective):
            document = {
                "event_id": config["event_id"],
                "respondent_id_hash": respondent_hash,
                "session_id": session_id,
                "expectation_score": incoming["expectation_score"],
                "actual_score": incoming["actual_score"],
                "skipped": incoming["skipped"],
                "retrospective_expectation": retrospective,
                "client_updated_at": incoming_client_time,
                "expectation_updated_at": incoming["expectation_updated_at"],
                "actual_updated_at": incoming["actual_updated_at"],
                "updated_at": firestore.SERVER_TIMESTAMP,
                "schema_version": config["schema_version"],
            }
            if not existing:
                document["created_at"] = firestore.SERVER_TIMESTAMP
            batch.set(
                db.collection(COLLECTION_NAME).document(
                    _document_id(respondent_hash, session_id)
                ),
                document,
                merge=True,
            )
            writes += 1
            status = "updated"
            response_records[session_id] = {
                **document,
                "updated_at": datetime.now().astimezone(),
            }

        acknowledgements.append(
            {
                "session_id": session_id,
                "client_updated_at": incoming_client_time.isoformat(),
                "status": status,
            }
        )

    if writes:
        batch.commit(timeout=FIRESTORE_TIMEOUT_SECONDS)

    return {
        "acknowledgements": acknowledgements,
        "records": [
            _serialize_record(record) for record in response_records.values()
        ],
        "write_count": writes,
    }


def _respondent_bundle(
    *,
    loaded: bool = False,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "loaded": loaded,
        "response": response,
        "generated_at": datetime.now().astimezone().isoformat(),
    }


def _handle_component_action(
    action: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    action_type = action.get("type")
    action_id = str(action.get("action_id", ""))
    respondent_id = action.get("respondent_id")
    if not action_id:
        raise ValueError("action_id is required")
    if not is_valid_respondent_id(respondent_id):
        raise ValueError("匿名回答者IDが不正です。")

    db = get_firestore_client()
    if db is None:
        raise RuntimeError("回答データベースへ接続できません。")
    config_event_id = config["event_id"]
    respondent_hash = _respondent_hash(str(respondent_id), config_event_id)

    if action_type == "hydrate":
        records = _load_records_for_respondent(db, respondent_hash)
        return {
            "type": "hydrate",
            "action_id": action_id,
            "ok": True,
            "records": [_serialize_record(record) for record in records],
        }

    if action_type != "sync":
        raise ValueError("Unknown component action")

    now = time.monotonic()
    previous_sync_at = st.session_state.get("cw_last_sync_monotonic", 0.0)
    if previous_sync_at and now - previous_sync_at < 0.75:
        raise ValueError("同期が速すぎます。少し待って再試行してください。")
    st.session_state.cw_last_sync_monotonic = now

    language = str(action.get("language", "ja")).lower()
    notice_text = (
        "Temporarily syncing your answers\n\n"
        "You can continue answering."
        if language == "en"
        else "ご回答を一時送信中\n\nそのまま回答を続けられます。"
    )
    sending_notice = st.toast(notice_text, icon="☁️")
    notice_started_at = time.monotonic()
    try:
        result = _sync_response_batch(
            db=db,
            respondent_hash=respondent_hash,
            entries=action.get("entries"),
            config=config,
        )
    finally:
        remaining_notice_time = 0.75 - (time.monotonic() - notice_started_at)
        if remaining_notice_time > 0:
            time.sleep(remaining_notice_time)
        sending_notice.empty()
    return {
        "type": "sync",
        "action_id": action_id,
        "ok": True,
        **result,
    }


def _render_respondent_view(config: dict[str, Any]) -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background: #000 !important;
        }
        .block-container {
            max-width: 980px !important;
            padding: .35rem .55rem 2rem !important;
        }
        header, footer, #MainMenu, [data-testid="stToolbar"] {
            display: none !important;
        }
        iframe[title="consulting_week_session_feedback"] {
            border: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    bundle = st.session_state.get(
        "cw_component_bundle",
        _respondent_bundle(),
    )
    component_value = _consulting_week_component(
        event=config,
        logo_data_uri=_logo_data_uri(),
        server_bundle=bundle,
        key="consulting-week-2026-form",
        default=None,
    )

    if not isinstance(component_value, dict):
        return
    action_id = str(component_value.get("action_id", ""))
    if not action_id or action_id == st.session_state.get("cw_last_action_id"):
        return

    st.session_state.cw_last_action_id = action_id
    try:
        response = _handle_component_action(component_value, config)
    except (ValueError, RuntimeError) as exc:
        response = {
            "type": component_value.get("type", "unknown"),
            "action_id": action_id,
            "ok": False,
            "error": str(exc),
        }
    except Exception:
        response = {
            "type": component_value.get("type", "unknown"),
            "action_id": action_id,
            "ok": False,
            "error": (
                "サーバーへ同期できませんでした。回答は端末に保存されています。"
            ),
        }
    st.session_state.cw_component_bundle = _respondent_bundle(
        loaded=True,
        response=response,
    )
    st.rerun()


def _qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _admin_authenticated() -> bool:
    if st.session_state.get("cw_admin_authenticated"):
        return True
    correct_password = get_secret_password(st.secrets, "sales_admin")
    if correct_password is None:
        st.error(
            "管理者認証が設定されていません。Secrets の "
            "sales_admin.password を設定してください。"
        )
        return False

    with st.form("cw_admin_login"):
        password = st.text_input(
            "管理者パスワード",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button(
            "集計画面を開く",
            type="primary",
            use_container_width=True,
        )
    if submitted and hmac.compare_digest(password, correct_password):
        st.session_state.cw_admin_authenticated = True
        st.rerun()
    elif submitted:
        st.error("パスワードが違います。")
    return False


def _render_admin_view(config: dict[str, Any]) -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background: #000 !important;
            color: #fff !important;
        }
        .block-container {max-width: 1380px; padding-top: 1.4rem;}
        header, footer, #MainMenu {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.image(str(AUTODESK_LOGO_PATH), width=150)
    st.title("Consulting Week Session Feedback")
    st.caption("運営担当者用・匿名集計")

    if not _admin_authenticated():
        return

    db = get_firestore_client()
    if db is None:
        st.error("回答データベースへ接続できません。")
        return

    if st.button("最新データへ更新", type="secondary"):
        st.rerun()
    records = _load_all_event_records(db)
    aggregate = aggregate_responses(records, config)
    anonymous = anonymized_rows(records)

    unique_respondents = len(
        {
            record.get("respondent_id_hash")
            for record in records
            if record.get("respondent_id_hash")
        }
    )
    metric_cols = st.columns(3)
    metric_cols[0].metric("匿名回答者", unique_respondents)
    metric_cols[1].metric("保存済みセッション回答", len(records))
    metric_cols[2].metric(
        "事後入力の期待値",
        sum(
            1
            for record in records
            if record.get("retrospective_expectation", False)
            and not record.get("skipped", False)
        ),
    )

    aggregate_df = pd.DataFrame(aggregate)
    st.subheader("セッション別集計")
    st.caption(
        "表示順はアジェンダ順です。赤・緑の評価色やランキング表示は行いません。"
    )
    st.dataframe(
        aggregate_df,
        use_container_width=True,
        hide_index=True,
        height=610,
    )

    csv_cols = st.columns(2)
    csv_cols[0].download_button(
        "セッション別集計CSV",
        data=aggregate_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="consulting-week-2026-session-summary.csv",
        mime="text/csv",
        use_container_width=True,
    )
    anonymous_df = pd.DataFrame(
        anonymous,
        columns=[
            "anonymized_respondent_key",
            "session_id",
            "expectation_score",
            "actual_score",
            "total_score",
            "gap_score",
            "skipped",
            "retrospective_expectation",
            "updated_at",
        ],
    )
    csv_cols[1].download_button(
        "匿名回答CSV",
        data=anonymous_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="consulting-week-2026-anonymous-responses.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()
    st.subheader("回答フォーム共有")
    st.code(PUBLIC_RESPONSE_URL, language=None)
    qr_bytes = _qr_png(PUBLIC_RESPONSE_URL)
    qr_col, url_col = st.columns([1, 2])
    qr_col.image(qr_bytes, width=280)
    qr_col.download_button(
        "QRコードをPNGで保存",
        data=qr_bytes,
        file_name="consulting-week-2026-response-qr.png",
        mime="image/png",
        use_container_width=True,
    )
    url_col.markdown(
        f"""
        **回答URL**

        {PUBLIC_RESPONSE_URL}

        **管理URL**

        {PUBLIC_ADMIN_URL}

        **保存先collection**

        `{COLLECTION_NAME}`
        """
    )


def render_consulting_week(
    view: str = "respond", *, configure_page: bool = True
) -> None:
    if configure_page:
        try:
            st.set_page_config(
                page_title="Consulting Week Session Feedback",
                layout="wide",
            )
        except Exception:
            pass
    config = _event_config()
    if view == "admin":
        _render_admin_view(config)
    elif config.get("status") != "active":
        st.image(str(AUTODESK_LOGO_PATH), width=150)
        st.title(config["display_name"])
        st.info("このイベントの回答受付は終了しました。")
    else:
        _render_respondent_view(config)
