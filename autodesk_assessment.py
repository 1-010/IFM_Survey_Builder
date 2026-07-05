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
import tempfile
from fpdf import FPDF
import urllib.request

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

# Autodesk Brand Official Color & Layout Guidelines Integration
# Primary: Black (#000000), White (#FFFFFF), Hello Yellow (#FFFF00)
# Secondary: Warm Slate (#D5D5CB), Slate (#666666)
# Tertiary (Functional): Dawn (#F09D4F), Dusk (#F2520A), Twilight (#1D91D0), Morning (#2AD0A9)
# Radii Scale: Buttons/Tags = 4px, Inputs/Small Cards = 8px, Structural Containers/Images = 0px (Sharp)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* 1. Global Color Canvas (Autodesk Black & White) */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important; /* Pure Autodesk Black */
        color: #FFFFFF !important; /* Pure Autodesk White */
        font-family: 'Inter', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    /* 2. Structural Elements - Sharp Corners (0px) for precision */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 0px !important; /* Sharp corners per layout guidelines */
        border: none !important;
        border-left: 1px solid #666666 !important; /* Slate divider line */
        background-color: transparent !important;
        padding: 0px 24px !important;
        box-shadow: none !important;
    }
    
    /* Sharp corners for Images */
    .stImage img {
        border-radius: 0px !important; /* Sharp corners for structural images */
        border: 1px solid #666666 !important; /* Slate border */
    }
    
    /* 4. Inputs & Interactive controls - 8px radius */
    div[data-baseweb="input"], select, textarea {
        border-radius: 8px !important;
        border: 1px solid #666666 !important;
        background-color: #121212 !important;
        color: #FFFFFF !important;
    }
    
    /* 5. Button Stylings - Contrast & Hierarchy Fixes */
    /* Primary buttons (Yellow Background, Black Text) - strictly for final actions */
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #FFFF00 !important; /* Hello Yellow */
        color: #000000 !important; /* Autodesk Black text */
        border: none !important;
        border-radius: 4px !important; /* 4px for buttons */
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        letter-spacing: 0.05em !important;
        padding: 10px 24px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #E5E500 !important; /* Hover effect */
    }
    /* Force black text color for all child elements of primary button to fix Streamlit's white-text override */
    div.stButton > button[data-testid="stBaseButton-primary"] * {
        color: #000000 !important;
    }
    
    /* Secondary buttons (Transparent/Black Background, White Text, Slate Border) - for navigation */
    div.stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid #666666 !important; /* Slate border */
        border-radius: 4px !important;
        font-weight: 500 !important;
        font-size: 0.92rem !important;
        padding: 10px 24px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
        border-color: #FFFF00 !important; /* Hover outline highlight in Hello Yellow */
        color: #FFFF00 !important;
    }
    /* Force white text color for all child elements of secondary button */
    div.stButton > button[data-testid="stBaseButton-secondary"] * {
        color: #FFFFFF !important;
    }
    /* Force Hello Yellow text color for child elements of secondary button on hover */
    div.stButton > button[data-testid="stBaseButton-secondary"]:hover * {
        color: #FFFF00 !important;
    }
    
    /* Secondary/Navigation buttons when disabled */
    div.stButton > button[disabled] {
        background-color: #1A1A1A !important;
        color: #666666 !important;
        border-color: #333333 !important;
    }
    div.stButton > button[disabled] * {
        color: #666666 !important;
    }
    
    /* 6. Custom Slider & Toggle Accent - Hello Yellow (#FFFF00) */
    div[role="slider"] {
        background-color: #FFFF00 !important; /* Hello Yellow thumb */
    }
    .stSlider > div {
        color: #FFFF00 !important;
    }
    /* Toggle active track styling */
    div[data-testid="stCheckbox"] > label > div:first-child {
        background-color: #FFFF00 !important;
    }
    
    /* Clean Tab bars */
    button[data-baseweb="tab"] {
        color: #D5D5CB !important; /* Warm Slate */
        font-size: 0.95rem !important;
        border-bottom-width: 2px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFF00 !important; /* Hello Yellow active tab */
        border-bottom-color: #FFFF00 !important;
    }
    
    /* Clean Progress Bar */
    .stProgress > div > div > div {
        background-color: #FFFF00 !important; /* Hello Yellow progress */
    }
    
    /* Hide Streamlit Default UI Noise */
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    [class^="viewerBadge"] {display: none !important;}
    [class*="viewerBadge"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden; display: none !important;}
    
    /* Sticky Right Column Visuals */
    @media (min-width: 992px) {
        div[data-testid="stColumn"]:nth-child(2) {
            position: -webkit-sticky;
            position: sticky;
            top: 20px;
            z-index: 999;
        }
    }
    
    /* Custom Proposal Cards Styles */
    .proposal-card {
        background-color: #121212;
        border: 1px solid #333333;
        border-left: 4px solid #FFFF00 !important;
        border-radius: 4px;
        padding: 18px;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    .proposal-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #FFFF00;
        margin-bottom: 6px;
    }
    .proposal-desc {
        font-size: 0.88rem;
        color: #FFFFFF;
        line-height: 1.5;
        margin-bottom: 12px;
    }
    .proposal-link-btn {
        display: inline-block;
        background-color: #000000;
        color: #FFFF00 !important;
        border: 1px solid #FFFF00;
        border-radius: 4px;
        padding: 6px 14px;
        font-size: 0.82rem;
        font-weight: 600;
        text-decoration: none !important;
        letter-spacing: 0.05em;
        transition: all 0.15s ease;
    }
    .proposal-link-btn:hover {
        background-color: #FFFF00;
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# FPDF日本語フォント自動解決＆PDF出力エンジン
def generate_pdf_report_bytes(res_name, res_email, res_team, res_exp, answers_list, gaps_sorted, proposals_dict, survey_title):
    font_path = os.path.join(tempfile.gettempdir(), "NotoSansJP-Regular.ttf")
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/shindome/noto-emoji-jp/raw/master/fonts/NotoSansJP-Regular.ttf"
            urllib.request.urlretrieve(url, font_path)
        except:
            pass
            
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(font_path):
        pdf.add_font("NotoSansJP", "", font_path)
        pdf.set_font("NotoSansJP", size=10)
    else:
        pdf.set_font("Helvetica", size=10)
        
    # Title Header (Black Autodesk Banner)
    pdf.set_fill_color(0, 0, 0)
    pdf.rect(0, 0, 210, 42, "F")
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("NotoSansJP", size=15)
    pdf.text(15, 20, "AUTODESK SOLUTION ASSESSMENT REPORT")
    pdf.set_font("NotoSansJP", size=10)
    pdf.text(15, 30, f"{survey_title} - 診断結果レポート")
    
    # Client Info Block
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 245, 242)
    pdf.rect(15, 50, 180, 30, "F")
    pdf.set_font("NotoSansJP", size=9)
    pdf.text(20, 57, f"回答者氏名: {res_name} 様")
    pdf.text(20, 64, f"部署・チーム: {res_team if res_team else '未登録'}")
    pdf.text(20, 71, f"連絡先メール: {res_email}  (経験年数: {res_exp})")
    
    # Gap analysis Table
    pdf.set_font("NotoSansJP", size=11)
    pdf.text(15, 95, "アセスメント評価 Gap 分析")
    
    pdf.line(15, 99, 195, 99)
    pdf.set_font("NotoSansJP", size=8.5)
    pdf.text(17, 104, "設問ID")
    pdf.text(32, 104, "評価カテゴリ / フェーズ")
    pdf.text(125, 104, "As-Is (現状)")
    pdf.text(150, 104, "To-Be (目標)")
    pdf.text(175, 104, "Gap (乖離)")
    pdf.line(15, 107, 195, 107)
    
    y = 113
    for a in answers_list:
        pdf.text(17, y, str(a["question_id"]))
        pdf.text(32, y, f"{a['phase']} ({a['department']})")
        pdf.text(133, y, str(a["as_is"]))
        pdf.text(158, y, str(a["to_be"]))
        
        gap_val = 0
        if a["as_is"] != "N/A" and a["to_be"] != "N/A":
            gap_val = int(a["to_be"]) - int(a["as_is"])
            
        pdf.text(180, y, str(gap_val) if a["as_is"] != "N/A" else "N/A")
        y += 7
        
    pdf.line(15, y-2, 195, y-2)
    
    # Proposal Section
    pdf.ln(y - 95 + 10)
    pdf.set_font("NotoSansJP", size=11)
    pdf.cell(0, 10, "推奨 Autodesk ソリューションのご提案", ln=True)
    pdf.ln(2)
    
    display_count = 0
    for gap_item in gaps_sorted:
        qid = gap_item["question_id"]
        if qid in proposals_dict and gap_item["gap"] >= 1:
            prop = proposals_dict[qid]
            pdf.set_font("NotoSansJP", size=10)
            pdf.set_text_color(255, 120, 0)
            pdf.cell(0, 6, f"■ {prop['title']}", ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("NotoSansJP", size=8.5)
            pdf.multi_cell(180, 5, prop["desc"])
            pdf.set_text_color(29, 145, 208)
            pdf.cell(0, 5, f"製品詳細リンク: {prop['url']}", ln=True)
            pdf.ln(4)
            display_count += 1
            if display_count >= 2:
                break
                
    if display_count == 0:
        pdf.set_font("NotoSansJP", size=10)
        pdf.set_text_color(255, 120, 0)
        pdf.cell(0, 6, "■ Autodesk Tandem", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("NotoSansJP", size=8.5)
        pdf.multi_cell(180, 5, "設備管理デジタルツインプラットフォームをご検討ください。BIMモデルやアセット情報、リアルタイムIoTデータを連携し、効率的な建物維持管理プロセスを実現します。")
        pdf.set_text_color(29, 145, 208)
        pdf.cell(0, 5, "製品詳細リンク: https://www.autodesk.com/products/tandem/overview", ln=True)
        
    return pdf.output()

# Load Questions
def load_all_questions_json():
    if not DATA_JSON.exists():
        st.error(f"質問定義ファイルが見つかりません: {DATA_JSON}")
        return {}
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def get_active_questions():
    # 安全にクエリパラメータを取得（新旧バージョン互換性ハック）
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
            return pd.DataFrame(custom_survey["questions"]), survey_id, custom_survey.get("client_name")
        else:
            st.warning(f"指定されたアンケートID `{survey_id}` が登録されていません。デフォルトの設問を表示します。")
            
    # クエリパラメータに 'model' があり、'factory_cloud' が指定されている場合は新モデルをデフォルトに
    model_param = None
    try:
        model_param = st.query_params.get("model")
    except AttributeError:
        try:
            model_param = st.experimental_get_query_params().get("model", [None])[0]
        except:
            pass
            
    all_qs = load_all_questions_json()
    if model_param == "factory_cloud" and "factory_cloud_questions" in all_qs:
        return pd.DataFrame(all_qs["factory_cloud_questions"]), "default", None
        
    return pd.DataFrame(all_qs.get("questions", [])), "default", None

q_df, active_survey_id, client_name = get_active_questions()

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
            worksheet = sh.add_worksheet(title="成熟度回答", rows="100", cols="10")
            new_headers = ["timestamp", "respondent", "email", "experience_years", "department", "team", "question_id", "phase", "as_is", "to_be"]
            worksheet.append_row(new_headers)
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
                r["department"], r["team"], r["question_id"], r["phase"], r["as_is"], r["to_be"]
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
    
    if df_sheets.empty:
        return df_firestore
    if df_firestore.empty:
        if "survey_id" not in df_sheets.columns:
            df_sheets["survey_id"] = "default"
        return df_sheets
        
    if "survey_id" not in df_sheets.columns:
        df_sheets["survey_id"] = "default"
        
    df_sheets["as_is"] = pd.to_numeric(df_sheets["as_is"], errors='coerce')
    df_sheets["to_be"] = pd.to_numeric(df_sheets["to_be"], errors='coerce')
    df_firestore["as_is"] = pd.to_numeric(df_firestore["as_is"], errors='coerce')
    df_firestore["to_be"] = pd.to_numeric(df_firestore["to_be"], errors='coerce')
    
    return pd.concat([df_sheets, df_firestore], ignore_index=True)

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email.strip()) is not None

if q_df.empty:
    st.stop()

# Question ID to Autodesk Brand Image Mapping Table (Expanded to support FC01-FC08)
IMAGE_MAPPING = {
    "FI01": "fy27-aec-forma-industry-cloud-imagery.webp",
    "FI02": "brand-image-prototype-1-dark.webp",
    "FI03": "Construction-CCEED-China-0644_with_overlay.webp",
    "FI04": "fy27-water-image-02.webp",
    "PE01": "fy27-dm-digital-factory-campaign-visual-01.webp",
    "PE02": "fy27-dm-fusion-industry-cloud-imagery.webp",
    "PE03": "Tech-Center-Birmingham-industrial-robots-086_with_overlay.webp",
    "PE04": "brand-image-prototype-4-dark.webp",
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
    # Default fallback container
    st.markdown(
        """
        <div style="
            border: 1px solid #666666; 
            background-color: #121212;
            height: 220px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            border-radius: 0px;
            color: #D5D5CB;
            font-size: 0.9rem;
            font-family: monospace;
            margin-bottom: 20px;
        ">
        [ AUTODESK // PRECISION_DESIGN_SYSTEM ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand Header Layout (Dynamic 2-Stacked Logo on Left, Title on Right for Visual Hierarchy)
# Flattened to single-line HTML to bypass Streamlit's markdown parser codeblock fallback bug
stacked_logo_svg = '<svg width="220" height="85" viewBox="0 0 220 85" fill="none" xmlns="http://www.w3.org/2000/svg"><g transform="scale(2.4) translate(30, 1)"><path d="M0.538536 22.7316L19.9163 10.678H29.9686C30.2781 10.678 30.5561 10.9259 30.5561 11.2662C30.5561 11.5442 30.4321 11.6681 30.2781 11.7605L20.7598 17.4657C20.1416 17.8368 19.9252 18.579 19.9252 19.1356L19.9155 22.7316H32.0097V1.83296C32.0097 1.4303 31.7002 1.09078 31.2367 1.09078H19.6999L0.369995 13.091V22.7316L0.538536 22.7316Z" fill="white"/></g><text x="110" y="74" fill="white" font-family="\'Inter\', sans-serif" font-size="18" font-weight="900" letter-spacing="4.5" text-anchor="middle">AUTODESK</text></svg>'

header_html = f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; margin-bottom: 10px; gap: 20px;"><div style="width: 220px; display: flex; align-items: center;">{stacked_logo_svg}</div><div style="text-align: right; min-width: 250px;"><div style="font-size: 0.75rem; color: #666666; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Maturity Evaluation Platform</div><div style="font-size: 1.7rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.03em;">IFM Maturity Assessment</div></div></div>'

st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Hide Navigation Tabs for Clients
is_client_access = False
try:
    is_client_access = "survey_id" in st.query_params
except AttributeError:
    try:
        is_client_access = "survey_id" in st.experimental_get_query_params()
    except:
        pass

if is_client_access:
    tabs = st.tabs(["アセスメント回答"])
    tab_input = tabs[0]
    tab_dashboard = None
    tab_admin = None
else:
    tabs = st.tabs(["アセスメント回答", "結果分析", "営業管理"])
    tab_input = tabs[0]
    tab_dashboard = tabs[1]
    tab_admin = tabs[2]

### 📝 Tab 1: 回ザー回答入力フォーム ###
with tab_input:
    col_left_form, col_right_chart = st.columns([11, 9])
    
    # セッション状態管理:
    # current_step == 0: 個人情報入力 ＆ プライバシーポリシー同意画面 (Step 0)
    # current_step >= 1: 設問 1 〜 10 の回答画面
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
        
    num_questions = len(q_df)
    
    # 送信完了フラグ
    if "is_submitted" not in st.session_state:
        st.session_state.is_submitted = False
        
    with col_left_form:
        if st.session_state.is_submitted:
            # --- 送信完了＆おすすめ製品動的提案画面 ---
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF;'>アセスメント回答送信完了</h3>", unsafe_allow_html=True)
            st.success("アセスメントの回答が安全に記録されました。ご協力ありがとうございました。")
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#FFFF00; font-weight:700; margin-bottom:10px;'>お客様の回答に基づく最適なソリューション提案</h4>", unsafe_allow_html=True)
            st.markdown("<p style='color:#D5D5CB; font-size:0.92rem; margin-bottom:20px;'>回答から抽出された「現在の課題（As-Is）」と「目指したいゴール（To-Be）」の乖離値（Gap）を自動分析し、最適な解決策をご提案いたします。</p>", unsafe_allow_html=True)
            
            # 各設問のGap分析
            gaps = []
            answers_list_for_pdf = []
            for _, r in q_df.iterrows():
                qid = r['question_id']
                is_skipped = st.session_state.get(f"skip_{qid}", False)
                as_is = st.session_state.get(f"asis_{qid}", 2) if not is_skipped else "N/A"
                to_be = st.session_state.get(f"tobe_{qid}", 4) if not is_skipped else "N/A"
                
                answers_list_for_pdf.append({
                    "question_id": qid,
                    "phase": r["phase"],
                    "department": r["department"],
                    "as_is": as_is,
                    "to_be": to_be
                })
                
                if not is_skipped:
                    gaps.append({
                        "question_id": qid,
                        "phase": r['phase'],
                        "gap": to_be - as_is,
                        "to_be": to_be
                    })
            
            # Gapが大きい順（且つTo-Beが高い順）にソート
            gaps_sorted = sorted(gaps, key=lambda x: (x["gap"], x["to_be"]), reverse=True)
            
            # 製品提案マッピングテーブル
            # 新モデル（FC01-FC08）および既存IFMモデル双方に対応
            PRODUCT_PROPOSALS = {
                "FC01": {
                    "title": "AEC環境シミュレーションクラウド - Autodesk Forma",
                    "desc": "初期計画段階での敷地分析、日影・騒音・風向シミュレーションの生産性向上に大きな乖離が見られます。Autodesk Formaを導入することで、敷地規制や環境影響をクラウド上のAIで即時解析し、手戻りの少ない初期配置計画を迅速に策定できます。",
                    "url": "https://www.autodesk.com/products/forma/overview"
                },
                "FC02": {
                    "title": "離散イベント生産シミュレーション - FlexSim",
                    "desc": "製造工程や搬送・AGVルートのボトルネック検証に大きな改善余地があります。FlexSimを用いることで、工場レイアウト設計に『時間の概念』をプラスした高度なシミュレーションを実行し、無駄な設備投資の発生を防ぎます。",
                    "url": "https://www.autodesk.com/products/flexsim/overview"
                },
                "FC03": {
                    "title": "2D/3D双方向レイアウト設計同期 - Factory Design Utilities",
                    "desc": "AutoCADによる平面計画と、Inventorによる3D設備アセンブリの連携に課題感が見られます。Factory Design Utilitiesを使用することで、2Dと3Dがリアルタイムに相互同期し、干渉チェックと整合性維持を全自動で行えます。",
                    "url": "https://www.autodesk.com/solutions/factory-design"
                },
                "FC04": {
                    "title": "AI搭載次世代設計モデリング - Navpack / Navasto",
                    "desc": "AIを用いた自律型モデリングおよび設計支援に強い関心があるようです。過去の3D設計データを学習したAIエンジンと連携することで、形状要件を満たすバリエーションを自動生成し、設計効率を劇的に高めます。",
                    "url": "https://www.autodesk.com/solutions/generative-design"
                },
                "FC05": {
                    "title": "作図およびデータ連携の自動化 - AutoCAD API & 業種別ツールセット",
                    "desc": "CAD内での定型処理の自動化やBOM連携にGapがあります。AutoCADの専用ツールセットやLISP/APIの本格導入により、図面から部品表の作成、データ統合などの手作業を完全に自動化できます。",
                    "url": "https://www.autodesk.com/products/autocad/overview"
                },
                "FC06": {
                    "title": "クラウド統合データ環境 - Autodesk Construction Cloud (ACC)",
                    "desc": "社内外のサプライヤーとの協調設計および履歴管理に乖離が見られます。ACCを導入することで、常に最新の3DモデルをWeb上でセキュアに共有し、バージョン管理や承認ワークフローを効率化します。",
                    "url": "https://www.autodesk.com/products/autodesk-construction-cloud/overview"
                },
                "FC07": {
                    "title": "直感的なバーチャル合意形成 - FlexSim VR/AR",
                    "desc": "意思決定プロセスにおける合意形成スピードの向上に大きなGapがあります。FlexSimのシミュレーションとVR（仮想現実）を連動させ、実物大の工場内を体験しながら検証することで、社内会議の意思決定を劇的に迅速化します。",
                    "url": "https://www.autodesk.com/products/flexsim/overview"
                },
                "FC08": {
                    "title": "パラメータ駆動型設計自動化 - Inventor iLogic",
                    "desc": "設計の再利用とバリエーション展開に課題があります。iLogicのルールエンジンを構築することで、注文仕様に応じたアセンブリの自動構成から、製造用図面の自動出力を一気通貫で自動化できます。",
                    "url": "https://www.autodesk.com/products/inventor/overview"
                },
                # 既存のIFMモデル（PE01-PE05, FI01-FI05）からのマッピングフォールバック
                "PE05": {
                    "title": "建物・設備デジタルツイン - Autodesk Tandem",
                    "desc": "運用および保全段階におけるデータの一元管理において乖離が見られます。Autodesk Tandemを導入して建物のデジタルツインを構築し、BIMデータとリアルタイムアセットデータを連携させることで、予知保全をスマートに推進します。",
                    "url": "https://www.autodesk.com/products/tandem/overview"
                },
                "PE03": {
                    "title": "3D統合コーディネーション - Autodesk Navisworks",
                    "desc": "設計内容の統合検証・干渉チェックの自動化にGapがあります。Navisworksにより、複数の異なるフォーマットの3Dモデルを単一の環境に統合し、自動干渉検出と変更追跡を行うことで、施工手戻りを防ぎます。",
                    "url": "https://www.autodesk.com/products/navisworks/overview"
                }
            }
            
            # Gapが大きい上位2製品を抽出して表示
            display_count = 0
            for gap_item in gaps_sorted:
                qid = gap_item["question_id"]
                if qid in PRODUCT_PROPOSALS and gap_item["gap"] >= 1: # Gapが1以上あるもののみ推奨
                    prop = PRODUCT_PROPOSALS[qid]
                    st.markdown(
                        f"""
                        <div class="proposal-card">
                            <div class="proposal-title">{prop['title']}</div>
                            <div class="proposal-desc">{prop['desc']}</div>
                            <a href="{prop['url']}" target="_blank" class="proposal-link-btn">製品の詳細情報を確認する</a>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    display_count += 1
                    if display_count >= 2: # 最大2つ表示
                        break
                        
            if display_count == 0:
                # 目立ったGapがない場合のデフォルトプレミアム推奨
                st.markdown(
                    """
                    <div class="proposal-card">
                        <div class="proposal-title">Autodesk Product Design & Manufacturing Collection (PDMC)</div>
                        <div class="proposal-desc">お客様の全体的な成熟度はすでに非常に高い水準にあります。AutoCAD、Inventor、Factory Design Utilitiesを網羅したPDMCコレクションパッケージをご活用いただくことで、デジタルファクトリー全体のプロセスをさらに統合・洗練できます。</div>
                        <a href="https://www.autodesk.com/collections/product-design-manufacturing/overview" target="_blank" class="proposal-link-btn">PDMC コレクションの詳細を確認する</a>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            # PDF診断書ダウンロードボタンの実装
            with st.spinner("PDFレポートを準備中..."):
                pdf_data = generate_pdf_report_bytes(
                    res_name=st.session_state.get("res_name", "テスト回答者"),
                    res_email=st.session_state.get("res_email", "info@autodesk.com"),
                    res_team=st.session_state.get("res_team", "未設定"),
                    res_exp=st.session_state.get("res_exp", "未設定"),
                    answers_list=answers_list_for_pdf,
                    gaps_sorted=gaps_sorted,
                    proposals_dict=PRODUCT_PROPOSALS,
                    survey_title="アセスメント"
                )
            
            st.download_button(
                label="診断結果レポート (PDF) をダウンロード",
                data=pdf_data,
                file_name=f"Autodesk_Assessment_Report_{active_survey_id}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
            st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
            if st.button("アセスメントを再回答する", type="secondary", use_container_width=True):
                st.session_state.is_submitted = False
                st.session_state.current_step = 0
                st.rerun()

        elif st.session_state.current_step == 0:
            # --- STEP 0: プロファイル ＆ プライバシーポリシー同意画面 ---
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF;'>回答者プロファイル ＆ 同意確認</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color:#D5D5CB; font-size:0.95rem; margin-bottom:20px;'>アセスメントを開始する前に、以下のプロファイル情報の入力と、個人情報の取り扱いへのご同意をお願いいたします。</p>", unsafe_allow_html=True)
            
            # 入力フィールド群
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
            
            # 個人情報同意チェックボックス（先にチェック欄を配置）
            agree_privacy = st.checkbox("個人情報の取り扱い説明事項を確認し、同意します。 *", value=st.session_state.get("agree_privacy", False), key="agree_privacy_step0")
            st.session_state["agree_privacy"] = agree_privacy
            
            # 同意チェックが入っていない（False）ときのみ、法務確認済みのポリシー文面（プレースホルダー）を表示
            if not agree_privacy:
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                st.markdown("<b style='font-size:0.85rem; color:#666666;'>【確認用：個人情報保護に関する同意文面（法務確認中プレースホルダー）】</b>", unsafe_allow_html=True)
                privacy_policy_text = "[法務確認済みの個人情報保護方針に関する詳細な同意文面がここに入ります。チェックボックスに同意を入れると、この文面エリアは自動的に非表示になり、アセスメント開始ボタンに素早くアクセスできるようになります。]"
                st.markdown(
                    f'<div style="background-color:#121212; border:1px solid #333333; border-radius:8px; padding:15px; font-size:0.88rem; color:#8C9BA5; line-height:1.5; white-space:pre-wrap; transition: all 0.2s ease;">'
                    f'{privacy_policy_text}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            
            # バリデーションチェック
            inputs_valid = (
                respondent_name.strip() != "" and 
                email_input.strip() != "" and 
                is_valid_email(email_input) and 
                experience_years is not None and 
                agree_privacy
            )
            
            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
            
            # アセスメント開始ボタン
            if st.button("自己アセスメントを開始する", type="primary", disabled=not inputs_valid, use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
                
        else:
            # --- STEP 1 〜 10: 設問回答画面 (プロファイルは画面外に隠蔽) ---
            current_idx = st.session_state.current_step - 1
            row = q_df.iloc[current_idx]
            qid = row['question_id']
            
            # ステップ送りナビゲーション
            st.markdown(
                f"<div style='font-size:0.85rem; color:#FFFF00; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;'>"
                f"{row['department']} 領域  ·  STEP {st.session_state.current_step} / {num_questions}</div>",
                unsafe_allow_html=True
            )
            st.markdown(f"<h3 style='margin-top:2px; font-size:1.6rem; font-weight:700;'>{row['question_id']} ({row['phase']})</h3>", unsafe_allow_html=True)
            
            # 設問カード (無骨な囲み枠の余白を極限まで圧縮し、フォントサイズを最適化して一画面に収める)
            st.markdown(
                f"<div style='background-color:#121212; padding:12px 16px; border-left:3px solid #FFFF00; margin-bottom:12px; font-size:0.95rem; line-height:1.5; color:#FFFFFF;'>"
                f"{row['question_text']} 各レベルの定義を参考に、現状と目標を選択してください。</div>", 
                unsafe_allow_html=True
            )
            
            # 該当しない場合のスキップ
            skip_key = f"skip_{qid}"
            if skip_key not in st.session_state:
                st.session_state[skip_key] = False
            skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key)
            
            # プレースホルダー（コンテナ）を作成し、画面順序とパース順序を逆転させてRDP表示を上に持ってくる
            levels_container = st.container()
            profile_container = st.container()
            
            # 回答用のバー二つは画面の一番下側（送信ボタンのすぐ上）に配置
            slider_container = st.container()
            
            with slider_container:
                st.markdown("<hr style='border-color:#333333; margin:8px 0;'>", unsafe_allow_html=True)
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    as_is_val = st.slider(
                        "現状の成熟度評価 (As-Is)", 
                        1, 5, 
                        key=f"asis_{qid}", 
                        disabled=skip
                    )
                with col_s2:
                    to_be_val = st.slider(
                        "将来の目標成熟度 (To-Be)", 
                        1, 5, 
                        key=f"tobe_{qid}", 
                        disabled=skip
                    )
            
            # 1画面に収めるため、余白とフォントサイズをギュッと凝縮したレベルカードを描画
            with levels_container:
                if not skip:
                    levels_html = "<div style='display: flex; flex-direction: column; gap: 5px; margin-top: 5px;'>"
                    for lvl in ["L1", "L2", "L3", "L4", "L5"]:
                        lvl_num = int(lvl[1])
                        is_asis = (as_is_val == lvl_num)
                        is_tobe = (to_be_val == lvl_num)
                        
                        border_color = "rgba(102, 102, 102, 0.2)" 
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
                            
                        levels_html += f'<div style="border-left: 3px solid {border_color}; background-color: {bg_color}; padding: 6px 12px; border-top: 1px solid rgba(102,102,102,0.1); border-right: 1px solid rgba(102,102,102,0.1); border-bottom: 1px solid rgba(102,102,102,0.1); transition: all 0.15s ease;"><div style="display: flex; align-items: center; margin-bottom: 2px;">{badge_html}<b style="font-size: 0.8rem; color: #D5D5CB;">Level {lvl_num}</b></div><div style="font-size: 0.82rem; color: #FFFFFF; line-height: 1.35;">{row["levels"][lvl]}</div></div>'
                    levels_html += "</div>"
                    st.markdown(levels_html, unsafe_allow_html=True)
            
            with profile_container:
                st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
                with st.expander("登録プロファイル・個人情報同意事項の確認と変更"):
                    st.markdown("<p style='font-size:0.85rem; color:#D5D5CB; margin-bottom:10px;'>登録情報を変更すると、すべての設問の送信データにリアルタイムに反映されます。</p>", unsafe_allow_html=True)
                    
                    edit_name = st.text_input("回答者名 *", value=st.session_state.get("res_name", ""), key="edit_name")
                    st.session_state["res_name"] = edit_name
                    
                    edit_email = st.text_input("メールアドレス *", value=st.session_state.get("res_email", ""), key="edit_email")
                    st.session_state["res_email"] = edit_email
                    
                    edit_exp = st.selectbox(
                        "勤続年数 *",
                        ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"],
                        index=["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"].index(st.session_state.get("res_exp")) if st.session_state.get("res_exp") in ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"] else 0,
                        key="edit_exp"
                    )
                    st.session_state["res_exp"] = edit_exp
                    
                    edit_team = st.text_input("部署名・チーム名 (任意)", value=st.session_state.get("res_team", ""), key="edit_team")
                    st.session_state["res_team"] = edit_team
                    
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    st.markdown("<b style='font-size:0.88rem; color:#FFFFFF;'>【同意ステータス】</b>", unsafe_allow_html=True)
                    edit_agree = st.checkbox("個人情報の取り扱い説明事項に同意します *", value=st.session_state.get("agree_privacy", False), key="edit_agree")
                    st.session_state["agree_privacy"] = edit_agree
                    
                    if not edit_agree:
                        st.markdown("<div style='margin-top:5px;'></div>", unsafe_allow_html=True)
                        st.info("[法務確認済みの個人情報保護方針に関する詳細な同意文面がここに入ります。]")
                
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            
            # ナビゲーションボタン群 (絵文字を徹底排除、type="secondary" による対比)
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            with col_btn1:
                if st.button("前の画面", type="secondary", use_container_width=True):
                    st.session_state.current_step -= 1
                    st.rerun()
                    
            with col_btn2:
                next_disabled = st.session_state.current_step == num_questions
                if st.button("次の設問", type="secondary", disabled=next_disabled, use_container_width=True):
                    st.session_state.current_step += 1
                    st.rerun()
                    
            with col_btn3:
                is_last_step = st.session_state.current_step == num_questions
                profile_valid = (
                    st.session_state.get("res_name", "").strip() != "" and
                    st.session_state.get("res_email", "").strip() != "" and
                    is_valid_email(st.session_state.get("res_email", "")) and
                    st.session_state.get("res_exp") is not None and
                    st.session_state.get("agree_privacy", False)
                )
                submit_disabled = not (is_last_step and profile_valid)
                submit_clicked = st.button("アセスメント結果を最終送信する", type="primary", disabled=submit_disabled, use_container_width=True)
                
                if is_last_step and not st.session_state.get("agree_privacy", False):
                    st.warning("送信するには個人情報の取り扱いへの同意が必要です（『登録プロファイル・個人情報同意事項の確認と変更』から同意をオンにできます）。")

    with col_right_chart:
        # 送信完了後はチャート側の表示を固定
        if st.session_state.is_submitted:
            render_hero_image("PE01")
        elif st.session_state.current_step == 0:
            render_hero_image("PE01") 
        else:
            render_hero_image(qid)
            
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

    # 送信処理のバリデーションと実行
    if not st.session_state.is_submitted and st.session_state.current_step == num_questions and submit_clicked:
        res_name = st.session_state.get("res_name", "").strip()
        res_email = st.session_state.get("res_email", "").strip()
        res_exp = st.session_state.get("res_exp")
        res_team = st.session_state.get("res_team", "").strip()
        agree_privacy = st.session_state.get("agree_privacy", False)
        
        if not res_name:
            st.error("回答者名を入力してください。")
        elif not res_email or not is_valid_email(res_email):
            st.error("有効なメールアドレスを入力してください。")
        elif not res_exp:
            st.error("勤続年数を選択してください。")
        elif not agree_privacy:
            st.error("個人情報の取り扱いへの同意が必要です。")
        else:
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
                    "to_be": to_be_val
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
                fs_success = save_response_to_firestore(firestore_doc)
                sheets_success = False
                if fs_success:
                    sheets_success = save_response_to_sheets(records)
                
                if fs_success:
                    st.balloons()
                    st.session_state.is_submitted = True
                    st.rerun()
                else:
                    st.error("送信に失敗しました。管理者にお問い合わせください。")


### 📊 Tab 2: 結果分析ダッシュボード ###
if tab_dashboard:
    with tab_dashboard:
        st.header("成熟度アセスメントの分析・比較")
        dash_pw = st.text_input("結果分析ダッシュボード閲覧用パスワード", type="password", key="dash_pw_input")
        
        if dash_pw == "ifm-sales":
            st.success("認証されました。")
            resp_df = load_all_responses_merged()
            
            if resp_df.empty:
                st.warning("現在、回答データが存在しません。")
            else:
                st.subheader("絞り込みとグループ比較")
                compare_mode = st.checkbox("2つのグループを比較する（比較モード）", value=False, key="dash_compare")
                
                unique_domains = sorted([str(d) for d in resp_df['domain'].unique() if d and pd.notna(d)])
                registered_surveys = get_all_custom_survey_ids()
                unique_surveys = sorted(list(set([str(s) for s in resp_df['survey_id'].unique() if s and pd.notna(s)] + registered_surveys + ["default"])))
                unique_years = ["すべて", "0～2年", "2～5年", "5～10年", "10～15年", "15年以上"]
                
                def filter_data(data, domain, exp, team_kw, category, survey):
                    filtered = data.copy()
                    if survey != "すべて":
                        filtered = filtered[filtered['survey_id'] == survey]
                    if domain != "すべて":
                        filtered = filtered[filtered['domain'] == domain]
                    if exp != "すべて":
                        filtered = filtered[filtered['experience_years'] == exp]
                    if team_kw.strip():
                        filtered = filtered[filtered['team'].str.contains(team_kw.strip(), case=False, na=False)]
                    if category == "生産技術のみ":
                        filtered = filtered[filtered['department'] == "生産技術"]
                    elif category == "工場建築・建設のみ":
                        filtered = filtered[filtered['department'] == "工場建築・建設"]
                    return filtered

                if compare_mode:
                    col_filter_a, col_filter_b = st.columns(2)
                    with col_filter_a:
                        st.markdown("#### グループA の条件")
                        survey_a = st.selectbox("アンケートID (グループA)", ["すべて"] + unique_surveys, key="survey_a")
                        domain_a = st.selectbox("ドメイン (グループA)", ["すべて"] + unique_domains, key="domain_a")
                        exp_a = st.selectbox("勤続年数 (グループA)", unique_years, key="exp_a")
                        team_a = st.text_input("部署名（部分一致・グループA）", key="team_a", placeholder="例: 技術部")
                        cat_a = st.radio("表示カテゴリ (グループA)", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="cat_a", horizontal=True)
                        
                    with col_filter_b:
                        st.markdown("#### グループB の条件")
                        survey_b = st.selectbox("アンケートID (グループB)", ["すべて"] + unique_surveys, key="survey_b")
                        domain_b = st.selectbox("ドメイン (グループB)", ["すべて"] + unique_domains, key="domain_b")
                        exp_b = st.selectbox("勤続年数 (グループB)", unique_years, key="exp_b")
                        team_b = st.text_input("部署名（部分一致・グループB）", key="team_b", placeholder="例: 建築")
                        cat_b = st.radio("表示カテゴリ (グループB)", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="cat_b", horizontal=True)
                        
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
                    cat_a = st.radio("表示カテゴリ", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="single_cat", horizontal=True)
                    df_a = filter_data(resp_df, domain_a, exp_a, team_a, cat_a, survey_a)
                    df_b = pd.DataFrame()

                # レーダーチャート比較プロット
                agg_a = df_a.groupby(['question_id', 'phase'])[['as_is', 'to_be']].mean().reset_index()
                agg_a = agg_a.sort_values('question_id')
                theta_labels = [f"{row['phase']}\n({row['question_id']})" for _, row in agg_a.iterrows()]
                
                fig = go.Figure()
                if not agg_a.empty:
                    fig.add_trace(go.Scatterpolar(
                        r=agg_a['as_is'].tolist() + [agg_a['as_is'].tolist()[0]],
                        theta=theta_labels + [theta_labels[0]],
                        fill='toself',
                        name='グループA: 現状の評価',
                        line_color='#1D91D0',
                        fillcolor='rgba(29, 145, 208, 0.1)',
                        line=dict(width=1.5)
                    ))
                    fig.add_trace(go.Scatterpolar(
                        r=agg_a['to_be'].tolist() + [agg_a['to_be'].tolist()[0]],
                        theta=theta_labels + [theta_labels[0]],
                        fill='toself',
                        name='グループA: 将来の目標',
                        line_color='#2AD0A9',
                        fillcolor='rgba(42, 208, 169, 0.05)',
                        line=dict(width=1.2, dash='dash')
                    ))
                
                if compare_mode and not df_b.empty:
                    agg_b = df_b.groupby(['question_id', 'phase'])[['as_is', 'to_be']].mean().reset_index()
                    agg_b = agg_b.sort_values('question_id')
                    if not agg_b.empty:
                        fig.add_trace(go.Scatterpolar(
                            r=agg_b['as_is'].tolist() + [agg_b['as_is'].tolist()[0]],
                            theta=theta_labels + [theta_labels[0]],
                            fill='toself',
                            name='グループB: 現状の評価',
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
                
                # 組織内認識ギャップ分析セクションの追加
                st.markdown("<hr style='border-color:#333333; margin:25px 0;'>", unsafe_allow_html=True)
                st.subheader("組織内・認識の歪み（ギャップ）分析")
                
                if len(df_a['email'].unique()) < 2:
                    st.info("※ このアンケートIDに対する複数回答データが不足しています。組織内ギャップ分析を行うには2名以上の回答が必要です。")
                else:
                    st.markdown("<p style='font-size:0.92rem; color:#D5D5CB; margin-bottom:15px;'>同じアンケートIDに対する複数名の回答から、現場層（勤続年数5年未満）と意思決定層（勤続年数10年以上）の間の【認識ギャップ】を抽出します。</p>", unsafe_allow_html=True)
                    
                    # 現場層データ (勤続5年未満)
                    genba_df = df_a[df_a['experience_years'].isin(["0～2年", "2～5年"])]
                    # マネジメント層データ (勤続10年以上)
                    mgmt_df = df_a[df_a['experience_years'].isin(["10～15年", "15年以上"])]
                    
                    agg_genba = genba_df.groupby(['question_id', 'phase'])['as_is'].mean().reset_index().sort_values('question_id')
                    agg_mgmt = mgmt_df.groupby(['question_id', 'phase'])['as_is'].mean().reset_index().sort_values('question_id')
                    
                    fig_gap = go.Figure()
                    
                    if not agg_genba.empty:
                        fig_gap.add_trace(go.Scatterpolar(
                            r=agg_genba['as_is'].tolist() + [agg_genba['as_is'].tolist()[0]],
                            theta=theta_labels + [theta_labels[0]],
                            fill='toself',
                            name='現場担当層 (勤続5年未満) - As-Is',
                            line_color='#2AD0A9',
                            fillcolor='rgba(42, 208, 169, 0.04)',
                            line=dict(width=1.5)
                        ))
                        
                    if not agg_mgmt.empty:
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
                        st.markdown("<h5 style='color:#FFFFFF; font-weight:700; margin-bottom:10px;'>🚨 組織内認識不一致度アラート</h5>", unsafe_allow_html=True)
                        
                        # ギャップ算出
                        gap_details = []
                        for q in df_a['question_id'].unique():
                            val_genba = genba_df[genba_df['question_id'] == q]['as_is'].mean()
                            val_mgmt = mgmt_df[mgmt_df['question_id'] == q]['as_is'].mean()
                            
                            if pd.notna(val_genba) and pd.notna(val_mgmt):
                                diff = abs(val_mgmt - val_genba)
                                phase_name = df_a[df_a['question_id'] == q]['phase'].iloc[0]
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
                                st.write("現場層と意思決定層の認識はほぼ完全に一致しており、足並みが綺麗に揃っています。")
                        else:
                            st.write("各回答者層におけるデータが不足しています。")
        else:
            if dash_pw != "":
                st.error("パスワードが正しくありません。")


### 🔧 Tab 3: 営業管理（カスタム発行） ###
if tab_admin:
    with tab_admin:
        st.header("営業担当用 カスタムアンケート発行管理")
        admin_pw = st.text_input("管理用パスワード", type="password", key="admin_pw_input")
        
        if admin_pw == "ifm-sales":
            st.success("認証されました。")
            
            st.subheader("1. アンケート基本設定")
            col_ad1, col_ad2 = st.columns(2)
            with col_ad1:
                new_survey_id = st.text_input("アンケートID (英数字・ハイフンのみ) *", placeholder="例: toyota-2026")
                new_client_name = st.text_input("顧客企業名 *", placeholder="例: トヨタ自動車株式会社")
            with col_ad2:
                new_creator = st.text_input("作成者名 *", placeholder="例: 佐藤 営業担当")
                
            # モデルテンプレートのセレクトボックスを追加 (絵文字を徹底排除)
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
            
            # 選択されたモデルタイプに基づいてベース設問とappパラメータを決定
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
                        st.info("テスト用リンク (ローカル環境):")
                        st.code(local_url, language=None)
            
            # 最新の回答データを取得してレコメンドを表示するセクション
            st.markdown("---")
            st.subheader("4. 最新アセスメント回答通知 ＆ AIセールスレコメンド")
            
            # Firestoreから全回答をロード
            resp_df_all = load_responses_from_firestore()
            if resp_df_all.empty:
                st.info("まだ回答データが存在しません。")
            else:
                # 最も新しいタイムスタンプを取得
                latest_ts = resp_df_all['timestamp'].max()
                
                # そのタイムスタンプを持つ回答者の一連の回答行を抽出
                latest_rows = resp_df_all[resp_df_all['timestamp'] == latest_ts]
                
                if not latest_rows.empty:
                    # 代表情報を取得
                    first_row = latest_rows.iloc[0]
                    res_name = first_row.get("respondent", "匿名")
                    res_team = first_row.get("team", "部署未設定")
                    res_email = first_row.get("email", "なし")
                    res_sid = first_row.get("survey_id", "default")
                    
                    formatted_ts = str(latest_ts).replace("T", " ")[:19]
                    
                    # アンケートタイプの判定
                    qids = latest_rows['question_id'].tolist()
                    survey_type_lbl = "設備管理成熟度診断 (IFM)"
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
                    
                    # Gap計算
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
                        # AI推奨アプローチ・セールストークロジック
                        recommendations_map = {
                            # Factory Cloud
                            "FC01": "Formaによる敷地風向・日影解析デモをオファーし、『初期計画段階でのAI迅速シミュレーションによる手戻り削減』をフックにアプローチしてください。",
                            "FC02": "FlexSimによる工程シミュレーションデモを提案。『時間軸を考慮した設備能力と搬送ルートの最適化』をアピールして、工場部門への商談を開始してください。",
                            "FC03": "Factory Design Utilities (FDU) を紹介。『AutoCADとInventorの2D/3D双方向同期による干渉チェック』が最も響くアプローチです。",
                            "FC04": "AIモデリング（Navastoなど）やジェネレーティブデザインの紹介スライドを持参し、設計プロセスの自律化を切り口に会話を展開してください。",
                            "FC05": "AutoCAD専用ツールセットやAPI/LISPによる作図・BOM出力の『定型業務自動化』をフックにし、開発期間の圧縮を提案してください。",
                            "FC06": "Autodesk Construction Cloud (ACC) CDEによる『サプライヤとの安全なリアルタイム3Dモデル共有・整合性維持』をテーマに会話を構築してください。",
                            "FC07": "FlexSim VRを用いた『バーチャル工場内覧会・VR役員合意形成』のデモを提案し、意思決定の迅速化を支援してください。",
                            "FC08": "Inventor iLogicを活用した『パラメータ駆動型設計の自動化・仕様変更に伴う図面自動更新』の自動化導入ワークショップを提案してください。",
                            # AEC BIM
                            "AE01": "Autodesk Formaを用いた環境シミュレーションを提案。初期段階で騒音や日影の風向問題を秒速で解決する事例が刺さります。",
                            "AE02": "Revitの3D BIM設計への移行支援プログラムをオファー。2Dから3Dへの移行に伴う図面の一貫性確保が最大のセールスポイントです。",
                            "AE03": "Navisworksによる複数領域データの重ね合わせ・自動干渉検出のデモを提案し、現場施工段階の手戻り削減効果を訴求してください。",
                            "AE04": "ACC Docs/Design CollaborateによるISO 19650準拠のクラウドCDEコラボレーションの価値、データ紛失防止を提案してください。",
                            "AE05": "ACC Takeoffを用いた3D/2D統合数量算出による見積の高速化・高精度化のソリューション資料をオファーしてください。",
                            "AE06": "ACC Buildを用いた現場デジタル施工管理（モバイルでの図面閲覧や指摘管理）を提案し、現場監督の直行直帰促進をアピールしてください。",
                            "AE07": "Navisworks 4D工程シミュレーションにより、工期遅延リスクを3Dビジュアルで事前に洗い出す検証デモをオファーしてください。",
                            "AE08": "Autodesk Tandemを用いたデジタルツイン竣工FMデータ構築プログラムを提案。スマートビルディング化への道筋を示してください。",
                            # Civil CIM
                            "CI01": "InfraWorksによる広域CIM地形モデル構築のデモを提案。現況地形と道路設計の3Dビジュアルでの比較検証を訴求してください。",
                            "CI02": "Civil 3DによるCIM道路線形設計・パラメトリック法面展開の自動更新デモを提案し、設計変更への耐性をアピールしてください。",
                            "CI03": "Revit構造物（橋梁等）とCivil 3D道路線形の動的同期による干渉チェック＆座標自動補正デモが極めて有効です。",
                            "CI04": "Civil 3Dサーフェス比較を用いた高精度土量計算と、切盛土バランスの自動最適化ツールをフックに提案してください。",
                            "CI05": "ACC Collaboration for Civil 3Dによる大容量地形点群と線形データの安全なチーム間共有手法をテーマにオファーしてください。",
                            "CI06": "InfraWorksを用いた発注者や住民向け説明用のCIM 3Dビジュアル合意形成パッケージをオファーしてください。",
                            "CI07": "ReCap Proによるドローン点群からの地形面抽出・Civil 3D地形サーフェス化によるi-Construction出来形管理を提案してください。",
                            "CI08": "Civil 3DとTandemを組み合わせたCIM電子納品対応・維持管理データベース移行自動化ワークフローを提案してください。",
                            # MFG PDM
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
                        
                        st.markdown("<h5 style='color:#FFFFFF; font-weight:700; margin-top:15px; margin-bottom:5px;'>💡 AI推奨セールストーク ＆ 提案シナリオ</h5>", unsafe_allow_html=True)
                        st.info(f"👉 **アプローチの切り口 (最大課題: {top_gap['qid']} [{top_gap['phase']}] - Gap: {top_gap['gap']})**\n\n{recommend_text}")
                    else:
                        st.write("回答データに有効なGapが存在しません。全体の成熟度は非常に高い状況です。")
        else:
            if admin_pw != "":
                st.error("パスワードが正しくありません。")
