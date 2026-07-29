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

from ifm_guardrails import validate_questions

# Import Firestore helpers
from db_helper import (
    get_custom_survey,
    save_response_to_firestore
)

# Paths
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path(".").resolve()
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"
IMAGES_DIR = SCRIPT_DIR / "data" / "images"

# Autodesk Brand Official Color & Layout Guidelines
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: Arial, system-ui, -apple-system, "Segoe UI", sans-serif !important;
        font-size: 17px !important;
    }
    
    /* Responsive Text Sizes for Mobile & High Res */
    @media (max-width: 768px) {
        html, body, [data-testid="stAppViewContainer"] {
            font-size: 18px !important;
        }
        h3 {
            font-size: 1.45rem !important;
        }
        h4 {
            font-size: 1.25rem !important;
        }
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    /* Slider label size enhancement */
    .stSlider label p {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
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
        font-size: 1.05rem !important;
    }

    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="select"] input,
    .stTextInput input,
    .stTextArea textarea {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FFFFFF !important;
        font-size: 1.05rem !important;
    }
    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="textarea"] textarea::placeholder,
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #8C9BA5 !important;
        -webkit-text-fill-color: #8C9BA5 !important;
        opacity: 1 !important;
    }
    
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #FFFF00 !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
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
        font-size: 1.05rem !important;
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
    
    /* Toggle Switch Styling */
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

# Load Factory Cloud Questions
def get_factory_questions():
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
            if validate_questions(questions):
                st.error("このアンケートの設問定義が壊れているため、回答を開始できません。")
                st.stop()
            return pd.DataFrame(questions), survey_id, custom_survey.get("client_name")
        st.error("指定されたアンケートが見つかりません。URLを確認するか、発行元へお問い合わせください。")
        st.stop()
            
    if DATA_JSON.exists():
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data.get("factory_cloud_questions", [])), "default", None
    return pd.DataFrame(), "default", None

q_df, active_survey_id, client_name = get_factory_questions()

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

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email.strip()) is not None

if q_df.empty:
    st.stop()

# Persistent answers store in session state to prevent widget key purging
if "survey_answers" not in st.session_state:
    st.session_state.survey_answers = {}

# Image Mapping for Factory Cloud
IMAGE_MAPPING = {
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

# Brand Header Layout
header_html = '<div style="display:flex;align-items:end;justify-content:space-between;flex-wrap:wrap;margin:12px 0 16px;gap:16px;"><div><div style="font-size:.85rem;color:#FFFF00;letter-spacing:.12em;text-transform:uppercase;font-weight:700;">IFM Maturity Assessment</div><div style="font-size:2.0rem;font-weight:700;color:#FFFFFF;letter-spacing:-.03em;">工場設計・プロダクトクラウド適性診断</div></div><div style="font-size:.85rem;color:#D5D5CB;">for Autodesk Design &amp; Make workflows</div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

tabs = st.tabs(["アセスメント回答"])
with tabs[0]:
    col_left_form, col_right_chart = st.columns([11, 9])
    
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    num_questions = len(q_df)
    
    if "is_submitted" not in st.session_state:
        st.session_state.is_submitted = False
        
    with col_left_form:
        if st.session_state.is_submitted:
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF; font-size:1.5rem;'>アセスメント回答送信完了</h3>", unsafe_allow_html=True)
            st.success("アセスメントの回答が安全に記録されました。ご協力ありがとうございました。")
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
            if st.button("アセスメントを再回答する", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key.startswith(("asis_", "tobe_", "skip_", "res_")) or key in {"agree_privacy", "agree_privacy_step0", "current_step", "is_submitted", "survey_answers"}:
                        st.session_state.pop(key, None)
                st.rerun()

        elif st.session_state.current_step == 0:
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF; font-size:1.45rem;'>回答者プロファイル ＆ 同意確認</h3>", unsafe_allow_html=True)
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
            
            specific_team = st.text_input("部署名・チーム名 (任意)", placeholder="例: 生産技術部 設計課", value=st.session_state.get("res_team", ""))
            st.session_state["res_team"] = specific_team
            
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            agree_privacy = st.checkbox("個人情報の取り扱い説明事項を確認し、同意します。 *", value=st.session_state.get("agree_privacy", False), key="agree_privacy_step0")
            st.session_state["agree_privacy"] = agree_privacy
            
            if not agree_privacy:
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                st.markdown("<b style='font-size:0.95rem; color:#D5D5CB;'>個人情報の利用目的と保存先</b>", unsafe_allow_html=True)
                privacy_policy_text = "入力された氏名、メールアドレス、所属情報および回答内容は、成熟度分析、結果の連絡、提案内容の改善のために利用し、運用管理者が管理するFirestoreおよびGoogle Sheetsへ保存します。アクセスは担当者とシステム管理者に限定します。保持期間、削除依頼、第三者提供の有無など正式な取扱条件は、発行元が提示する個人情報取扱方針を確認してください。正式な方針が提示されていない場合は回答を開始せず、発行元へお問い合わせください。"
                st.markdown(
                    f'<div style="background-color:#121212; border:1px solid #333333; border-radius:8px; padding:15px; font-size:0.95rem; color:#8C9BA5; line-height:1.6; white-space:pre-wrap; transition: all 0.2s ease;">{privacy_policy_text}</div>',
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
                
                # Format question text with clean line breaks
                raw_qtext = str(row['question_text'])
                formatted_qtext = raw_qtext.replace('\n', '<br>')
                
                st.markdown(
                    f"<div style='background-color:#121212; padding:20px; border-left:5px solid #FFFF00; margin-top:15px; border-radius:4px; border-top:1px solid #333333; border-right:1px solid #333333; border-bottom:1px solid #333333;'>"
                    f"<div style='font-size:0.92rem; color:#FFFF00; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>"
                    f"{row['department']} 領域  ·  設問 {step_idx} / {num_questions}</div>"
                    f"<h3 style='margin-top:2px; margin-bottom:10px; font-size:1.45rem; font-weight:700; color:#FFFFFF;'>{row['question_id']} ({row['phase']})</h3>"
                    f"<div style='font-size:1.08rem; line-height:1.65; color:#FFFFFF; white-space:pre-wrap;'>{formatted_qtext}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                # スキップトグル
                skip_key = f"skip_{qid}"
                if skip_key not in st.session_state:
                    st.session_state[skip_key] = False
                skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key, disabled=(step_idx < st.session_state.current_step))
                
                # スライダー値の取得
                asis_key = f"asis_{qid}"
                tobe_key = f"tobe_{qid}"
                
                if asis_key not in st.session_state:
                    st.session_state[asis_key] = 2.0
                if tobe_key not in st.session_state:
                    st.session_state[tobe_key] = 4.0
                
                # Update persistent answers store
                st.session_state.survey_answers[qid] = {
                    "asis": float(st.session_state[asis_key]),
                    "tobe": float(st.session_state[tobe_key]),
                    "skip": skip
                }
                
                if not skip:
                    as_is_val = float(st.session_state[asis_key])
                    to_be_val = float(st.session_state[tobe_key])
                    
                    levels_html = "<div style='display: flex; flex-direction: column; gap: 8px; margin-top: 14px; margin-bottom: 16px;'>"
                    for lvl in ["L1", "L2", "L3", "L4", "L5"]:
                        lvl_num = int(lvl[1])
                        is_asis = (as_is_val == lvl_num)
                        is_tobe = (to_be_val == lvl_num)
                        
                        border_color = "rgba(102, 102, 102, 0.25)" 
                        bg_color = "#121212"
                        badge_html = ""
                        
                        if is_asis and is_tobe:
                            border_color = "#FFFF00" 
                            bg_color = "rgba(255, 255, 0, 0.08)"
                            badge_html = "<span style='background-color:#FFFF00; color:#000000; font-size:0.8rem; font-weight:800; padding:2px 8px; border-radius:3px; margin-right:8px;'>As-Is & To-Be</span>"
                        elif is_asis:
                            border_color = "#1D91D0" 
                            bg_color = "rgba(29, 145, 208, 0.12)"
                            badge_html = "<span style='background-color:#1D91D0; color:#FFFFFF; font-size:0.8rem; font-weight:800; padding:2px 8px; border-radius:3px; margin-right:8px;'>As-Is</span>"
                        elif is_tobe:
                            border_color = "#2AD0A9" 
                            bg_color = "rgba(42, 208, 169, 0.08)"
                            badge_html = "<span style='background-color:#2AD0A9; color:#000000; font-size:0.8rem; font-weight:800; padding:2px 8px; border-radius:3px; margin-right:8px;'>To-Be</span>"
                            
                        lvl_text = str(row["levels"][lvl]).replace('\n', '<br>')
                        levels_html += f'<div style="border-left: 4px solid {border_color}; background-color: {bg_color}; padding: 10px 14px; border-top: 1px solid rgba(255,255,255,0.08); border-right: 1px solid rgba(255,255,255,0.08); border-bottom: 1px solid rgba(255,255,255,0.08); border-radius:4px;"><div style="display: flex; align-items: center; margin-bottom: 4px;">{badge_html}<b style="font-size: 0.95rem; color: #FFFF00; font-weight: 700;">Level {lvl_num}</b></div><div style="font-size: 1.02rem; color: #FFFFFF; line-height: 1.6; white-space: pre-wrap;">{lvl_text}</div></div>'
                    levels_html += "</div>"
                    st.markdown(levels_html, unsafe_allow_html=True)
                    
                    # カラー同期されたスライダーの描画
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown("<div class='asis-slider-container'>", unsafe_allow_html=True)
                        st.slider("現状の成熟度評価 (As-Is)", min_value=1.0, max_value=5.0, step=0.5, key=asis_key, disabled=(step_idx < st.session_state.current_step))
                        st.markdown("</div>", unsafe_allow_html=True)
                    with col_s2:
                        st.markdown("<div class='tobe-slider-container'>", unsafe_allow_html=True)
                        st.slider("将来の目標成熟度 (To-Be)", 1, 5, key=tobe_key, disabled=(step_idx < st.session_state.current_step))
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='padding:12px 0; color:#8C9BA5; font-size:1.0rem;'>※ この設問はスキップされています</div>", unsafe_allow_html=True)
                
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
        if st.session_state.is_submitted or st.session_state.current_step == 0:
            render_hero_image("FC01")
        else:
            current_active_qid = q_df.iloc[st.session_state.current_step - 1]['question_id']
            render_hero_image(current_active_qid)
            
        st.markdown("<h4 style='margin-bottom:8px; font-weight:700; font-size:1.25rem; color:#FFFFFF;'>ライブ成熟度プロファイル</h4>", unsafe_allow_html=True)
        
        plot_categories = []
        plot_asis = []
        plot_tobe = []
        
        for idx, r in q_df.iterrows():
            q_id = r['question_id']
            ans = st.session_state.survey_answers.get(q_id, {"asis": 2, "tobe": 4, "skip": False})
            
            # Question is active if step reached or form submitted
            is_step_reached = (idx + 1 <= st.session_state.current_step) or st.session_state.is_submitted
            is_skipped = ans.get("skip", False)
            
            if is_step_reached and not is_skipped:
                as_is = ans.get("asis", 2)
                to_be = ans.get("tobe", 4)
            else:
                as_is = 0
                to_be = 0
                
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
                fillcolor='rgba(29, 145, 208, 0.15)',
                line=dict(width=2.5),
                opacity=0.8
            ))
            fig.add_trace(go.Scatterpolar(
                r=plot_tobe + [plot_tobe[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='将来の目標 (To-Be)',
                line_color='#2AD0A9',
                fillcolor='rgba(42, 208, 169, 0.08)',
                line=dict(width=2.0, dash='dash'),
                opacity=0.7
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickvals=[1, 2, 3, 4, 5],
                        gridcolor='rgba(255, 255, 255, 0.2)',
                        linecolor='rgba(255, 255, 255, 0.3)',
                        tickfont=dict(color='#FFFFFF', size=11, family='Arial')
                    ),
                    angularaxis=dict(
                        gridcolor='rgba(255, 255, 255, 0.2)',
                        linecolor='rgba(255, 255, 255, 0.3)',
                        tickfont=dict(color='#FFFFFF', size=11.5, family='Arial')
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
                    font=dict(color='#FFFFFF', size=12)
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=60, r=60, t=20, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            answered_count = len(st.session_state.survey_answers) if st.session_state.is_submitted else max(0, min(num_questions, st.session_state.current_step))
            st.progress(answered_count / num_questions)
            st.markdown(f"<div style='text-align:right; font-size:0.88rem; color:#D5D5CB; margin-top:2px;'>回答進捗: {answered_count} / {num_questions} 問</div>", unsafe_allow_html=True)

    # 最終送信処理
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
                ans = st.session_state.survey_answers.get(q_id, {"asis": 2, "tobe": 4, "skip": False})
                is_skipped = ans.get("skip", False)
                as_is_val = "N/A" if is_skipped else ans.get("asis", 2)
                to_be_val = "N/A" if is_skipped else ans.get("tobe", 4)
                
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
