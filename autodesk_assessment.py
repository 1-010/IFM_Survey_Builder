import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import re

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
    
    /* Secondary/Navigation buttons when disabled */
    div.stButton > button[disabled] {
        background-color: #1A1A1A !important;
        color: #666666 !important;
        border-color: #333333 !important;
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
    </style>
    """,
    unsafe_allow_html=True
)

# Load Questions
def load_default_questions():
    if not DATA_JSON.exists():
        st.error(f"質問定義ファイルが見つかりません: {DATA_JSON}")
        return []
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]

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
            st.warning(f"⚠️ 指定されたアンケートID `{survey_id}` が登録されていません。デフォルトの設問を表示します。")
    return pd.DataFrame(load_default_questions()), "default", None

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

# Question ID to Autodesk Brand Image Mapping Table
IMAGE_MAPPING = {
    "FI01": "fy27-aec-forma-industry-cloud-imagery.webp",
    "FI02": "brand-image-prototype-1-dark.webp",
    "FI03": "Construction-CCEED-China-0644_with_overlay.webp",
    "FI04": "fy27-water-image-02.webp",
    "PE01": "fy27-dm-digital-factory-campaign-visual-01.webp",
    "PE02": "fy27-dm-fusion-industry-cloud-imagery.webp",
    "PE03": "Tech-Center-Birmingham-industrial-robots-086_with_overlay.webp",
    "PE04": "brand-image-prototype-4-dark.webp"
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
    tabs = st.tabs(["📝 アセスメント回答"])
    tab_input = tabs[0]
    tab_dashboard = None
    tab_admin = None
else:
    tabs = st.tabs(["📝 アセスメント回答", "📊 結果分析", "🔧 営業管理"])
    tab_input = tabs[0]
    tab_dashboard = tabs[1]
    tab_admin = tabs[2]

### 📝 Tab 1: 回答入力フォーム ###
with tab_input:
    col_left_form, col_right_chart = st.columns([11, 9])
    
    # セッション状態管理:
    # current_step == 0: 個人情報入力 ＆ プライバシーポリシー同意画面 (Step 0)
    # current_step >= 1: 設問 1 〜 10 の回答画面
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
        
    num_questions = len(q_df)
    
    with col_left_form:
        if st.session_state.current_step == 0:
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
            # チェックを入れたら「画面左へスッと隠れる（非表示化）」されてレイアウトを圧迫しない設計！
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
            
            # アセスメント開始ボタン (必須事項が埋まっていない、または同意がない場合は押せない)
            # 送信や開始などの「決定的なアクション」のみに Hello Yellow (Primary) を適用
            if st.button("自己アセスメントを開始する ➔", type="primary", disabled=not inputs_valid, use_container_width=True):
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
            st.markdown(f"<h3 style='margin-top:2px; font-size:1.6rem; font-weight:700;'>{row['phase']}</h3>", unsafe_allow_html=True)
            
            # 設問カード
            st.markdown(
                f"<div style='background-color:#121212; padding:20px; border-left:4px solid #FFFF00; margin-bottom:20px; font-size:1.05rem; line-height:1.6; color:#FFFFFF;'>"
                f"{row['question_text']}</div>", 
                unsafe_allow_html=True
            )
            
            # 該当しない場合のスキップ
            skip_key = f"skip_{qid}"
            if skip_key not in st.session_state:
                st.session_state[skip_key] = False
            skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key)
            
            # スライダー
            asis_key = f"asis_{qid}"
            tobe_key = f"tobe_{qid}"
            if asis_key not in st.session_state:
                st.session_state[asis_key] = 2
            if tobe_key not in st.session_state:
                st.session_state[tobe_key] = 4
                
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                as_is_val = st.slider(
                    "現状の成熟度評価 (As-Is)", 
                    1, 5, 
                    key=asis_key, 
                    disabled=skip
                )
            with col_s2:
                to_be_val = st.slider(
                    "将来の目標成熟度 (To-Be)", 
                    1, 5, 
                    key=tobe_key, 
                    disabled=skip
                )
                
            # --- 【改善】評価定義カードリスト (L1〜L5 の全体像を表示 ＋ 選択された値を動的ハイライト) ---
            if not skip:
                st.markdown("<div style='margin-top:15px; margin-bottom:5px;'><b style='font-size:0.95rem; color:#D5D5CB;'>成熟度レベル定義 (L1〜L5)</b></div>", unsafe_allow_html=True)
                
                # HTMLリストの構築
                levels_html = "<div style='display: flex; flex-direction: column; gap: 8px; margin-top: 5px;'>"
                for lvl in ["L1", "L2", "L3", "L4", "L5"]:
                    lvl_num = int(lvl[1])
                    is_asis = (as_is_val == lvl_num)
                    is_tobe = (to_be_val == lvl_num)
                    
                    # カラーマッピング (一致状態によりハイライト枠とバッジを設定)
                    border_color = "rgba(102, 102, 102, 0.25)" # Slate default
                    bg_color = "transparent"
                    badge_html = ""
                    
                    if is_asis and is_tobe:
                        border_color = "#FFFF00" # Hello Yellow
                        bg_color = "rgba(255, 255, 0, 0.05)"
                        badge_html = "<span style='background-color:#FFFF00; color:#000000; font-size:0.72rem; font-weight:700; padding:2px 6px; border-radius:2px; margin-right:8px;'>As-Is & To-Be</span>"
                    elif is_asis:
                        border_color = "#1D91D0" # Twilight Blue
                        bg_color = "rgba(29, 145, 208, 0.08)"
                        badge_html = "<span style='background-color:#1D91D0; color:#FFFFFF; font-size:0.72rem; font-weight:700; padding:2px 6px; border-radius:2px; margin-right:8px;'>As-Is</span>"
                    elif is_tobe:
                        border_color = "#2AD0A9" # Morning Green
                        bg_color = "rgba(42, 208, 169, 0.04)"
                        badge_html = "<span style='background-color:#2AD0A9; color:#000000; font-size:0.72rem; font-weight:700; padding:2px 6px; border-radius:2px; margin-right:8px;'>To-Be</span>"
                        
                    levels_html += f'<div style="border-left: 3px solid {border_color}; background-color: {bg_color}; padding: 10px 14px; border-top: 1px solid rgba(102,102,102,0.15); border-right: 1px solid rgba(102,102,102,0.15); border-bottom: 1px solid rgba(102,102,102,0.15); transition: all 0.2s ease;"><div style="display: flex; align-items: center; margin-bottom: 3px;">{badge_html}<b style="font-size: 0.85rem; color: #D5D5CB;">Level {lvl_num}</b></div><div style="font-size: 0.88rem; color: #FFFFFF; line-height: 1.45;">{row["levels"][lvl]}</div></div>'
                levels_html += "</div>"
                st.markdown(levels_html, unsafe_allow_html=True)
                
            st.markdown("<br><hr style='border-color:#666666; margin:10px 0;'>", unsafe_allow_html=True)
            
            # 必要に応じて引っ張り出せるアコーディオン (プロファイル ＆ 同意書の再確認/編集)
            with st.expander("👤 登録プロファイル・個人情報同意事項の確認と変更"):
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
                
                # アコーディオン内にもポリシー詳細プレースホルダーを隠して格納
                if not edit_agree:
                    st.markdown("<div style='margin-top:5px;'></div>", unsafe_allow_html=True)
                    st.info("[法務確認済みの個人情報保護方針に関する詳細な同意文面がここに入ります。]")
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # ナビゲーションボタン群 (type="secondary" にして白枠黒背景に変更、視認性 100% 確保)
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            with col_btn1:
                # 前のステップへ戻る (Step 1のときは Step 0 のプロファイル画面に戻る)
                if st.button("⬅️ 前の画面", type="secondary", use_container_width=True):
                    st.session_state.current_step -= 1
                    st.rerun()
                    
            with col_btn2:
                next_disabled = st.session_state.current_step == num_questions
                if st.button("次の設問 ➡️", type="secondary", disabled=next_disabled, use_container_width=True):
                    st.session_state.current_step += 1
                    st.rerun()
                    
            with col_btn3:
                # 最終送信条件: 同意チェックがONであり、かつ必須項目がすべて正しく入力されていること
                is_last_step = st.session_state.current_step == num_questions
                profile_valid = (
                    st.session_state.get("res_name", "").strip() != "" and
                    st.session_state.get("res_email", "").strip() != "" and
                    is_valid_email(st.session_state.get("res_email", "")) and
                    st.session_state.get("res_exp") is not None and
                    st.session_state.get("agree_privacy", False)
                )
                submit_disabled = not (is_last_step and profile_valid)
                submit_clicked = st.button("🏁 アセスメント結果を最終送信する", type="primary", disabled=submit_disabled, use_container_width=True)
                
                # 同意が外れている場合に警告メッセージを表示する親切設計
                if is_last_step and not st.session_state.get("agree_privacy", False):
                    st.warning("⚠️ 送信するには個人情報の取り扱いへの同意が必要です（『登録プロファイル・個人情報同意事項の確認と変更』から同意をONにできます）。")

    with col_right_chart:
        # Step 0 のときは共通のアセット画像を表示、回答中は設問に連動した画像を表示
        if st.session_state.current_step == 0:
            render_hero_image("PE01") # デフォルトで美麗なデジタルファクトリー画像
        else:
            render_hero_image(qid)
            
        st.markdown("<h4 style='margin-bottom:5px; font-weight:600; font-size:1.1rem; color:#D5D5CB;'>🛰️ ライブ成熟度プロファイル</h4>", unsafe_allow_html=True)
        
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
            # Functional Colors: Twilight Blue (#1D91D0) for As-Is, Morning Green (#2AD0A9) for To-Be
            # Ultra-clean holographic stylings (opacity and thin line)
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
            
            # Subtle Progress indicators
            st.progress(answered_count / num_questions)
            st.markdown(f"<div style='text-align:right; font-size:0.75rem; color:#666666; margin-top:2px;'>回答進捗: {answered_count} / {num_questions} 問</div>", unsafe_allow_html=True)

    # 送信処理のバリデーションと実行
    if st.session_state.current_step == num_questions and submit_clicked:
        res_name = st.session_state.get("res_name", "").strip()
        res_email = st.session_state.get("res_email", "").strip()
        res_exp = st.session_state.get("res_exp")
        res_team = st.session_state.get("res_team", "").strip()
        agree_privacy = st.session_state.get("agree_privacy", False)
        
        if not res_name:
            st.error("❌ 回答者名を入力してください。")
        elif not res_email or not is_valid_email(res_email):
            st.error("❌ 有効なメールアドレスを入力してください。")
        elif not res_exp:
            st.error("❌ 勤続年数を選択してください。")
        elif not agree_privacy:
            st.error("❌ 個人情報の取り扱いへの同意が必要です。")
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
                    st.success("🎉 自己アセスメント回答が安全に送信されました！")
                else:
                    st.error("❌ 送信に失敗しました。管理者にお問い合わせください。")


### 📊 Tab 2: 結果分析ダッシュボード ###
if tab_dashboard:
    with tab_dashboard:
        st.header("📊 成熟度アセスメントの分析・比較")
        dash_pw = st.text_input("結果分析ダッシュボード閲覧用パスワード", type="password", key="dash_pw_input")
        
        if dash_pw == "ifm-sales":
            st.success("認証されました。")
            resp_df = load_all_responses_merged()
            
            if resp_df.empty:
                st.warning("現在、回答データが存在しません。")
            else:
                st.subheader("📊 絞り込みとグループ比較")
                compare_mode = st.checkbox("👥 2つのグループを比較する（比較モード）", value=False, key="dash_compare")
                
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
                        st.markdown("#### 🔵 グループA の条件")
                        survey_a = st.selectbox("アンケートID (グループA)", ["すべて"] + unique_surveys, key="survey_a")
                        domain_a = st.selectbox("ドメイン (グループA)", ["すべて"] + unique_domains, key="domain_a")
                        exp_a = st.selectbox("勤続年数 (グループA)", unique_years, key="exp_a")
                        team_a = st.text_input("部署名（部分一致・グループA）", key="team_a", placeholder="例: 技術部")
                        cat_a = st.radio("表示カテゴリ (グループA)", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="cat_a", horizontal=True)
                        
                    with col_filter_b:
                        st.markdown("#### 🟠 グループB の条件")
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

                # ... (ダッシュボード比較チャートプロット - 色指定修正)
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
        else:
            if dash_pw != "":
                st.error("パスワードが正しくありません。")


### 🔧 Tab 3: 営業管理（カスタム発行） ###
if tab_admin:
    with tab_admin:
        st.header("🔧 営業担当用 カスタムアンケート発行管理")
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
                
            if new_survey_id.strip():
                if not re.match(r"^[a-zA-Z0-9\-_]+$", new_survey_id.strip()):
                    st.error("⚠️ アンケートIDは英数字、ハイフン(-), アンダースコア(_)のみ使用可能です。")
                else:
                    if st.button("既存のカスタム設問を読み込む (IDが存在する場合)"):
                        existing = get_custom_survey(new_survey_id.strip())
                        if existing:
                            st.session_state[f"loaded_survey_{new_survey_id}"] = existing
                            st.success(f"ID: `{new_survey_id}` の既存設定を読み込みました！")
            
            st.subheader("2. 設問テキストのカスタマイズ")
            default_qs = load_default_questions()
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
                    st.error("❌ 必須入力項目をすべて埋めてください。")
                else:
                    sid = new_survey_id.strip()
                    success = save_custom_survey(
                        survey_id=sid,
                        client_name=new_client_name.strip(),
                        creator=new_creator.strip(),
                        questions_list=custom_questions_data
                    )
                    if success:
                        st.success(f"🎉 カスタムアンケート `{sid}` が保存・発行されました！")
                        prod_url = f"https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?survey_id={sid}&brand=autodesk"
                        local_url = f"http://localhost:8501/?survey_id={sid}&brand=autodesk"
                        
                        st.info("📋 **顧客配信用リンク (本番環境):**")
                        st.code(prod_url, language=None)
                        st.info("💻 **テスト用リンク (ローカル環境):**")
                        st.code(local_url, language=None)
        else:
            if admin_pw != "":
                st.error("パスワードが正しくありません。")
