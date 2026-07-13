import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import re
import os
import html
from io import BytesIO

from ifm_guardrails import dedupe_response_rows, get_secret_password, validate_questions

# Import Firestore helpers
from db_helper import (
    get_custom_survey,
    save_custom_survey,
    save_response_to_firestore,
    load_responses_from_firestore,
    get_all_custom_survey_ids
)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"
IMAGES_DIR = SCRIPT_DIR / "data" / "images"

# Load default questions
def load_all_questions_json():
    if DATA_JSON.exists():
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_default_questions():
    survey_id = None
    try:
        survey_id = st.query_params.get("survey_id")
    except AttributeError:
        try:
            survey_id = st.experimental_get_query_params().get("survey_id", [None])[0]
        except:
            pass
            
    if survey_id:
        custom_survey = get_custom_survey(survey_id)
        if custom_survey:
            questions = custom_survey.get("questions", [])
            errors = validate_questions(questions)
            if errors:
                st.error("このアンケートの設問定義が壊れているため、回答を開始できません。管理者へお問い合わせください。")
                st.stop()
            return pd.DataFrame(questions), survey_id, custom_survey.get("client_name")
        st.error("指定されたアンケートが見つかりません。URLを確認するか、発行元へお問い合わせください。")
        st.stop()
            
    all_qs = load_all_questions_json()
    return pd.DataFrame(all_qs.get("questions", [])), "default", None

q_df, active_survey_id, client_name = get_default_questions()

# Autodesk Brand Official Color & Layout Guidelines Integration
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: Arial, system-ui, -apple-system, "Segoe UI", sans-serif !important;
        font-size: 15px;
    }
    
    /* Responsive Text Sizes for Mobile */
    @media (max-width: 768px) {
        html, body, [data-testid="stAppViewContainer"] {
            font-size: 16px !important;
        }
        h3 {
            font-size: 1.35rem !important;
        }
        h4 {
            font-size: 1.15rem !important;
        }
        .stSlider {
            margin-bottom: 10px !important;
        }
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 0px !important;
        border: none !important;
        border-left: 1px solid #666666 !important;
        background-color: transparent !important;
        padding: 0px 16px !important;
        box-shadow: none !important;
    }
    
    .stImage img {
        border-radius: 0px !important;
        border: 1px solid #666666 !important;
    }
    
    /* Disable Streamlit Image Zoom Button */
    button[data-testid="stImageZoomButton"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    div[data-baseweb="input"], select, textarea {
        border-radius: 8px !important;
        border: 1px solid #666666 !important;
        background-color: #121212 !important;
        color: #FFFFFF !important;
    }
    
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #FFFF00 !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.05em !important;
        padding: 12px 28px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #E5E500 !important;
    }
    div.stButton > button[data-testid="stBaseButton-primary"] * {
        color: #000000 !important;
    }
    
    div.stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid #666666 !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
        padding: 12px 28px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
        border-color: #FFFF00 !important;
        color: #FFFF00 !important;
    }
    div.stButton > button[data-testid="stBaseButton-secondary"] * {
        color: #FFFFFF !important;
    }
    div.stButton > button[data-testid="stBaseButton-secondary"]:hover * {
        color: #FFFF00 !important;
    }
    
    div.stButton > button[disabled] {
        background-color: #1A1A1A !important;
        color: #666666 !important;
        border-color: #333333 !important;
    }
    div.stButton > button[disabled] * {
        color: #666666 !important;
    }
    
    /* Toggle Switch Styling - Standard Gray & Active green, no ugly yellow */
    div[data-testid="stToggle"] > label > div:first-child {
        background-color: #333333 !important;
    }
    div[data-testid="stToggle"] > label > div:first-child[aria-checked="true"] {
        background-color: #2AD0A9 !important;
    }
    
    /* Slider Color Sync */
    .asis-slider-container div[role="slider"] {
        background-color: #1D91D0 !important;
        border-color: #1D91D0 !important;
    }
    .asis-slider-container .stSlider > div > div > div > div {
        background-color: #1D91D0 !important;
    }
    
    .tobe-slider-container div[role="slider"] {
        background-color: #2AD0A9 !important;
        border-color: #2AD0A9 !important;
    }
    .tobe-slider-container .stSlider > div > div > div > div {
        background-color: #2AD0A9 !important;
    }
    
    /* Force text on yellow badge to be black */
    span[style*="background-color:#FFFF00"], span[style*="background-color: rgb(255, 255, 0)"] {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    
    .stProgress > div > div > div {
        background-color: #FFFF00 !important;
    }
    
    button[data-baseweb="tab"] {
        color: #D5D5CB !important;
        font-size: 0.95rem !important;
        border-bottom-width: 2px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFF00 !important;
        border-bottom-color: #FFFF00 !important;
    }
    
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    [class^="viewerBadge"] {display: none !important;}
    [class*="viewerBadge"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden; display: none !important;}
    
    </style>
    """,
    unsafe_allow_html=True
)

# Google Sheets Helper Functions
def get_gspread_client():
    if "gserviceaccount" not in st.secrets:
        return None
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = dict(st.secrets["gserviceaccount"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").replace("\r\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except:
        return None

def get_worksheet():
    client = get_gspread_client()
    if not client or "gserviceaccount" not in st.secrets:
        return None
    spreadsheet_id = st.secrets["gserviceaccount"].get("spreadsheet_id")
    if not spreadsheet_id:
        return None
    try:
        sh = client.open_by_key(spreadsheet_id)
        try:
            worksheet = sh.worksheet("成熟度回答")
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="成熟度回答", rows="100", cols="11")
            new_headers = ["timestamp", "respondent", "email", "experience_years", "department", "team", "question_id", "phase", "as_is", "to_be", "survey_id"]
            worksheet.append_row(new_headers)
        headers = worksheet.row_values(1)
        if "survey_id" not in headers:
            worksheet.update_cell(1, len(headers) + 1, "survey_id")
        return worksheet
    except:
        return None

def save_response_to_sheets(response_records):
    ws = get_worksheet()
    if not ws:
        return False
    try:
        rows_to_append = []
        for r in response_records:
            rows_to_append.append([
                r["timestamp"], r["respondent"], r["email"], r["experience_years"],
                r["department"], r["team"], r["question_id"], r["phase"], r["as_is"], r["to_be"], r["survey_id"]
            ])
        ws.append_rows(rows_to_append)
        return True
    except:
        return False

def load_responses_from_sheets():
    ws = get_worksheet()
    if not ws:
        return pd.DataFrame()
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["as_is"] = pd.to_numeric(df["as_is"], errors='coerce')
        df["to_be"] = pd.to_numeric(df["to_be"], errors='coerce')
        df["domain"] = df["email"].apply(lambda x: x.split("@")[-1].strip() if "@" in str(x) else "")
        return df
    except:
        return pd.DataFrame()

def load_all_responses_merged():
    df_sheets = load_responses_from_sheets()
    df_firestore = load_responses_from_firestore()

    # Firestore is the canonical source. Sheets is a backup/export surface and
    # must not be concatenated with the same records for analysis.
    if not df_firestore.empty:
        return dedupe_response_rows(df_firestore)
    if "survey_id" not in df_sheets.columns:
        df_sheets["survey_id"] = "default"
    return dedupe_response_rows(df_sheets)

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email.strip()) is not None

if q_df.empty:
    st.stop()

# Image Mapping for IFM
IMAGE_MAPPING = {
    "FI01": "fy27-aec-forma-industry-cloud-imagery.webp",
    "FI02": "brand-image-prototype-1-dark.webp",
    "FI03": "Construction-CCEED-China-0644_with_overlay.webp",
    "FI04": "fy27-water-image-02.webp",
    "FI05": "Ops analytics_Overlay-people collaborating.webp",
    "PE01": "fy27-dm-digital-factory-campaign-visual-01.webp",
    "PE02": "fy27-dm-fusion-industry-cloud-imagery.webp",
    "PE03": "Tech-Center-Birmingham-industrial-robots-086_with_overlay.webp",
    "PE04": "brand-image-prototype-4-dark.webp",
    "PE05": "Ops analytics_Overlay_people in field.webp",
    "FC01": "fy27-aec-forma-industry-cloud-imagery.webp",
    "FC02": "Tech-Center-Birmingham-industrial-robots-086_with_overlay.webp",
    "FC03": "brand-image-prototype-1-dark.webp",
    "FC04": "brand-image-prototype-4-dark.webp",
    "FC05": "Construction-CCEED-China-0644_with_overlay.webp",
    "FC06": "fy27-water-image-02.webp",
    "FC07": "fy27-dm-fusion-industry-cloud-imagery.webp",
    "FC08": "fy27-dm-digital-factory-campaign-visual-01.webp"
}

def render_hero_image(qid):
    img_filename = IMAGE_MAPPING.get(qid)
    if img_filename:
        img_path = IMAGES_DIR / img_filename
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
            return
    st.markdown(
        """
        <div style="border: 1px solid #666666; background-color: #121212; height: 180px; display: flex; align-items: center; justify-content: center; border-radius: 0px; color: #D5D5CB; font-size: 0.9rem; font-family: monospace; margin-bottom: 20px;">
        [ AUTODESK // PRECISION_DESIGN_SYSTEM ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand header: the service name is primary; Autodesk is used descriptively.
header_html = '<div style="display:flex;align-items:end;justify-content:space-between;flex-wrap:wrap;margin:12px 0 16px;gap:16px;"><div><div style="font-size:.78rem;color:#D5D5CB;letter-spacing:.12em;text-transform:uppercase;font-weight:600;">IFM Maturity Assessment</div><div style="font-size:1.85rem;font-weight:700;color:#FFFFFF;letter-spacing:-.03em;">設備管理成熟度アセスメント</div></div><div style="font-size:.8rem;color:#D5D5CB;">for Autodesk Design &amp; Make workflows</div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Client navigation view switcher
is_client_access = False
requested_tab = ""
try:
    is_client_access = "survey_id" in st.query_params
    requested_tab = str(st.query_params.get("tab", "")).lower()
except AttributeError:
    try:
        legacy_params = st.experimental_get_query_params()
        is_client_access = "survey_id" in legacy_params
        requested_tab = str(legacy_params.get("tab", [""])[0]).lower()
    except:
        pass

if is_client_access:
    tabs = st.tabs(["アセスメント回答"])
    tab_input = tabs[0]
    tab_dashboard = None
    tab_admin = None
else:
    if requested_tab == "dashboard":
        tab_dashboard, tab_input, tab_admin = st.tabs(["結果分析", "アセスメント回答", "営業管理"])
    elif requested_tab == "admin":
        tab_admin, tab_input, tab_dashboard = st.tabs(["営業管理", "アセスメント回答", "結果分析"])
    else:
        tab_input, tab_dashboard, tab_admin = st.tabs(["アセスメント回答", "結果分析", "営業管理"])

###  Tab 1: 回答入力フォーム ###
with tab_input:
    if client_name:
        st.info(f"{client_name} 向けアセスメント · アンケートID: {active_survey_id}")
    col_left_form, col_right_chart = st.columns([11, 9])
    
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    num_questions = len(q_df)
    
    if "is_submitted" not in st.session_state:
        st.session_state.is_submitted = False
        
    with col_left_form:
        if st.session_state.is_submitted:
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF;'>アセスメント回答送信完了</h3>", unsafe_allow_html=True)
            st.success("アセスメントの回答が安全に記録されました。ご協力ありがとうございました。")
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
            if st.button("アセスメントを再回答する", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key.startswith(("asis_", "tobe_", "skip_", "res_")) or key in {"agree_privacy", "agree_privacy_step0", "current_step", "is_submitted"}:
                        st.session_state.pop(key, None)
                st.rerun()

        elif st.session_state.current_step == 0:
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF;'>回答者プロファイル ＆ 同意確認</h3>", unsafe_allow_html=True)
            respondent_name = st.text_input("回答者名 *", placeholder="氏名をご記入ください（例: 山田 太郎）", value=st.session_state.get("res_name", ""))
            st.session_state["res_name"] = respondent_name
            
            email_input = st.text_input("メールアドレス *", placeholder="example@autodesk.com", value=st.session_state.get("res_email", ""))
            st.session_state["res_email"] = email_input
            
            experience_years = st.radio(
                "勤続年数 *",
                ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"],
                index=["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"].index(st.session_state.get("res_exp")) if st.session_state.get("res_exp") in ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"] else None,
                horizontal=True,
                key="res_exp_radio_step0"
            )
            st.session_state["res_exp"] = experience_years
            
            specific_team = st.text_input("部署名・チーム名 (任意)", placeholder="例: FM推進部 管理課", value=st.session_state.get("res_team", ""))
            st.session_state["res_team"] = specific_team
            
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            agree_privacy = st.checkbox("個人情報の取り扱い説明事項を確認し、同意します。 *", value=st.session_state.get("agree_privacy", False), key="agree_privacy_step0")
            st.session_state["agree_privacy"] = agree_privacy
            
            if not agree_privacy:
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                st.markdown("<b style='font-size:0.85rem; color:#D5D5CB;'>個人情報の利用目的と保存先</b>", unsafe_allow_html=True)
                privacy_policy_text = "入力された氏名、メールアドレス、所属情報および回答内容は、成熟度分析、結果の連絡、提案内容の改善のために利用し、運用管理者が管理するFirestoreおよびGoogle Sheetsへ保存します。アクセスは担当者とシステム管理者に限定します。保持期間、削除依頼、第三者提供の有無など正式な取扱条件は、発行元が提示する個人情報取扱方針を確認してください。正式な方針が提示されていない場合は回答を開始せず、発行元へお問い合わせください。"
                st.markdown(
                    f'<div style="background-color:#121212; border:1px solid #333333; border-radius:8px; padding:15px; font-size:0.88rem; color:#8C9BA5; line-height:1.5; white-space:pre-wrap; transition: all 0.2s ease;">{privacy_policy_text}</div>',
                    unsafe_allow_html=True
                )
            
            inputs_valid = (
                respondent_name.strip() != "" and 
                email_input.strip() != "" and 
                is_valid_email(email_input) and 
                experience_years is not None and 
                agree_privacy
            )
            
            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
            if st.button("自己アセスメントを開始する", type="primary", disabled=not inputs_valid, use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
                
        else:
            # Keep the mobile flow compact: render only the current question.
            for step_idx in [st.session_state.current_step]:
                q_idx = step_idx - 1
                row = q_df.iloc[q_idx]
                qid = row['question_id']
                
                st.markdown(
                    f"<div style='background-color:#121212; padding:15px; border-left:4px solid #FFFF00; margin-top:20px; border-top:1px solid #333333; border-right:1px solid #333333; border-bottom:1px solid #333333;'>"
                    f"<div style='font-size:0.8rem; color:#FFFF00; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;'>"
                    f"{html.escape(str(row['department']))} 領域  ·  設問 {step_idx} / {num_questions}</div>"
                    f"<h4 style='margin-top:4px; margin-bottom:6px; font-size:1.2rem; font-weight:700; color:#FFFFFF;'>{html.escape(str(row['question_id']))} ({html.escape(str(row['phase']))})</h4>"
                    f"<div style='font-size:0.92rem; line-height:1.45; color:#FFFFFF;'>{html.escape(str(row['question_text']))}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                # スキップトグル (回答済みのステップは強制ロック)
                skip_key = f"skip_{qid}"
                if skip_key not in st.session_state:
                    st.session_state[skip_key] = False
                skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key, disabled=(step_idx < st.session_state.current_step))
                
                # スライダー値の取得
                asis_key = f"asis_{qid}"
                tobe_key = f"tobe_{qid}"
                
                if asis_key not in st.session_state:
                    st.session_state[asis_key] = 2
                if tobe_key not in st.session_state:
                    st.session_state[tobe_key] = 4
                
                if not skip:
                    # レベルカードの表示
                    as_is_val = st.session_state[asis_key]
                    to_be_val = st.session_state[tobe_key]
                    
                    levels_html = "<div style='display: flex; flex-direction: column; gap: 4px; margin-top: 8px; margin-bottom: 12px;'>"
                    for lvl in ["L1", "L2", "L3", "L4", "L5"]:
                        lvl_num = int(lvl[1])
                        is_asis = (as_is_val == lvl_num)
                        is_tobe = (to_be_val == lvl_num)
                        
                        border_color = "rgba(102, 102, 102, 0.15)" 
                        bg_color = "transparent"
                        badge_html = ""
                        
                        if is_asis and is_tobe:
                            border_color = "#FFFF00" 
                            bg_color = "rgba(255, 255, 0, 0.04)"
                            badge_html = "<span style='background-color:#FFFF00; color:#000000; font-size:0.68rem; font-weight:700; padding:1px 4px; border-radius:2px; margin-right:6px;'>As-Is & To-Be</span>"
                        elif is_asis:
                            border_color = "#1D91D0" 
                            bg_color = "rgba(29, 145, 208, 0.06)"
                            badge_html = "<span style='background-color:#1D91D0; color:#FFFFFF; font-size:0.68rem; font-weight:700; padding:1px 4px; border-radius:2px; margin-right:6px;'>As-Is</span>"
                        elif is_tobe:
                            border_color = "#2AD0A9" 
                            bg_color = "rgba(42, 208, 169, 0.03)"
                            badge_html = "<span style='background-color:#2AD0A9; color:#000000; font-size:0.68rem; font-weight:700; padding:1px 4px; border-radius:2px; margin-right:6px;'>To-Be</span>"
                            
                        levels_html += f'<div style="border-left: 3px solid {border_color}; background-color: {bg_color}; padding: 5px 10px; border-top: 1px solid rgba(102,102,102,0.1); border-right: 1px solid rgba(102,102,102,0.1); border-bottom: 1px solid rgba(102,102,102,0.1);"><div style="display: flex; align-items: center; margin-bottom: 2px;">{badge_html}<b style="font-size: 0.78rem; color: #D5D5CB;">Level {lvl_num}</b></div><div style="font-size: 0.8rem; color: #FFFFFF; line-height: 1.35;">{row["levels"][lvl]}</div></div>'
                    levels_html += "</div>"
                    st.markdown(levels_html, unsafe_allow_html=True)
                    
                    # カラー同期されたスライダーの描画 (回答済みのステップは強制ロック)
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown("<div class='asis-slider-container'>", unsafe_allow_html=True)
                        st.slider("現状の成熟度評価 (As-Is)", 1, 5, key=asis_key, disabled=(step_idx < st.session_state.current_step))
                        st.markdown("</div>", unsafe_allow_html=True)
                    with col_s2:
                        st.markdown("<div class='tobe-slider-container'>", unsafe_allow_html=True)
                        st.slider("将来の目標成熟度 (To-Be)", 1, 5, key=tobe_key, disabled=(step_idx < st.session_state.current_step))
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='padding:10px 0; color:#8C9BA5; font-size:0.9rem;'>※ この設問はスキップされています</div>", unsafe_allow_html=True)
                
                # 「現在フォーカスしている最新の設問」のみ操作ボタンを表示する
                if step_idx == st.session_state.current_step:
                    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
                    if step_idx > 1 and st.button("前の設問に戻って修正する", type="secondary", use_container_width=True, key=f"back_btn_{qid}"):
                        st.session_state.current_step -= 1
                        st.rerun()
                    if step_idx < num_questions:
                        if st.button("回答を確定して次の設問へ", type="primary", use_container_width=True, key=f"next_btn_{qid}"):
                            st.session_state.current_step += 1
                            st.rerun()
                    else:
                        # 最終設問の最後の送信ボタン
                        profile_valid = (
                            st.session_state.get("res_name", "").strip() != "" and
                            st.session_state.get("res_email", "").strip() != "" and
                            is_valid_email(st.session_state.get("res_email", "")) and
                            st.session_state.get("res_exp") is not None and
                            st.session_state.get("agree_privacy", False)
                        )
                        
                        submit_disabled = not profile_valid
                        submit_clicked = st.button("アセスメント結果を最終送信する", type="primary", disabled=submit_disabled, use_container_width=True, key="final_submit_btn")
                        
                        if not st.session_state.get("agree_privacy", False):
                            st.warning("送信するには個人情報の取り扱いへの同意が必要です。")

    with col_right_chart:
        # 現在アクティブな設問IDのイメージを表示
        if st.session_state.is_submitted:
            render_hero_image("FI01")
        elif st.session_state.current_step == 0:
            render_hero_image("FI01") 
        else:
            current_active_qid = q_df.iloc[st.session_state.current_step - 1]['question_id']
            render_hero_image(current_active_qid)
            
        st.markdown("<h4 style='margin-bottom:5px; font-weight:600; font-size:1.1rem; color:#D5D5CB;'>ライブ成熟度プロファイル</h4>", unsafe_allow_html=True)
        
        plot_categories = []
        plot_asis = []
        plot_tobe = []
        
        for idx, r in q_df.iterrows():
            q_id = r['question_id']
            is_skipped = st.session_state.get(f"skip_{q_id}", False)
            as_is = st.session_state.get(f"asis_{q_id}", 0) if not is_skipped else 0
            to_be = st.session_state.get(f"tobe_{q_id}", 0) if not is_skipped else 0
            
            plot_categories.append(f"{r['phase']}\n({q_id})")
            plot_asis.append(as_is)
            plot_tobe.append(to_be)
            
        if plot_categories:
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=plot_asis + [plot_asis[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='現在の評価 (As-Is)',
                line_color='#1D91D0',
                fillcolor='rgba(29, 145, 208, 0.08)',
                line=dict(width=1.5),
                opacity=0.7
            ))
            fig.add_trace(go.Scatterpolar(
                r=plot_tobe + [plot_tobe[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='将来の目標 (To-Be)',
                line_color='#2AD0A9',
                fillcolor='rgba(42, 208, 169, 0.04)',
                line=dict(width=1.2, dash='dash'),
                opacity=0.5
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickvals=[1, 2, 3, 4, 5],
                        gridcolor='rgba(102, 102, 102, 0.15)',
                        linecolor='rgba(102, 102, 102, 0.2)',
                        tickfont=dict(color='#666666', size=8)
                    ),
                    angularaxis=dict(
                        gridcolor='rgba(102, 102, 102, 0.15)',
                        linecolor='rgba(102, 102, 102, 0.2)',
                        tickfont=dict(color='#D5D5CB', size=8.5, family='Inter')
                    ),
                    bgcolor='rgba(0,0,0,0)'
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.28,
                    xanchor="center",
                    x=0.5,
                    font=dict(color='#D5D5CB', size=10)
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=60, r=60, t=20, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            answered_count = sum(1 for idx, r in q_df.iterrows() if st.session_state.get(f"asis_{r['question_id']}") is not None or st.session_state.get(f"skip_{r['question_id']}"))
            st.progress(answered_count / num_questions)
            st.markdown(f"<div style='text-align:right; font-size:0.75rem; color:#666666; margin-top:2px;'>回答進捗: {answered_count} / {num_questions} 問</div>", unsafe_allow_html=True)

    # 最終送信処理の実行（デバッグ用トレース出力付き）
    if not st.session_state.is_submitted and st.session_state.current_step == num_questions and 'submit_clicked' in locals() and submit_clicked:
        res_name = st.session_state.get("res_name", "").strip()
        res_email = st.session_state.get("res_email", "").strip()
        res_exp = st.session_state.get("res_exp")
        res_team = st.session_state.get("res_team", "").strip()
        agree_privacy = st.session_state.get("agree_privacy", False)
        
        if res_name and res_email and is_valid_email(res_email) and res_exp and agree_privacy:
            timestamp = datetime.now().isoformat()
            records = []
            answers_list = []
            
            for _, r in q_df.iterrows():
                q_id = r['question_id']
                is_skipped = st.session_state.get(f"skip_{q_id}", False)
                as_is_val = "N/A" if is_skipped else st.session_state.get(f"asis_{q_id}", 2)
                to_be_val = "N/A" if is_skipped else st.session_state.get(f"tobe_{q_id}", 4)
                
                records.append({
                    "timestamp": timestamp,
                    "respondent": res_name,
                    "email": res_email,
                    "experience_years": res_exp,
                    "department": r['department'],
                    "team": res_team,
                    "question_id": q_id,
                    "phase": r['phase'],
                    "as_is": as_is_val,
                    "to_be": to_be_val,
                    "survey_id": active_survey_id
                })
                
                answers_list.append({
                    "question_id": q_id,
                    "phase": r['phase'],
                    "department": r['department'],
                    "as_is": as_is_val,
                    "to_be": to_be_val
                })
                
            firestore_doc = {
                "timestamp": timestamp,
                "respondent": res_name,
                "email": res_email,
                "experience_years": res_exp,
                "team": res_team,
                "survey_id": active_survey_id,
                "answers": answers_list
            }
                
            with st.spinner("結果を送信中..."):
                fs_success = False
                try:
                    fs_success = save_response_to_firestore(firestore_doc)
                except Exception as e:
                    st.error(f"Firestore送信エラー: {e}")
                    
                sheets_success = False
                if fs_success:
                    try:
                        sheets_success = save_response_to_sheets(records)
                    except Exception as e:
                        st.error(f"Google Sheets送信エラー: {e}")
                
                if fs_success:
                    st.balloons()
                    st.session_state.is_submitted = True
                    st.rerun()
                else:
                    st.error("データの格納に失敗しました。認証鍵またはデータベースの接続制限を確認してください。")

###  Tab 2: 結果分析ダッシュボード ###
if tab_dashboard:
    with tab_dashboard:
        st.header("成熟度アセスメントの分析・比較")
        dash_pw = st.text_input("結果分析ダッシュボード閲覧用パスワード", type="password", key="dash_pw_input")
        correct_dash_pw = get_secret_password(st.secrets, "sales_admin")
        if correct_dash_pw is None:
            st.error("管理者認証が設定されていません。Secrets の sales_admin.password を設定してください。")
        elif dash_pw == correct_dash_pw:
            st.success("認証されました。")
            resp_df_raw = load_all_responses_merged()
            
            if resp_df_raw.empty:
                st.warning("現在、回答データが存在しません。")
            else:
                # 各回答レコードにサーベイタイプ属性を追加
                def get_survey_type_by_qid(qid):
                    if str(qid).startswith("FC"):
                        return "工場設計・プロダクトクラウド"
                    elif str(qid).startswith("AE"):
                        return "建築設計・施工 BIM"
                    elif str(qid).startswith("CI"):
                        return "土木・インフラ CIM"
                    elif str(qid).startswith("MF"):
                        return "製品設計・開発 デジタル"
                    else:
                        return "IFM 設備管理成熟度"
                
                resp_df_raw["survey_type"] = resp_df_raw["question_id"].apply(get_survey_type_by_qid)
                
                st.subheader("絞り込みとグループ比較")
                
                # 1. まず大元のサーベイモデルでのフィルタ
                unique_survey_types = ["すべて", "IFM 設備管理成熟度", "工場設計・プロダクトクラウド", "建築設計・施工 BIM", "土木・インフラ CIM", "製品設計・開発 デジタル"]
                selected_survey_type = st.selectbox("分析対象サーベイモデル (設問体系)", unique_survey_types, key="main_survey_type_filter")
                
                # サーベイタイプで足切りしたデータ
                if selected_survey_type == "すべて":
                    resp_df = resp_df_raw.copy()
                else:
                    resp_df = resp_df_raw[resp_df_raw["survey_type"] == selected_survey_type]
                
                # 2. 連動して他のフィルタ用ユニークリストを作成
                unique_domains = sorted([str(d) for d in resp_df['domain'].unique() if d and pd.notna(d)])
                registered_surveys = get_all_custom_survey_ids()
                unique_surveys = sorted(list(set([str(s) for s in resp_df['survey_id'].unique() if s and pd.notna(s)] + registered_surveys + ["default"])))
                unique_years = ["すべて", "0～2年", "2～5年", "5～10年", "10～15年", "15年以上"]
                
                # サーベイタイプに応じた動的な部門（カテゴリ）の選択肢
                if "建築設計" in selected_survey_type:
                    cat_options = ["両方", "設計のみ", "施工のみ"]
                    cat_map = {"両方": "両方", "設計のみ": "設計", "施工のみ": "施工"}
                elif "土木" in selected_survey_type:
                    cat_options = ["両方", "設計のみ", "施工のみ"]
                    cat_map = {"両方": "両方", "設計のみ": "設計", "施工のみ": "施工"}
                elif "製品設計" in selected_survey_type:
                    cat_options = ["両方", "設計のみ", "製造のみ"]
                    cat_map = {"両方": "両方", "設計のみ": "設計", "製造のみ": "製造"}
                else:
                    cat_options = ["両方", "生産技術のみ", "工場建築・建設のみ"]
                    cat_map = {"両方": "両方", "生産技術のみ": "生産技術", "工場建築・建設のみ": "工場建築・建設"}

                compare_mode = st.checkbox("2つのグループを比較する（比較モード）", value=False, key="dash_compare")

                def filter_data(data, domain, exp, team_kw, cat_selection, survey):
                    filtered = data.copy()
                    if survey != "すべて":
                        filtered = filtered[filtered['survey_id'] == survey]
                    if domain != "すべて":
                        filtered = filtered[filtered['domain'] == domain]
                    if exp != "すべて":
                        filtered = filtered[filtered['experience_years'] == exp]
                    if team_kw.strip():
                        filtered = filtered[filtered['team'].str.contains(team_kw.strip(), case=False, na=False)]
                    
                    target_dept = cat_map.get(cat_selection)
                    if target_dept and target_dept != "両方":
                        filtered = filtered[filtered['department'] == target_dept]
                    return filtered

                if compare_mode:
                    col_filter_a, col_filter_b = st.columns(2)
                    with col_filter_a:
                        st.markdown("#### グループA の条件")
                        survey_a = st.selectbox("アンケートID (グループA)", ["すべて"] + unique_surveys, key="survey_a")
                        domain_a = st.selectbox("ドメイン (グループA)", ["すべて"] + unique_domains, key="domain_a")
                        exp_a = st.selectbox("勤続年数 (グループA)", unique_years, key="exp_a")
                        team_a = st.text_input("部署名（部分一致・グループA）", key="team_a", placeholder="例: 技術部")
                        cat_a = st.radio("表示カテゴリ (グループA)", cat_options, key="cat_a", horizontal=True)
                        
                    with col_filter_b:
                        st.markdown("#### グループB の条件")
                        survey_b = st.selectbox("アンケートID (グループB)", ["すべて"] + unique_surveys, key="survey_b")
                        domain_b = st.selectbox("ドメイン (グループB)", ["すべて"] + unique_domains, key="domain_b")
                        exp_b = st.selectbox("勤続年数 (グループB)", unique_years, key="exp_b")
                        team_b = st.text_input("部署名（部分一致・グループB）", key="team_b", placeholder="例: 建築")
                        cat_b = st.radio("表示カテゴリ (グループB)", cat_options, key="cat_b", horizontal=True)
                        
                    df_a = filter_data(resp_df, domain_a, exp_a, team_a, cat_a, survey_a)
                    df_b = filter_data(resp_df, domain_b, exp_b, team_b, cat_b, survey_b)
                else:
                    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                    with col_f1:
                        survey_a = st.selectbox("アンケートID", ["すべて"] + unique_surveys, key="single_survey")
                    with col_f2:
                        domain_a = st.selectbox("メールアドレスのドメイン", ["すべて"] + unique_domains, key="single_domain")
                    with col_f3:
                        exp_a = st.selectbox("勤続年数", unique_years, key="single_exp")
                    with col_f4:
                        team_a = st.text_input("部署名（部分一致で検索）", key="single_team", placeholder="例: 生産技術")
                    cat_a = st.radio("表示カテゴリ", cat_options, key="single_cat", horizontal=True)
                    df_a = filter_data(resp_df, domain_a, exp_a, team_a, cat_a, survey_a)
                    df_b = pd.DataFrame()

                # ---  サマリーインフォメーション (回答人数) ---
                st.markdown("<hr style='border-color:#333333; margin:15px 0;'>", unsafe_allow_html=True)
                col_sum1, col_sum2 = st.columns([1, 2])
                with col_sum1:
                    num_a = df_a['email'].nunique() if not df_a.empty else 0
                    if compare_mode:
                        num_b = df_b['email'].nunique() if not df_b.empty else 0
                        st.metric("有効回答者数 (グループA / B)", f"{num_a}名 / {num_b}名")
                    else:
                        st.metric("有効回答者数 (選択グループ)", f"{num_a}名")
                
                with col_sum2:
                    if not df_a.empty:
                        # アンケートIDごとの回答人数内訳表示
                        cnt_df = df_a.groupby('survey_id')['email'].nunique().reset_index()
                        cnt_df.columns = ["アンケートID (サーベイID)", "回答人数"]
                        st.dataframe(cnt_df, use_container_width=True, hide_index=True, height=110)
                    else:
                        st.write("該当するデータがありません")

                # --- ⬇ 生データダウンロード (CSV) ---
                if not df_a.empty:
                    # 回答者ごとに1行にするワイド形式の作成
                    try:
                        df_wide = df_a.pivot_table(
                            index=["timestamp", "respondent", "email", "experience_years", "team", "survey_id", "survey_type"],
                            columns="question_id",
                            values=["as_is", "to_be"],
                            aggfunc="first"
                        )
                        # カラム名のフラット化
                        df_wide.columns = [f"{val}_{qid}" for val, qid in df_wide.columns]
                        df_wide = df_wide.reset_index()
                        
                        csv_data = df_wide.to_csv(index=False, encoding='utf-8-sig') # Excelで開いても文字化けしないBOM付UTF-8
                        
                        st.download_button(
                            label=f"⬇ 選択したデータの生回答一覧 (CSV) をダウンロード",
                            data=csv_data,
                            file_name=f"autodesk_assessment_raw_{selected_survey_type}_{survey_a}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.warning(f"CSV変換中にエラーが発生しました: {e}")

                st.markdown("<h4 style='margin-top:15px; margin-bottom:5px; color:#FFFFFF;'>アセスメント レーダーチャート比較</h4>", unsafe_allow_html=True)

                # レーダーチャート比較プロットの全アセスメントモデル動的対応
                def detect_survey_type_and_sort(df):
                    if df.empty:
                        return df, []
                    
                    qids = df['question_id'].unique()
                    all_qs = load_all_questions_json()
                    
                    # 判別ロジック
                    if any(str(q).startswith("FC") for q in qids):
                        base_qs = all_qs.get("factory_cloud_questions", [])
                    elif any(str(q).startswith("AE") for q in qids):
                        base_qs = all_qs.get("aec_questions", [])
                    elif any(str(q).startswith("CI") for q in qids):
                        base_qs = all_qs.get("civil_questions", [])
                    elif any(str(q).startswith("MF") for q in qids):
                        base_qs = all_qs.get("mfg_questions", [])
                    else:
                        base_qs = all_qs.get("questions", [])
                        
                    # 正しい設問順序リストを作成
                    order_map = {q["question_id"]: i for i, q in enumerate(base_qs)}
                    
                    df_sorted = df.copy()
                    df_sorted["sort_idx"] = df_sorted["question_id"].map(order_map).fillna(99)
                    df_sorted = df_sorted.sort_values("sort_idx")
                    
                    theta_labels = [f"{q['phase']}\n({q['question_id']})" for q in base_qs if q["question_id"] in qids]
                    for qid in qids:
                        if qid not in order_map:
                            theta_labels.append(f"不明\n({qid})")
                            
                    return df_sorted, theta_labels

                df_a_sorted, theta_labels = detect_survey_type_and_sort(df_a)
                
                agg_a = df_a_sorted.groupby(['question_id', 'phase', 'sort_idx'])[['as_is', 'to_be']].mean().reset_index()
                agg_a = agg_a.sort_values('sort_idx')
                
                fig = go.Figure()
                if not agg_a.empty and theta_labels:
                    fig.add_trace(go.Scatterpolar(
                        r=agg_a['as_is'].tolist() + [agg_a['as_is'].tolist()[0]],
                        theta=theta_labels + [theta_labels[0]],
                        fill='toself',
                        name='グループA: 現状の評価 (As-Is)',
                        line_color='#1D91D0',
                        fillcolor='rgba(29, 145, 208, 0.1)',
                        line=dict(width=1.5)
                    ))
                    fig.add_trace(go.Scatterpolar(
                        r=agg_a['to_be'].tolist() + [agg_a['to_be'].tolist()[0]],
                        theta=theta_labels + [theta_labels[0]],
                        fill='toself',
                        name='グループA: 将来の目標 (To-Be)',
                        line_color='#2AD0A9',
                        fillcolor='rgba(42, 208, 169, 0.05)',
                        line=dict(width=1.2, dash='dash')
                    ))
                
                if compare_mode and not df_b.empty:
                    df_b_sorted, _ = detect_survey_type_and_sort(df_b)
                    agg_b = df_b_sorted.groupby(['question_id', 'phase', 'sort_idx'])[['as_is', 'to_be']].mean().reset_index()
                    agg_b = agg_b.sort_values('sort_idx')
                    if not agg_b.empty and theta_labels:
                        fig.add_trace(go.Scatterpolar(
                            r=agg_b['as_is'].tolist() + [agg_b['as_is'].tolist()[0]],
                            theta=theta_labels + [theta_labels[0]],
                            fill='toself',
                            name='グループB: 現状の評価 (As-Is)',
                            line_color='#F2520A',
                            fillcolor='rgba(242, 82, 10, 0.1)',
                            line=dict(width=1.5)
                        ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 5], 
                            gridcolor='rgba(102, 102, 102, 0.15)',
                            linecolor='rgba(102, 102, 102, 0.2)',
                            tickfont=dict(color='#666666', size=8)
                        ),
                        angularaxis=dict(
                            gridcolor='rgba(102, 102, 102, 0.15)',
                            linecolor='rgba(102, 102, 102, 0.2)',
                            tickfont=dict(color='#D5D5CB', size=8.5, family='Inter')
                        ),
                        bgcolor='rgba(0,0,0,0)'
                    ),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#FFFFFF'),
                    margin=dict(l=60, r=60, t=20, b=40)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 組織内認識ギャップ分析セクション
                st.markdown("<hr style='border-color:#333333; margin:25px 0;'>", unsafe_allow_html=True)
                st.subheader("組織内・認識の歪み（ギャップ）分析")
                
                if len(df_a['email'].unique()) < 2:
                    st.info("※ このアンケートIDに対する複数回答データが不足しています。組織内ギャップ分析を行うには2名以上の回答が必要です。")
                else:
                    st.markdown("<p style='font-size:0.92rem; color:#D5D5CB; margin-bottom:15px;'>同じアンケートIDに対する複数名の回答から、現場層（勤続年数5年未満）と意思決定層（勤続年数10年以上）の間の【認識ギャップ】を抽出します。</p>", unsafe_allow_html=True)
                    
                    genba_df = df_a_sorted[df_a_sorted['experience_years'].isin(["0～2年", "2～5年"])]
                    mgmt_df = df_a_sorted[df_a_sorted['experience_years'].isin(["10～15年", "15年以上"])]
                    
                    agg_genba = genba_df.groupby(['question_id', 'phase', 'sort_idx'])['as_is'].mean().reset_index().sort_values('sort_idx')
                    agg_mgmt = mgmt_df.groupby(['question_id', 'phase', 'sort_idx'])['as_is'].mean().reset_index().sort_values('sort_idx')
                    
                    fig_gap = go.Figure()
                    
                    if not agg_genba.empty and theta_labels:
                        fig_gap.add_trace(go.Scatterpolar(
                            r=agg_genba['as_is'].tolist() + [agg_genba['as_is'].tolist()[0]],
                            theta=theta_labels + [theta_labels[0]],
                            fill='toself',
                            name='現場担当層 (勤続5年未満) - As-Is',
                            line_color='#2AD0A9',
                            fillcolor='rgba(42, 208, 169, 0.04)',
                            line=dict(width=1.5)
                        ))
                        
                    if not agg_mgmt.empty and theta_labels:
                        fig_gap.add_trace(go.Scatterpolar(
                            r=agg_mgmt['as_is'].tolist() + [agg_mgmt['as_is'].tolist()[0]],
                            theta=theta_labels + [theta_labels[0]],
                            fill='toself',
                            name='意思決定層 (勤続10年以上) - As-Is',
                            line_color='#FFFF00',
                            fillcolor='rgba(255, 255, 0, 0.04)',
                            line=dict(width=1.5)
                        ))
                        
                    fig_gap.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True, 
                                range=[0, 5], 
                                tickvals=[1, 2, 3, 4, 5],
                                gridcolor='rgba(102, 102, 102, 0.15)',
                                linecolor='rgba(102, 102, 102, 0.2)',
                                tickfont=dict(color='#666666', size=8)
                            ),
                            angularaxis=dict(
                                gridcolor='rgba(102, 102, 102, 0.15)',
                                linecolor='rgba(102, 102, 102, 0.2)',
                                tickfont=dict(color='#D5D5CB', size=8.5)
                            ),
                            bgcolor='rgba(0,0,0,0)'
                        ),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#FFFFFF'),
                        margin=dict(l=60, r=60, t=20, b=40)
                    )
                    
                    col_g1, col_g2 = st.columns([10, 8])
                    with col_g1:
                        st.plotly_chart(fig_gap, use_container_width=True)
                    with col_g2:
                        st.markdown("<h5 style='color:#FFFFFF; font-weight:700; margin-bottom:10px;'> 組織内認識不一致度アラート</h5>", unsafe_allow_html=True)
                        
                        gap_details = []
                        for q in df_a_sorted['question_id'].unique():
                            val_genba = genba_df[genba_df['question_id'] == q]['as_is'].mean()
                            val_mgmt = mgmt_df[mgmt_df['question_id'] == q]['as_is'].mean()
                            
                            if pd.notna(val_genba) and pd.notna(val_mgmt):
                                diff = abs(val_mgmt - val_genba)
                                phase_name = df_a_sorted[df_a_sorted['question_id'] == q]['phase'].iloc[0]
                                gap_details.append({"qid": q, "phase": phase_name, "diff": diff, "genba": val_genba, "mgmt": val_mgmt})
                                
                        gap_details_sorted = sorted(gap_details, key=lambda x: x["diff"], reverse=True)
                        
                        if gap_details_sorted:
                            display_err_count = 0
                            for i, item in enumerate(gap_details_sorted[:3]):
                                if item["diff"] >= 0.5:
                                    st.markdown(
                                        f"<div style='background-color:#121212; padding:10px 14px; border-left:3px solid #FF5252; margin-bottom:8px;'>"
                                        f"<b style='color:#FF5252;'>不一致度 第{i+1}位: {item['qid']} ({item['phase']})</b><br>"
                                        f"<span style='font-size:0.82rem; color:#D5D5CB;'>意思決定層 平均: <b>{item['mgmt']:.1f}</b> / 現場層 平均: <b>{item['genba']:.1f}</b> (乖離: {item['diff']:.1f})</span>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                    display_err_count += 1
                            if display_err_count == 0:
                                st.write("現場層と意思決定層の間で認識ギャップはありません。")
                        else:
                            st.write("データが不足しています。")

                # --- Autodesk製品提案マッピング参照 ---
                st.markdown("<hr style='border-color:#333333; margin:25px 0;'>", unsafe_allow_html=True)
                st.subheader("Autodesk製品提案マッピング仕様")
                st.write("アセスメント設問がどのAutodesk製品の提案や価値訴求に結びつくかを整理したマッピングです。")
                
                with st.expander("各設問と製品提案シナリオのマッピングを表示する"):
                    # Mapping definitions for all 5 sets
                    all_mappings = {
                        "設備管理成熟度アセスメント (Default - PE/FI)": {
                            "PE01": {"dept": "生産技術", "phase": "計画", "title": "PE01 (計画): 生産・工程計画やレイアウト設備検討におけるデータ活用", "products": "Factory Design Utilities (FDU), AutoCAD Architecture, Inventor", "value_pitch": "2D-3D双方向同期レイアウト設計による手戻り防止。2Dでの簡易配置が3Dへ即座に反映され、設備干渉の早期発見が可能。", "sales_hint": "L1-L2レベル（2D中心）の顧客には、FDUを用いた2D-3Dレイアウト同期と、標準アセットライブラリによる配置設計の高速化を提案。"},
                            "PE02": {"dept": "生産技術", "phase": "設計", "title": "PE02 (設計): 設備やラインの設計プロセスにおけるデータ活用", "products": "Autodesk Inventor, iLogic, Informed Design", "value_pitch": "パラメータ駆動設計とモデリングルールの標準化。Informed Designにより製造可能な設計条件をパラメータとしてロックし、Revitへ出力可能。", "sales_hint": "L2-L3の顧客には、iLogicによる定型モデリングの自動化、およびInformed Designによるモジュール製品のデジタルカタログ化・Revitファミリ化を提案。"},
                            "PE03": {"dept": "生産技術", "phase": "検証", "title": "PE03 (検証): 設計内容の検証やシミュレーションにおけるデータ活用", "products": "Autodesk Navisworks Manage, Inventor Simulation", "value_pitch": "マルチサプライヤ設備データの統合、および自動干渉チェックによる施工前エラー検出。構造シミュレーションによる動作検証。", "sales_hint": "L3-L4の顧客には、Navisworksを用いた干渉チェック自動化と設計変更プロセスのデジタル追跡（Issues連携）を提案。"},
                            "PE04": {"dept": "生産技術", "phase": "建設", "title": "PE04 (建設): 設備の導入や建設段階の進捗管理におけるデータ活用", "products": "Autodesk Construction Cloud (ACC) / Build, Navisworks (4D)", "value_pitch": "現場設備導入の進捗と計画のデジタル管理、4D施工シミュレーションによる現場干渉と作業順序の可視化・最適化。", "sales_hint": "施工段階の情報分断があるL2-L3にはACCによるチェックリスト管理、L4以上には4D連動施工計画を提案して現場手戻りを防止。"},
                            "PE05": {"dept": "生産技術", "phase": "運用", "title": "PE05 (運用): 設備や生産ラインの運用・保全管理におけるデータ活用", "products": "Autodesk Tandem, MES Integration APIs", "value_pitch": "竣工BIMモデルからデジタルツインへの移行。工場内IoTセンサーや生産設備データ（MES）と連携し、稼働保全・予知保全を実現。", "sales_hint": "運用フェーズのL3-L4顧客へTandemを訴求し、設備状態モニタリングからデジタルツインでの自動最適化へのロードマップを提示。"},
                            "FI01": {"dept": "工場建築・建設", "phase": "計画", "title": "FI01 (計画): 工場建築の計画策定や空間検討におけるデータ活用", "products": "Autodesk Revit, FormIt, Autodesk Docs", "value_pitch": "工場建築の初期コンセプト空間計画のデジタル可視化と、共通データ環境（CDE）による要件情報の一元管理・共有。", "sales_hint": "L1-L2レベルの建築計画検討をRevitの初期ボリュームスタディとDocsによる要件管理でデジタル化することを提案。"},
                            "FI02": {"dept": "工場建築・建設", "phase": "設計", "title": "FI02 (設計): 工場建築の設計プロセスにおけるデータ活用", "products": "Autodesk Revit (BIM), BIM Collaborate Pro", "value_pitch": "属性（メタデータ）情報を持つインテリジェントBIMモデルの構築と、意匠・構造・設備（MEP）間のクラウドリアルタイム共同設計設計。", "sales_hint": "L2-L3の3Dモデリングから、属性情報を付与したBIM設計（Revit）とクラウド共同設計（BIM Collaborate Pro）への移行を推進。"},
                            "FI03": {"dept": "工場建築・建設", "phase": "検証", "title": "FI03 (検証): 工場建築の検証（干渉チェックや施工性確認）におけるデータ活用", "products": "Autodesk Navisworks Manage, BIM Collaborate (Coordination)", "value_pitch": "建物構造と付帯・製造設備間の自動衝突検出（干渉チェック）。VR検証による設計不整合の現場着工前クリア。", "sales_hint": "L2-L3の目視チェックから、Navisworks/BIM Collaborateを用いた自動衝突検出と指摘事項（Issues）ワークフローの運用を提案。"},
                            "FI04": {"dept": "工場建築・建設", "phase": "建設", "title": "FI04 (建設): 工場建築の施工計画や現場管理におけるデータ活用", "products": "Autodesk Build, ReCap Pro (Point Cloud)", "value_pitch": "3Dレーザースキャン点群（ReCap）とBIMモデルの重ね合わせによる出来形検査。現場施工計画のリアルタイム更新管理。", "sales_hint": "L3-L4の出来形検証・進捗管理に対して、ReCapの点群とAutodesk Buildによる現場施工管理の組み合わせを提案。"},
                            "FI05": {"dept": "工場建築・建設", "phase": "運用", "title": "FI05 (運用): 工場の建物・設備の運用や保守管理におけるデータ活用", "products": "Autodesk Tandem, Facility Manager APIs", "value_pitch": "建物ファシリティマネジメント用のデジタルツイン。ライフサイクル管理や修繕履歴の紐付けによる、建物の省エネ・運用効率最適化。", "sales_hint": "L3-L4の建物保全業務に対し、Tandemを用いた空間・アセットの一元的なFM運用と、将来的なスマートビルディング化を推進。"}
                        },
                        "工場設計・プロダクトクラウドアセスメント (Factory Cloud - FC)": {
                            "FC01": {"dept": "工場設計", "phase": "初期計画・環境分析", "title": "FC01 (初期計画・環境分析): 敷地風向・日影解析等の初期検討", "products": "Autodesk Forma", "value_pitch": "AIによる迅速な敷地環境シミュレーションにより、初期計画段階での気流・日照問題を秒速で解決し手戻りを劇的に削減します。", "sales_hint": "風向・日照データを手作業で集計しているL1-L2顧客に対し、クラウド上での一撃シミュレーションによる工期圧縮を提案。"},
                            "FC02": {"dept": "工場設計", "phase": "工程シミュレーション", "title": "FC02 (工程シミュレーション): 時間軸を考慮した搬送ルート最適化", "products": "Autodesk FlexSim", "value_pitch": "工場内レイアウトと連携した動的なボトルネック検出。工程内のモノの流れを可視化し、ライン効率を最大化します。", "sales_hint": "搬送シミュレーションを頭の中や表計算で行っているL1-L2顧客に、動的な3D物流・ボトルネック可視化の重要性をフックに提案。"},
                            "FC03": {"dept": "工場設計", "phase": "3Dレイアウト同期", "title": "FC03 (3Dレイアウト同期): 2D/3D図面の双方向整合性維持", "products": "Factory Design Utilities (FDU)", "value_pitch": "AutoCADとInventor間の完全双方向同期。2Dの配置図面が3D設備モデルとリアルタイムで連動し、整合性を自動維持します。", "sales_hint": "2Dと3Dの図面二重作成に苦しむL2-L3のエンジニアにFDUを刺し、設計スピード向上と手戻りゼロを訴求。"},
                            "FC04": {"dept": "工場設計", "phase": "AI支援モデリング", "title": "FC04 (AI支援モデリング): 設計プロセスの自律化・自動化", "products": "AIモデリング (Navastoなど), ジェネレーティブデザイン", "value_pitch": "設計条件や過去データをもとにした、レイアウト設計案のAI自動生成と、エンジニアリング意思決定の自律化支援。", "sales_hint": "L3-L4の先進企業に対し、設計条件から最適な機器配置をAI生成する高度設計自動化ロードマップを提案。"},
                            "FC05": {"dept": "工場設計", "phase": "作図自動化", "title": "FC05 (作図自動化): 定型業務・BOM・図面出力の自動化", "products": "AutoCAD Mechanical, AutoCAD APIs/LISP", "value_pitch": "専用ツールセットやAPI/LISPスクリプトを活用した、2D詳細図面の自動生成とBOM（部品表）出力の自動化。", "sales_hint": "定型作図を手作業で行っているL2顧客に対し、APIによる一括自動レイアウト出力とBOM連動によるミス削減を提案。"},
                            "FC06": {"dept": "工場設計", "phase": "クラウド協調設計", "title": "FC06 (クラウド協調設計): サプライヤ間モデル共有と変更追跡", "products": "Autodesk Construction Cloud (ACC) Docs / Collaboration", "value_pitch": "安全な共通データ環境(CDE)による、複数サプライヤ設備3Dモデルのリアルタイム共有と、設計変更のバージョン履歴管理。", "sales_hint": "メールやファイル転送で3Dモデルをやり取りしている分断されたL2-L3顧客に、クラウドBIMデータ流通による情報一元化を提案。"},
                            "FC07": {"dept": "工場設計", "phase": "意思決定プロセス", "title": "FC07 (意思決定プロセス): VR内覧・役員合意形成の迅速化", "products": "FlexSim VR, VRED Pro", "value_pitch": "実寸VR空間における事前検証と、美しくリアルな3Dビジュアライゼーションによる関係者・経営層の合意形成スピードの劇的向上。", "sales_hint": "稟議や承認プロセスに何週間もかかっている企業に対し、VRを用いた一撃での意思決定スピード向上をオファー。"},
                            "FC08": {"dept": "工場設計", "phase": "バリエーション設計", "title": "FC08 (バリエーション設計): パラメータ駆動型自動設計", "products": "Autodesk Inventor, iLogic", "value_pitch": "iLogicを用いた、設計ルールの定義による設備の自動変形・コンフィギュレーションと、それに伴う図面・帳票の自動更新機能。", "sales_hint": "製品の仕様変更や受注ごとに一から図面を描き直しているL2-L3の設備メーカーに対し、パラメータ駆動の完全自動設計を提案。"}
                        },
                        "建築設計・施工 BIMアセスメント (AEC - AE)": {
                            "AE01": {"dept": "建築設計", "phase": "初期ボリューム・日影解析", "title": "AE01 (初期ボリューム・日影解析): 敷地解析と初期ボリューム検討", "products": "Autodesk Forma", "value_pitch": "初期段階での迅速な日影・気流・騒音シミュレーション。設計初期フェーズの意思決定をデータに基づき支援します。", "sales_hint": "敷地検討を手作業やExcelで行っている初期段階の建築事務所に対し、Formaによる即時クラウドシミュレーションを提案。"},
                            "AE02": {"dept": "建築設計", "phase": "BIM詳細設計", "title": "AE02 (BIM詳細設計): メタデータを持つ3D BIM設計への移行", "products": "Autodesk Revit", "value_pitch": "意匠、構造、MEP（設備）の全情報を統合した3D BIMによる設計。図面相互の一貫性を常に保ち、転記ミスを完全排除します。", "sales_hint": "2D設計からBIMへの移行期にあるL2顧客に対し、Revit導入による図面の完全不整合解消とBIMモデルの価値をアピール。"},
                            "AE03": {"dept": "建築設計", "phase": "統合コーディネーション", "title": "AE03 (統合コーディネーション): 自動衝突検出と施工性検証", "products": "Autodesk Navisworks Manage, BIM Collaborate", "value_pitch": "複数分野の3Dモデルを統合し、自動衝突検出（干渉チェック）を実施。着工前に現場手戻りの要因となる設計不整合をクリアします。", "sales_hint": "現場で設備と構造の干渉が見つかり予算超過しているL2-L3のゼネコン・サブコンに対し、Navisworksによる事前クリアを提案。"},
                            "AE04": {"dept": "建築設計", "phase": "共通データ環境", "title": "AE04 (共通データ環境): ISO 19650準拠のクラウドコラボレーション", "products": "Autodesk Docs / BIM Collaborate Pro", "value_pitch": "共通データ環境(CDE)によるプロジェクト情報の一元管理。異なる会社間でも安全に最新のBIMモデルを共有・共同設計します。", "sales_hint": "関係者間のデータ共有がメールやファイルストレージで分断されているL2-L3顧客に、Docsによる一元管理と共同設計を提案。"},
                            "AE05": {"dept": "建築設計", "phase": "施工図・数量算出", "title": "AE05 (施工図・数量算出): 3D/2D統合数量算出・積算", "products": "Autodesk Takeoff", "value_pitch": "BIMモデルからの自動数量算出と2D図面計測の統合。積算作業を高速化・高精度化し、見積の信頼性を担保します。", "sales_hint": "積算・見積もりを手作業やPDF計測で行っているL1-L2顧客に対し、Takeoffによる3D自動拾い出しと効率化を訴求。"},
                            "AE06": {"dept": "建築設計", "phase": "現場管理・デジタル施工", "title": "AE06 (現場管理・デジタル施工): モバイルでの図面・指摘事項管理", "products": "Autodesk Build", "value_pitch": "現場とオフィスをクラウドで接続。タブレット等による最新図面の閲覧、指摘事項（品質・安全）のデジタル起票・追跡管理。", "sales_hint": "紙の図面を現場に持ち歩き、事務所に戻ってPCで写真整理を行っている施工現場向けに、Buildによる現場施工管理を提案。"},
                            "AE07": {"dept": "建築設計", "phase": "工程シミュレーション", "title": "AE07 (工程シミュレーション): BIMモデル連動4D工程表", "products": "Autodesk Navisworks (TimeLiner)", "value_pitch": "BIMオブジェクトと工程スケジュールをリンクさせ、4D施工シミュレーションを実行。工期遅延や現場配置リスクを可視化します。", "sales_hint": "複雑な大型プロジェクトで工期遅延や資材置き場競合に悩むL3顧客に対し、4Dシミュレーションによる現場干渉防止を提案。"},
                            "AE08": {"dept": "建築設計", "phase": "デジタルツイン移行", "title": "AE08 (デジタルツイン移行): 竣工BIMからデジタルツインFMへの接続", "products": "Autodesk Tandem", "value_pitch": "竣工したアセットのインテリジェントモデル（デジタルツイン）化。FMデータベースへアセットデータをシームレスに引渡します。", "sales_hint": "竣工引き渡し後の建物維持管理フェーズでExcelや紙ファイルに苦しむL3-L4オーナー企業に、TandemでのFMアセット管理を提案。"}
                        },
                        "インフラ・土木設計 CDEアセスメント (Civil - CI)": {
                            "CI01": {"dept": "土木設計", "phase": "現況データと初期計画", "title": "CI01 (現況データと初期計画): 現況地形と道路設計の3D比較", "products": "Autodesk InfraWorks", "value_pitch": "GISやドローン点群を含む大規模な現況3D地形モデルの迅速な構築。初期計画の代替案検討と景観シミュレーションの高速化を実現します。", "sales_hint": "国土地理院マップや平面図から初期景観イメージを個別に作っているL1-L2設計事務所に、InfraWorksによる秒速3Dモデル化を提案。"},
                            "CI02": {"dept": "土木設計", "phase": "土木3D設計", "title": "CI02 (土木3D設計): CIM道路線形・パラメトリック設計", "products": "Autodesk Civil 3D", "value_pitch": "3D線形設計およびサーフェスベースの法面パラメトリック設計。線形の変更に合わせてすべての土量や法面展開が自動追従・更新されます。", "sales_hint": "設計変更に伴う断面図の描き直しや土量計算のやり直しを手作業で行っているL2顧客に対し、Civil 3Dの自動連動設計を提案。"},
                            "CI03": {"dept": "土木設計", "phase": "土木構造物との統合", "title": "CI03 (土木構造物との統合): Revit構造物（橋梁等）とCivil 3D道路線形の動的同期", "products": "Autodesk Civil 3D, Autodesk Revit", "value_pitch": "道路設計と構造物設計の緊密な連携。Civil 3Dの最新道路線形データをRevitの橋梁などの構造設計モデルと動的同期・干渉検出します。", "sales_hint": "構造設計と道路設計がバラバラで座標ずれや干渉に悩むL2-L3の総合建設コンサルに対し、Civil 3D-Revitの動的座標連携を提案。"},
                            "CI04": {"dept": "土木設計", "phase": "土量計算と自動化", "title": "CI04 (土量計算と自動化): 土量計算の高速化・切盛バランス自動計算", "products": "Civil 3D (Grading Optimization)", "value_pitch": "サーフェス比較を用いた高精度土量計算。AI/アルゴリズムによる法面や敷地計画の土量切盛バランスの自動最適化設計。", "sales_hint": "大規模造成プロジェクトで土砂の搬出入コスト削減や最適な法面計画設計に悩むL2-L3顧客に、自動最適化ツールを提案。"},
                            "CI05": {"dept": "土木設計", "phase": "CIMクラウド協調", "title": "CI05 (CIMクラウド協調): Civil 3Dチーム協調クラウド設計", "products": "Autodesk Collaboration for Civil 3D, ACC Docs", "value_pitch": "共通データ環境(CDE)によるCivil 3Dデータショートカットのクラウド共有。遠隔地のサブコンや別拠点と同期設計を実施します。", "sales_hint": "巨大な土木データをローカルサーバーやHDD移動でやり取りしているL2-L3企業に、クラウド上での線形データ参照同期設計を提案。"},
                            "CI06": {"dept": "土木設計", "phase": "周辺住民・発注者説明", "title": "CI06 (周辺住民・発注者説明): 住民合意形成用の3Dビジュアルパッケージ", "products": "Autodesk InfraWorks", "value_pitch": "リアルな3D地形・構造物アニメーションを用いた住民説明会・発注者説明のスピード化。景観変化や交通影響をビジュアルで即座に伝達。", "sales_hint": "合意形成プロセスに時間がかかり着工が遅れがちなL2-L3のコンサルや自治体担当者に対し、3Dビジュアル合意形成を提案。"},
                            "CI07": {"dept": "土木設計", "phase": "i-Constructionと点群", "title": "CI07 (i-Constructionと点群): ドローン点群からの出来形・土量検査", "products": "Autodesk ReCap Pro, Civil 3D", "value_pitch": "3Dレーザースキャン・ドローン点群データの高速処理と、Civil 3D地形サーフェスとの重ね合わせによるi-Construction出来形管理の自動化。", "sales_hint": "ICT土工の導入期にあり、点群データのハンドリングやCIM図面との重ね合わせに苦労している現場L3顧客にReCap Proを提案。"},
                            "CI08": {"dept": "土木設計", "phase": "納品とデータ引渡", "title": "CI08 (納品とデータ引渡): CIM電子納品とアセットデータの連携", "products": "Civil 3D, Autodesk Tandem", "value_pitch": "3DデータによるCIM電子納品への対応、および設計・施工時のBIM/CIMメタデータを維持管理データベース（FM）へシームレスに引き渡します。", "sales_hint": "電子納品データ作成が手作業のファイリングで大変な企業や、アセット管理への3D連携を求める発注者L3-L4へ提案。"}
                        },
                        "製品設計・製造プロセスアセスメント (MFG - MF)": {
                            "MF01": {"dept": "製品設計", "phase": "3D機械設計・BOM連携", "title": "MF01 (3D機械設計・BOM連携): Inventor詳細設計とBOM完全連動", "products": "Autodesk Inventor, Vault", "value_pitch": "3D CADモデルのパーツ構成と部品表(BOM)の完全同期。設計変更に伴う手入力でのBOM転記ミスや不整合を完全に防止します。", "sales_hint": "3D CADを使いつつBOMは手入力でExcel管理しているL2レベルの製造業に対し、設計-BOM自動連動プログラムを提案。"},
                            "MF02": {"dept": "製品設計", "phase": "設計シミュレーション", "title": "MF02 (設計シミュレーション): 設計段階での強度・熱応力FEA解析", "products": "Inventor Nastran / Simulation", "value_pitch": "CAD統合型のFEA・有限要素法解析。設計変更の都度、同じCAD環境で動的・静的シミュレーションを実行し、試作回数を激減させます。", "sales_hint": "試作検証と再設計を何度も繰り返し開発期間が長期化しているL2顧客に対し、設計エンジニアが回す事前FEA解析を提案。"},
                            "MF03": {"dept": "製品設計", "phase": "製品データ管理(PDM)", "title": "MF03 (製品データ管理(PDM)): Vaultによるリビジョン・承認自動統制", "products": "Autodesk Vault", "value_pitch": "リビジョンの厳密な世代管理、承認ワークフローのシステム統制、および重複設計（過去アセンブリの使い回し）の防止を実現します。", "sales_hint": "サーバー内のどれが最新の図面か分からなくなり、古い図面で製造をかけてしまった苦い経験のあるL2顧客にVaultを提案。"},
                            "MF04": {"dept": "製品設計", "phase": "クラウドレビューと協調", "title": "MF04 (クラウドレビューと協調): Fusionクラウドによる取引先レビュー共有", "products": "Autodesk Fusion (Cloud)", "value_pitch": "取引先や製造部門とのセキュアな3D設計クラウドビュー。ブラウザ上でのマークアップやチャット形式でのリアルタイム設計変更レビューの実現。", "sales_hint": "取引先に図面を渡す際にPDF変換してメール送信しており、3Dの整合性確認に時間がかかるL2-L3企業にFusionの強みをアピール。"},
                            "MF05": {"dept": "製品設計", "phase": "ジェネレーティブデザイン", "title": "MF05 (ジェネレーティブデザイン): AIによる軽量最適形状の自動生成", "products": "Autodesk Fusion (Generative Design)", "value_pitch": "設計条件（力・固定箇所・製法等）からAIが複数の最適な軽量化モデル案を自動生成。人間が思いつかない極限の材料・コスト削減を達成します。", "sales_hint": "製品の劇的な軽量化や材料費削減の壁に直面しているL3以上の高度製造業に対し、ジェネレーティブデザインの適用会を提案。"},
                            "MF06": {"dept": "製品設計", "phase": "CAD/CAM統合と製造", "title": "MF06 (CAD/CAM統合と製造): CAD/CAM統合によるNCコード作成と自動再計算", "products": "Autodesk Fusion (CAM)", "value_pitch": "同一CAD環境でのCAMパス作成。設計変更が発生した瞬間、加工のツールパスも自動的に再計算・更新され、再設計の手間をゼロにします。", "sales_hint": "CADとCAMが別ソフトで、設計変更のたびにCAMオペレーターが再プログラムしている非効率な工場L2-L3にFusion CAMを提案。"},
                            "MF07": {"dept": "製品設計", "phase": "iLogic・自動コンフィギュレーション", "title": "MF07 (iLogic・自動コンフィギュレーション): パラメータ自動構成ルール作成", "products": "Autodesk Inventor (iLogic)", "value_pitch": "アセンブリ・図面のパラメータ自動構成。仕様入力に応じてパーツが自動変形し、詳細設計図と帳票が一瞬で自動出力されます。", "sales_hint": "標準品のバリエーション変更（幅・高さ変更など）の受注対応で、毎回手動で図面を描き直しているL2-L3メーカーに最適の提案。"},
                            "MF08": {"dept": "製品設計", "phase": "ECAD/MCAD協調設計", "title": "MF08 (ECAD/MCAD協調設計): 基板と筐体のリアルタイムオンライン3D干渉検証", "products": "Autodesk Fusion (ECAD/MCAD)", "value_pitch": "電子CAD基板設計とメカニカル筐体設計েরリアルタイムな3Dデータ同期。基板の干渉などを試作前にオンライン画面で検証・クリアします。", "sales_hint": "電子基板と筐体の干渉による設計やり直しが多い、または異なるツールでファイルやり取りしている電気・機械L2-L3企業へ提案。"}
                        }
                    }
                    
                    mapping_keys = list(all_mappings.keys())
                    selected_map_key = mapping_keys[0]
                    if selected_survey_type == "工場設計・プロダクトクラウド":
                        selected_map_key = "工場設計・プロダクトクラウドアセスメント (Factory Cloud - FC)"
                    elif selected_survey_type == "建築設計・施工 BIM":
                        selected_map_key = "建築設計・施工 BIMアセスメント (AEC - AE)"
                    elif selected_survey_type == "インフラ・土木設計 CIM":
                        selected_map_key = "インフラ・土木設計 CDEアセスメント (Civil - CI)"
                    elif selected_survey_type == "製品設計・開発":
                        selected_map_key = "製品設計・製造プロセスアセスメント (MFG - MF)"
                        
                    selected_mapping_set = st.selectbox(
                        "表示する提案マッピング分野の切り替え",
                        options=mapping_keys,
                        index=mapping_keys.index(selected_map_key),
                        key="sales_console_mapping_set"
                    )
                    
                    active_mapping = all_mappings[selected_mapping_set]
                    for qid, info in active_mapping.items():
                        st.markdown(f"**{qid}  {info['dept']} - {info['phase']}**")
                        st.markdown(f"* {info['title']}")
                        st.markdown(f"**提案対象製品:** `{info['products']}`")
                        st.markdown(f"**価値訴求:** {info['value_pitch']}")
                        st.markdown(f"**セールスヒント:** {info['sales_hint']}")
                        st.markdown("---")

        else:
            if dash_pw != "":
                st.error("パスワードが正しくありません。")

###  Tab 3: 営業管理 ###
if tab_admin:
    with tab_admin:
        st.header("営業担当用 カスタムアンケート発行管理")
        admin_pw = st.text_input("管理用パスワード", type="password", key="admin_pw_input")
        
        correct_admin_pw = get_secret_password(st.secrets, "sales_admin")
        if correct_admin_pw is None:
            st.error("管理者認証が設定されていません。Secrets の sales_admin.password を設定してください。")
        elif admin_pw == correct_admin_pw:
            st.success("認証されました。")
            
            st.subheader("1. アンケート基本設定")
            col_ad1, col_ad2 = st.columns(2)
            with col_ad1:
                new_survey_id = st.text_input("アンケートID (英数字・ハイフンのみ) *", placeholder="例: toyota-2026")
                new_client_name = st.text_input("顧客企業名 *", placeholder="例: トヨタ自動車株式会社")
            with col_ad2:
                new_creator = st.text_input("作成者名 *", placeholder="例: 佐藤 営業担当")
                
            model_template = st.selectbox(
                "設問モデルテンプレート", 
                [
                    "IFM 設備管理成熟度アセスメント (デフォルト)", 
                    "工場設計・プロダクトクラウド適性診断 (Forma, FlexSim 誘導用)",
                    "建築設計・施工 BIM適性診断 (Forma, Revit, ACC 誘導用)",
                    "土木・インフラ CIM適性診断 (InfraWorks, Civil 3D 誘導用)",
                    "製品設計・開発 デジタル適性診断 (Inventor, Fusion 誘導用)"
                ],
                key="model_template_select"
            )
                
            if new_survey_id.strip():
                if not re.match(r"^[a-zA-Z0-9\-_]+$", new_survey_id.strip()):
                    st.error("アンケートIDは英数字、ハイフン(-), アンダースコア(_)のみ使用可能です。")
                else:
                    if st.button("既存のカスタム設問を読み込む (IDが存在する場合)"):
                        existing = get_custom_survey(new_survey_id.strip())
                        if existing:
                            st.session_state[f"loaded_survey_{new_survey_id}"] = existing
                            st.success(f"ID: `{new_survey_id}` の既存設定を読み込みました！")
            
            st.subheader("2. 設問テキストのカスタマイズ")
            all_qs = load_all_questions_json()
            
            app_suffix = ""
            if "工場設計" in model_template:
                default_qs = all_qs.get("factory_cloud_questions", [])
                app_suffix = "&app=factory"
            elif "建築設計" in model_template:
                default_qs = all_qs.get("aec_questions", [])
                app_suffix = "&app=aec"
            elif "土木・インフラ" in model_template:
                default_qs = all_qs.get("civil_questions", [])
                app_suffix = "&app=civil"
            elif "製品設計" in model_template:
                default_qs = all_qs.get("mfg_questions", [])
                app_suffix = "&app=mfg"
            else:
                default_qs = all_qs.get("questions", [])
                app_suffix = ""
                
            custom_questions_data = []
            loaded_survey = st.session_state.get(f"loaded_survey_{new_survey_id}")
            existing_qs_map = {}
            if loaded_survey:
                existing_qs_map = {q["question_id"]: q["question_text"] for q in loaded_survey.get("questions", [])}
                
            for q in default_qs:
                qid = q["question_id"]
                current_value = existing_qs_map.get(qid, q["question_text"])
                
                with st.expander(f"【{q['department']}】 {q['phase']} ({qid})"):
                    custom_text = st.text_area(f"設問文 ({qid})", value=current_value, key=f"edit_text_{qid}", height=80)
                    
                custom_questions_data.append({
                    "department": q['department'],
                    "question_id": qid,
                    "phase": q['phase'],
                    "question_text": custom_text.strip() if custom_text.strip() else q["question_text"],
                    "levels": q["levels"]
                })
                
            st.markdown("---")
            if st.button("アンケートを発行・保存する", type="primary", use_container_width=True):
                if not new_survey_id.strip() or not new_client_name.strip() or not new_creator.strip():
                    st.error("必須入力項目をすべて埋めてください。")
                else:
                    sid = new_survey_id.strip()
                    success = save_custom_survey(
                        survey_id=sid,
                        client_name=new_client_name.strip(),
                        creator=new_creator.strip(),
                        questions_list=custom_questions_data
                    )
                    if success:
                        st.success(f"カスタムアンケート `{sid}` が保存・発行されました！")
                        prod_url = f"https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?survey_id={sid}&brand=autodesk{app_suffix}"
                        local_url = f"http://localhost:8501/?survey_id={sid}&brand=autodesk{app_suffix}"
                        
                        st.info("顧客配信用リンク (本番環境):")
                        st.code(prod_url, language=None)
                        
                        # Generate locally so customer URLs are never sent to a third-party QR service.
                        try:
                            import qrcode

                            qr_buffer = BytesIO()
                            qrcode.make(prod_url).save(qr_buffer, format="PNG")
                            st.image(qr_buffer.getvalue(), caption="スマホ用顧客配信用QRコード（本番環境）", width=180)
                        except ImportError:
                            st.caption("QRコード生成機能は現在利用できません。上記URLをコピーして共有してください。")
                        
                        st.info("テスト用リンク (ローカル環境):")
                        st.code(local_url, language=None)
            
            # 最新の回答データを取得してレコメンドを表示するセクション
            st.markdown("---")
            st.subheader("4. 最新アセスメント回答通知 ＆ AIセールスレコメンド")
            
            resp_df_all = load_responses_from_firestore()
            if resp_df_all.empty:
                st.info("まだ回答データが存在しません。")
            else:
                latest_ts = resp_df_all['timestamp'].max()
                latest_rows = resp_df_all[resp_df_all['timestamp'] == latest_ts]
                
                if not latest_rows.empty:
                    first_row = latest_rows.iloc[0]
                    res_name = first_row.get("respondent", "匿名")
                    res_team = first_row.get("team", "部署未設定")
                    res_email = first_row.get("email", "なし")
                    res_sid = first_row.get("survey_id", "default")
                    
                    formatted_ts = str(latest_ts).replace("T", " ")[:19]
                    
                    qids = latest_rows['question_id'].tolist()
                    survey_type_lbl = "設備管理成熟度アセスメント (IFM)"
                    if any(str(q).startswith("FC") for q in qids):
                        survey_type_lbl = "工場設計・プロダクトクラウド適性診断"
                    elif any(str(q).startswith("AE") for q in qids):
                        survey_type_lbl = "建築設計・施工 BIM適性診断"
                    elif any(str(q).startswith("CI") for q in qids):
                        survey_type_lbl = "土木・インフラ CIM適性診断"
                    elif any(str(q).startswith("MF") for q in qids):
                        survey_type_lbl = "製品設計・開発 デジタル適性診断"
                        
                    st.markdown(
                        f"""
                        <div style='background-color:#121212; padding:15px; border-left:4px solid #FFFF00; border-radius:4px; margin-bottom:15px;'>
                            <span style='background-color:#FFFF00; color:#000000; font-size:0.75rem; font-weight:700; padding:2px 6px; border-radius:2px; margin-right:8px;'>REALTIME ALERT</span>
                            <b>{res_name} 様 ({res_team}) がアセスメントを完了しました！</b><br>
                            <span style='font-size:0.85rem; color:#8C9BA5;'>回答時刻: {formatted_ts}  ·  対象モデル: {survey_type_lbl}  ·  アンケートID: {res_sid}  ·  連絡先: {res_email}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    gaps = []
                    for _, row in latest_rows.iterrows():
                        as_is_val = row.get("as_is")
                        to_be_val = row.get("to_be")
                        if pd.notna(as_is_val) and pd.notna(to_be_val):
                            gap_val = int(to_be_val) - int(as_is_val)
                            gaps.append({
                                "qid": row.get("question_id"),
                                "phase": row.get("phase"),
                                "gap": gap_val,
                                "to_be": int(to_be_val)
                            })
                            
                    gaps_sorted = sorted(gaps, key=lambda x: (x["gap"], x["to_be"]), reverse=True)
                    
                    if gaps_sorted:
                        top_gap = gaps_sorted[0]
                        recommendations_map = {
                            "FC01": "Formaによる敷地風向・日影解析デモをオファーし、『初期計画段階でのAI迅速シミュレーションによる手戻り削減』をフックにアプローチしてください。",
                            "FC02": "FlexSimによる工程シミュレーションデモを提案。『時間軸を考慮した設備能力と搬送ルートの最適化』をアピールして、工場部門への商談を開始してください。",
                            "FC03": "Factory Design Utilities (FDU) を紹介。『AutoCADとInventorの2D/3D双方向同期による干渉チェック』が最も響くアプローチです。",
                            "FC04": "AIモデリング（Navastoなど）やジェネレーティブデザインの紹介スライドを持参し、設計プロセスの自律化を切り口に会話を展開してください。",
                            "FC05": "AutoCAD専用ツールセットやAPI/LISPによる作図・BOM出力の『定型業務自動化』をフックにし、開発期間の圧縮を提案してください。",
                            "FC06": "Autodesk Construction Cloud (ACC) CDEによる『サプライヤとの安全なリアルタイム3Dモデル共有・整合性維持』をテーマに会話を構築してください。",
                            "FC07": "FlexSim VRを用いた『バーチャル工場内覧会・VR役員合意形成』のデモを提案し、意思決定の迅速化を支援してください。",
                            "FC08": "Inventor iLogicを活用した『パラメータ駆動型設計の自動化・仕様変更に伴う図面自動更新』の自動化導入ワークショップを提案してください。",
                            "AE01": "Autodesk Formaを用いた環境シミュレーションを提案。初期段階で騒音や日影の風向問題を秒速で解決する事例が刺さります。",
                            "AE02": "Revitの3D BIM設計への移行支援プログラムをオファー。2Dから3Dへの移行に伴う図面の一貫性確保が最大のセールスポイントです。",
                            "AE03": "Navisworksによる複数領域データの重ね合わせ・自動干渉検出のデモを提案し、現場施工段階の手戻り削減効果を訴求してください。",
                            "AE04": "ACC Docs/Design CollaborateによるISO 19650準拠のクラウドCDEコラボレーションの価値、データ紛失防止を提案してください。",
                            "AE05": "ACC Takeoffを用いた3D/2D統合数量算出による見積の高速化・高精度化のソリューション資料をオファーしてください。",
                            "AE06": "ACC Buildを用いた現場デジタル施工管理（モバイルでの図面閲覧や指摘管理）を提案し、現場監督の直行直帰促進をアピールしてください。",
                            "AE07": "Navisworks 4D工程シミュレーションにより、工期遅延リスクを3Dビジュアルで事前に洗い出す検証デモをオファーしてください。",
                            "AE08": "Autodesk Tandemを用いたデジタルツイン FMデータ構築プログラムを提案。FM化への道筋を示してください。",
                            "CI01": "InfraWorksによる広域CIM地形モデル構築のデモを提案。現況地形と道路設計の3D比較を訴求してください。",
                            "CI02": "Civil 3DによるCIM道路線形設計・パラメトリック法面展開の自動更新デモを提案し、設計変更への耐性をアピールしてください。",
                            "CI03": "Revit構造物（橋梁等）とCivil 3D道路線形の動的同期による干渉チェック＆座標自動補正デモが極めて有効です。",
                            "CI04": "Civil 3Dサーフェス比較を用いた高精度土量計算と、切盛土バランスの自動最適化ツールをフックに提案してください。",
                            "CI05": "ACC Collaboration for Civil 3Dによるチーム間共有手法をテーマにオファーしてください。",
                            "CI06": "InfraWorksを用いた発注者や住民向け説明用のCIM 3Dビジュアル合意形成パッケージをオファーしてください。",
                            "CI07": "ReCap Proによるドローン点群からの地形面抽出・Civil 3D地形サーフェス化によるi-Construction出来形管理を提案してください。",
                            "CI08": "Civil 3DとTandemを組み合わせたCIM電子納品対応・維持管理データベース移行自動化ワークフローを提案してください。",
                            "MF01": "Inventor詳細設計とBOM（部品構成表）の完全連動デモを提案し、BOMの手入力ミスや不整合削減を訴求してください。",
                            "MF02": "Inventor Nastranによる設計段階での強度・熱応力FEA解析デモを提案。試作手戻りの劇的削減をアピールしてください。",
                            "MF03": "VaultによるPDMデータ管理（リビジョン管理・承認フロー自動統制・重複設計の防止）のデモ・体験会をオファーしてください。",
                            "MF04": "Autodesk Fusionクラウド共有機能による、取引先や製造現場との即時3D設計レビュー、変更箇所の可視化を提案してください。",
                            "MF05": "Fusion Generative Design（AIによる軽量最適形状の自動生成）を活用した製品軽量化の事例展示・検証会を提案してください。",
                            "MF06": "Fusion CAMを用いたCAD/CAM完全統合による加工NCデータ作成と、設計変更時のパス自動再計算デモを提案してください。",
                            "MF07": "Inventor iLogicを用いたアセンブリ・図面のパラメータ自動構成ルール作成ワークショップをオファーしてください。",
                            "MF08": "Fusion ECADによる基板設計とMCAD（筐体設計）のリアルタイムオンライン3D干渉検証機能をフックにアピールしてください。"
                        }
                        
                        recommend_text = recommendations_map.get(
                            top_gap["qid"],
                            "お客様の最大の課題箇所に対し、最適なAutodesk製品のデモ、または製品統合パッケージ（AEC Collection / PDMC）のご紹介ワークショップをオファーしてください。"
                        )
                        
                        st.markdown("<h5 style='color:#FFFFFF; font-weight:700; margin-top:15px; margin-bottom:5px;'> AI推奨セールストーク ＆ 提案シナリオ</h5>", unsafe_allow_html=True)
                        st.info(f" **アプローチの切り口 (最大課題: {top_gap['qid']} [{top_gap['phase']}] - Gap: {top_gap['gap']})**\n\n{recommend_text}")
                    else:
                        st.write("回答データに有効なGapが存在しません。全体の成熟度は非常に高い状況です。")
        else:
            if admin_pw != "":
                st.error("パスワードが正しくありません。")
