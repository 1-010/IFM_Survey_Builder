import streamlit as st
import pandas as pd
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
    # PEMキーの改行コードの表記のブレを補正
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

def save_custom_survey(survey_id, client_name, creator, questions_list):
    db = get_firestore_client()
    if not db:
        return False
    try:
        doc_ref = db.collection("surveys").document(survey_id)
        doc_ref.set({
            "survey_id": survey_id,
            "client_name": client_name,
            "creator": creator,
            "questions": questions_list,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        st.error(f"Firestoreカスタムアンケート保存エラー: {e}")
        return False

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
