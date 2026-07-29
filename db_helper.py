import streamlit as st
import pandas as pd
import hashlib
from google.cloud import firestore
from google.api_core.retry import Retry
from google.oauth2.service_account import Credentials

FIRESTORE_TIMEOUT_SECONDS = 12
FIRESTORE_READ_RETRY = Retry(deadline=FIRESTORE_TIMEOUT_SECONDS)

def get_firestore_client():
    if "gserviceaccount" not in st.secrets:
        st.error("Streamlit Secrets に gserviceaccount が定義されていません。")
        return None
    
    creds_dict = dict(st.secrets["gserviceaccount"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").replace("\r\n", "\n")
        
    try:
        creds = Credentials.from_service_account_info(creds_dict)
        return firestore.Client(credentials=creds, project=creds.project_id)
    except Exception as e:
        st.error(f"Google IAM 認証エラー: {e}")
        return None

def get_custom_survey(survey_id):
    db = get_firestore_client()
    if not db:
        return None
    try:
        doc_ref = db.collection("surveys").document(survey_id)
        doc = doc_ref.get(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        st.error(f"Firestoreカスタムアンケート取得エラー: {e}")
    return None

def save_custom_survey(survey_id, client_name, creator, questions_list, owner_email=None, ai_prompt=None, status="draft", module_name=None):
    db = get_firestore_client()
    if not db:
        return False
    try:
        doc_ref = db.collection("surveys").document(survey_id)
        payload = {
            "survey_id": survey_id,
            "client_name": client_name,
            "creator": creator,
            "questions": questions_list,
            "created_at": firestore.SERVER_TIMESTAMP,
            "owner_email": owner_email or creator,
            "status": status,
            "module_name": module_name or "Custom AI Survey"
        }
        if ai_prompt:
            payload["ai_prompt"] = ai_prompt
            
        doc_ref.set(payload)
        return True
    except Exception as e:
        st.error(f"Firestoreカスタムアンケート保存エラー: {e}")
        return False

def get_surveys_by_owner(owner_email):
    db = get_firestore_client()
    if not db:
        return []
    try:
        docs = db.collection("surveys").where("owner_email", "==", owner_email.strip().lower()).stream(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"Firestore所有者別アンケート取得エラー: {e}")
        return []

def get_all_custom_surveys():
    db = get_firestore_client()
    if not db:
        return []
    try:
        docs = db.collection("surveys").stream(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        surveys = []
        for doc in docs:
            d = doc.to_dict()
            if "survey_id" in d:
                surveys.append(d)
        return surveys
    except Exception as e:
        st.error(f"Firestore全アンケート取得エラー: {e}")
        return []

def update_survey_status(survey_id, status):
    db = get_firestore_client()
    if not db:
        return False
    try:
        doc_ref = db.collection("surveys").document(survey_id)
        doc_ref.update({"status": status})
        return True
    except Exception as e:
        st.error(f"ステータス更新エラー: {e}")
        return False

def _hash_pin(pin):
    return hashlib.sha256(str(pin).encode('utf-8')).hexdigest()

def verify_or_register_sales_user(email, pin):
    db = get_firestore_client()
    if not db or not email or not pin:
        return False, "メールアドレスと暗証番号を入力してください。"
    
    clean_email = email.strip().lower()
    hashed_pin = _hash_pin(pin)
    
    try:
        user_ref = db.collection("sales_users").document(clean_email)
        doc = user_ref.get()
        if doc.exists:
            stored_data = doc.to_dict()
            if stored_data.get("pin_hash") == hashed_pin:
                return True, "ログイン成功"
            else:
                return False, "暗証番号が一致しません。"
        else:
            # First-time registration
            user_ref.set({
                "email": clean_email,
                "pin_hash": hashed_pin,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            return True, "新規登録完了 ログインしました。"
    except Exception as e:
        return False, f"認証エラー: {e}"

def save_response_to_firestore(response_doc):
    db = get_firestore_client()
    if not db:
        return False
    try:
        db.collection("responses").add(response_doc)
        return True
    except Exception as e:
        st.error(f"Firestore回答保存エラー: {e}")
        return False

def load_responses_from_firestore():
    db = get_firestore_client()
    if not db:
        return pd.DataFrame()
    try:
        docs = db.collection("responses").stream(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        records = []
        for doc in docs:
            data = doc.to_dict()
            timestamp = data.get("timestamp")
            respondent = data.get("respondent")
            email = data.get("email")
            exp = data.get("experience_years")
            team = data.get("team") or ""
            survey_id = data.get("survey_id", "default")
            
            for ans in data.get("answers", []):
                records.append({
                    "timestamp": timestamp,
                    "respondent": respondent,
                    "email": email,
                    "experience_years": exp,
                    "department": ans.get("department"),
                    "team": team,
                    "question_id": ans.get("question_id"),
                    "phase": ans.get("phase"),
                    "as_is": ans.get("as_is"),
                    "to_be": ans.get("to_be"),
                    "survey_id": survey_id
                })
        
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        df["as_is"] = pd.to_numeric(df["as_is"], errors='coerce')
        df["to_be"] = pd.to_numeric(df["to_be"], errors='coerce')
        df["domain"] = df["email"].apply(lambda x: x.split("@")[-1].strip() if "@" in str(x) else "")
        return df
    except Exception as e:
        st.error(f"Firestore回答ロードエラー: {e}")
        return pd.DataFrame()

def get_all_custom_survey_ids():
    db = get_firestore_client()
    if not db:
        return []
    try:
        docs = db.collection("surveys").select(["survey_id"]).stream(
            retry=FIRESTORE_READ_RETRY,
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
        return [doc.id for doc in docs]
    except Exception as e:
        st.error(f"FirestoreカスタムアンケートID一覧取得エラー: {e}")
        return []
