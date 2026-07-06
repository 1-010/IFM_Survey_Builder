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
            return pd.DataFrame(custom_survey["questions"]), survey_id, custom_survey.get("client_name")
            
    all_qs = load_all_questions_json()
    return pd.DataFrame(all_qs.get("questions", [])), "default", None

q_df, active_survey_id, client_name = get_default_questions()

# Autodesk Brand Official Color & Layout Guidelines Integration
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
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
    
    @media (min-width: 992px) {
        div[data-testid="stColumn"]:nth-child(2) {
            position: -webkit-sticky;
            position: sticky;
            top: 20px;
            z-index: 999;
        }
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
    
    has_noto = os.path.exists(font_path)
    if has_noto:
        pdf.add_font("NotoSansJP", "", font_path)
        pdf.set_font("NotoSansJP", size=10)
    else:
        pdf.set_font("Helvetica", size=10)
        
    # Title Header (Black Autodesk Banner)
    pdf.set_fill_color(0, 0, 0)
    pdf.rect(0, 0, 210, 42, "F")
    
    pdf.set_text_color(255, 255, 255)
    if has_noto:
        pdf.set_font("NotoSansJP", size=15)
        pdf.text(15, 20, "AUTODESK SOLUTION ASSESSMENT REPORT")
        pdf.set_font("NotoSansJP", size=10)
        pdf.text(15, 30, f"{survey_title} - 診断結果レポート")
    else:
        pdf.set_font("Helvetica", size=14)
        pdf.text(15, 20, "AUTODESK SOLUTION ASSESSMENT REPORT")
        pdf.set_font("Helvetica", size=10)
        pdf.text(15, 30, "Assessment Result Report")
    
    # Client Info Block
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 245, 242)
    pdf.rect(15, 50, 180, 30, "F")
    
    if has_noto:
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
    else:
        pdf.set_font("Helvetica", size=9)
        pdf.text(20, 57, f"Respondent: {res_name}")
        pdf.text(20, 64, f"Department/Team: {res_team if res_team else 'N/A'}")
        pdf.text(20, 71, f"Email: {res_email}  (Experience: {res_exp})")
        
        pdf.set_font("Helvetica", size=11)
        pdf.text(15, 95, "Assessment Gap Analysis")
        
        pdf.line(15, 99, 195, 99)
        pdf.set_font("Helvetica", size=8.5)
        pdf.text(17, 104, "QID")
        pdf.text(32, 104, "Category / Phase")
        pdf.text(125, 104, "As-Is")
        pdf.text(150, 104, "To-Be")
        pdf.text(175, 104, "Gap")
        pdf.line(15, 107, 195, 107)
    
    y = 113
    for a in answers_list:
        pdf.text(17, y, str(a["question_id"]))
        if has_noto:
            pdf.text(32, y, f"{a['phase']} ({a['department']})")
        else:
            pdf.text(32, y, f"Phase {a['question_id']} ({a['department']})")
        pdf.text(133, y, str(a["as_is"]))
        pdf.text(158, y, str(a["to_be"]))
        
        gap_val = 0
        if a["as_is"] != "N/A" and a["to_be"] != "N/A":
            gap_val = int(a["to_be"]) - int(a["as_is"])
            
        pdf.text(180, y, str(gap_val) if a["as_is"] != "N/A" else "N/A")
        y += 7
        
    pdf.line(15, y-2, 195, y-2)
    
    # Summary of gaps
    pdf.ln(y - 95 + 10)
    if has_noto:
        pdf.set_font("NotoSansJP", size=11)
        pdf.cell(0, 10, "推奨ソリューションのご案内", ln=True)
        pdf.set_font("NotoSansJP", size=8.5)
        pdf.multi_cell(180, 5, "アセスメントは正常に送信完了いたしました。各設問の乖離値（Gap）の分析結果は上記テーブルの通りです。詳細な推奨ソリューションおよび個別提案書につきましては、担当営業より別途ご案内させていただきます。")
    else:
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 10, "Recommended Solutions Info", ln=True)
        pdf.set_font("Helvetica", size=8.5)
        pdf.multi_cell(180, 5, "Your assessment answers have been safely submitted. The gap analysis results are shown in the table above. Detailed proposal materials and custom recommendation scenarios will be delivered to you shortly by our sales team.")
        
    return pdf.output()

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

# Image Mapping for IFM
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
    st.markdown(
        """
        <div style="border: 1px solid #666666; background-color: #121212; height: 180px; display: flex; align-items: center; justify-content: center; border-radius: 0px; color: #D5D5CB; font-size: 0.9rem; font-family: monospace; margin-bottom: 20px;">
        [ AUTODESK // PRECISION_DESIGN_SYSTEM ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand Header Layout
stacked_logo_svg = '<svg width="220" height="85" viewBox="0 0 220 85" fill="none" xmlns="http://www.w3.org/2000/svg"><g transform="scale(2.4) translate(30, 1)"><path d="M0.538536 22.7316L19.9163 10.678H29.9686C30.2781 10.678 30.5561 10.9259 30.5561 11.2662C30.5561 11.5442 30.4321 11.6681 30.2781 11.7605L20.7598 17.4657C20.1416 17.8368 19.9252 18.579 19.9252 19.1356L19.9155 22.7316H32.0097V1.83296C32.0097 1.4303 31.7002 1.09078 31.2367 1.09078H19.6999L0.369995 13.091V22.7316L0.538536 22.7316Z" fill="white"/></g><text x="110" y="74" fill="white" font-family="\'Inter\', sans-serif" font-size="18" font-weight="900" letter-spacing="4.5" text-anchor="middle">AUTODESK</text></svg>'
header_html = f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; margin-bottom: 10px; gap: 20px;"><div style="width: 220px; display: flex; align-items: center;">{stacked_logo_svg}</div><div style="text-align: right; min-width: 250px;"><div style="font-size: 0.75rem; color: #666666; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Maturity Evaluation Platform</div><div style="font-size: 1.7rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.03em;">設備管理成熟度アセスメント</div></div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Client navigation view switcher
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

### 📝 Tab 1: 回答入力フォーム ###
with tab_input:
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
            
            # Gap分析
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
                        "gap": to_be - as_is,
                        "to_be": to_be
                    })
            
            gaps_sorted = sorted(gaps, key=lambda x: (x["gap"], x["to_be"]), reverse=True)
            
            # PDF診断書ダウンロードボタンの実装（堅牢な例外保護付き）
            pdf_data = None
            try:
                with st.spinner("PDFレポートを準備中..."):
                    pdf_data = generate_pdf_report_bytes(
                        res_name=st.session_state.get("res_name", "テスト回答者"),
                        res_email=st.session_state.get("res_email", "info@autodesk.com"),
                        res_team=st.session_state.get("res_team", "未設定"),
                        res_exp=st.session_state.get("res_exp", "未設定"),
                        answers_list=answers_list_for_pdf,
                        gaps_sorted=gaps_sorted,
                        proposals_dict={},
                        survey_title="設備管理成熟度アセスメント"
                    )
            except Exception as e:
                st.warning(f"PDF生成中にエラーが発生しました（安全のため標準レイアウトへフォールバックします）: {e}")
            
            if pdf_data:
                st.download_button(
                    label="診断結果レポート (PDF) をダウンロード",
                    data=pdf_data,
                    file_name=f"Autodesk_IFM_Report_{active_survey_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
            if st.button("アセスメントを再回答する", type="secondary", use_container_width=True):
                st.session_state.is_submitted = False
                st.session_state.current_step = 0
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
                st.markdown("<b style='font-size:0.85rem; color:#8C9BA5;'>【確認用：個人情報保護に関する同意文面（法務確認中プレースホルダー）】</b>", unsafe_allow_html=True)
                privacy_policy_text = "[法務確認済みの個人情報保護方針に関する詳細な同意文面がここに入ります。チェックボックスに同意を入れると、この文面エリアは自動的に非表示になり、アセスメント開始ボタンに素早くアクセスできるようになります。]"
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
            # 1から current_step までの設問を下方向に追加しながら描画する
            for step_idx in range(1, st.session_state.current_step + 1):
                q_idx = step_idx - 1
                row = q_df.iloc[q_idx]
                qid = row['question_id']
                
                st.markdown(
                    f"<div style='background-color:#121212; padding:15px; border-left:4px solid #FFFF00; margin-top:20px; border-top:1px solid #333333; border-right:1px solid #333333; border-bottom:1px solid #333333;'>"
                    f"<div style='font-size:0.8rem; color:#FFFF00; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;'>"
                    f"{row['department']} 領域  ·  設問 {step_idx} / {num_questions}</div>"
                    f"<h4 style='margin-top:4px; margin-bottom:6px; font-size:1.2rem; font-weight:700; color:#FFFFFF;'>{row['question_id']} ({row['phase']})</h4>"
                    f"<div style='font-size:0.92rem; line-height:1.45; color:#FFFFFF;'>{row['question_text']}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                # スキップトグル (イエローを使用せず視認性の高いグリーンアクティブスタイル)
                skip_key = f"skip_{qid}"
                if skip_key not in st.session_state:
                    st.session_state[skip_key] = False
                skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key)
                
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
                    
                    # カラー同期されたスライダーの描画
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
                
                # 組織内認識ギャップ分析セクション
                st.markdown("<hr style='border-color:#333333; margin:25px 0;'>", unsafe_allow_html=True)
                st.subheader("組織内・認識の歪み（ギャップ）分析")
                
                if len(df_a['email'].unique()) < 2:
                    st.info("※ このアンケートIDに対する複数回答データが不足しています。組織内ギャップ分析を行うには2名以上の回答が必要です。")
                else:
                    st.markdown("<p style='font-size:0.92rem; color:#D5D5CB; margin-bottom:15px;'>同じアンケートIDに対する複数名の回答から、現場層（勤続年数5年未満）と意思決定層（勤続年数10年以上）の間の【認識ギャップ】を抽出します。</p>", unsafe_allow_html=True)
                    
                    genba_df = df_a[df_a['experience_years'].isin(["0～2年", "2～5年"])]
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
                                st.write("現場層と意思決定層의 認識ギャップはありません。")
                        else:
                            st.write("データが不足しています。")
        else:
            if dash_pw != "":
                st.error("パスワードが正しくありません。")

### 🔧 Tab 3: 営業管理 ###
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
                        
                        # スマホですぐスキャンしてアクセスできるようにQRコードを表示
                        qr_prod_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={prod_url}"
                        st.image(qr_prod_url, caption="スマホ用顧客配信用QRコード (本番環境)", width=180)
                        
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
                            "FC03": "Factory Design Utilities (FDU) を紹介。『AutoCADとInventor of 2D/3D双方向同期による干渉チェック』が最も響くアプローチです。",
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
                        
                        st.markdown("<h5 style='color:#FFFFFF; font-weight:700; margin-top:15px; margin-bottom:5px;'>💡 AI推奨セールストーク ＆ 提案シナリオ</h5>", unsafe_allow_html=True)
                        st.info(f"👉 **アプローチの切り口 (最大課題: {top_gap['qid']} [{top_gap['phase']}] - Gap: {top_gap['gap']})**\n\n{recommend_text}")
                    else:
                        st.write("回答データに有効なGapが存在しません。全体の成熟度は非常に高い状況です。")
        else:
            if admin_pw != "":
                st.error("パスワードが正しくありません。")
