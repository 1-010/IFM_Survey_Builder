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

# Autodesk Brand Global CSS Styling Injection for Museum-like Minimalism
st.markdown(
    """
    <style>
    /* Autodesk Brand Theme Overrides */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0B0B0B !important; /* Rich Dark Charcoal */
        color: #E6E6E6 !important; /* Autodesk Clay Light Gray */
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Input & Text Colors */
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #E6E6E6 !important;
    }
    
    /* Clean headings */
    h1 {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em !important;
        margin-bottom: 0.2rem !important;
    }
    
    /* Layout card styling - Minimal borders, high whitespace */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 0px !important; /* Flat industrial edges */
        border: none !important;
        border-left: 1px solid #1F1F1F !important;
        background-color: transparent !important;
        padding: 0px 24px !important;
        box-shadow: none !important;
    }
    
    /* Left column card formatting */
    .question-card {
        background-color: #121212;
        border: 1px solid #1F1F1F;
        padding: 24px;
        margin-bottom: 20px;
    }
    
    /* Dynamic Level Definition Cards */
    .level-desc-box {
        background-color: #161616;
        border-left: 3px solid #0696D7;
        padding: 12px 16px;
        margin-top: 10px;
        font-size: 0.92rem;
        color: #C0C0C0;
    }
    .level-desc-box-target {
        background-color: #161616;
        border-left: 3px solid #8C9BA5;
        padding: 12px 16px;
        margin-top: 10px;
        font-size: 0.92rem;
        color: #C0C0C0;
    }
    
    /* Hide Streamlit Default branding & menus globally */
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    [class^="viewerBadge"] {display: none !important;}
    [class*="viewerBadge"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden; display: none !important;}
    
    /* Custom Slider Accent (Autodesk Cyan) */
    div[role="slider"] {
        background-color: #0696D7 !important;
    }
    .stSlider > div {
        color: #0696D7 !important;
    }
    
    /* Buttons styling - Flat & Minimalist */
    div.stButton > button:first-child {
        background-color: #0696D7 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 2px !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.05em !important;
        padding: 8px 20px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #0080B8 !important;
    }
    
    /* Secondary/Navigation buttons */
    div.stButton > button[disabled] {
        background-color: #1A1A1A !important;
        color: #555555 !important;
    }
    
    /* Tab bar color override */
    button[data-baseweb="tab"] {
        color: #8C9BA5 !important;
        font-size: 0.95rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #0696D7 !important;
        border-bottom-color: #0696D7 !important;
    }
    
    /* Navigation Progress Bar styling */
    .stProgress > div > div > div {
        background-color: #0696D7 !important;
    }
    
    /* Make the right visual & chart sticky on large screens */
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
    survey_id = st.query_params.get("survey_id")
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
    "FI01": "fy27-aec-forma-industry-cloud-imagery.webp", # Forma
    "FI02": "brand-image-prototype-1-dark.webp",
    "FI03": "Construction-CCEED-China-0644_with_overlay.webp",
    "FI04": "fy27-water-image-02.webp",
    "PE01": "fy27-dm-digital-factory-campaign-visual-01.webp", # Factory Design
    "PE02": "fy27-dm-fusion-industry-cloud-imagery.webp", # Fusion/Inventor
    "PE03": "Tech-Center-Birmingham-industrial-robots-086_with_overlay.webp", # Robots
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
            border: 1px dashed #2A2A2A; 
            background: linear-gradient(135deg, #161616 25%, #222222 25%, #222222 50%, #161616 50%, #161616 75%, #222222 75%, #222222 100%);
            background-size: 20px 20px;
            height: 220px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            border-radius: 2px;
            color: #5F6B73;
            font-size: 0.9rem;
            font-family: monospace;
            margin-bottom: 20px;
        ">
        [ AUTODESK // PRECISION_DRAFT_HERO ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand Header Layout
col_header_logo, col_header_text = st.columns([1, 8])
with col_header_logo:
    logo_svg_path = IMAGES_DIR / "autodesk_logo_white.svg"
    if logo_svg_path.exists():
        with open(logo_svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        st.markdown(f'<div style="margin-top: 14px; width: 140px;">{svg_content}</div>', unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='color:#0696D7; margin:0;'>AUTODESK</h2>", unsafe_allow_html=True)

with col_header_text:
    st.markdown("<h1 style='margin:0;'>IFM Maturity Assessment</h1>", unsafe_allow_html=True)

st.markdown("<hr style='border-color:#1F1F1F; margin-top:10px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Hide Navigation Tabs for Clients
is_client_access = "survey_id" in st.query_params

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
    # 2カラムレイアウト構築 (左: 設問コントロール / 右: ヒーロービジュアル ＆ ライブレーダーチャート)
    col_left_form, col_right_chart = st.columns([11, 9])
    
    # セッションによるステップ状態（1問1答）の管理
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
        
    num_questions = len(q_df)
    
    # ユーザー属性入力（最初のステップの前に表示するか、ステップ0に組み込む）
    with col_left_form:
        # 回答者属性情報の入力コンテナ（未完了時は常に上部にコンパクトに表示）
        st.markdown("<h4 style='margin-bottom:10px; font-weight:600; font-size:1.1rem; color:#8C9BA5;'>1. 回答者プロファイル</h4>", unsafe_allow_html=True)
        col_attr1, col_attr2 = st.columns(2)
        with col_attr1:
            respondent_name = st.text_input("回答者名 *", placeholder="氏名をご記入ください", value=st.session_state.get("res_name", ""))
            st.session_state["res_name"] = respondent_name
            email_input = st.text_input("メールアドレス *", placeholder="sasaki@autodesk.com", value=st.session_state.get("res_email", ""))
            st.session_state["res_email"] = email_input
        with col_attr2:
            experience_years = st.radio(
                "勤続年数 *",
                ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"],
                index=["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"].index(st.session_state.get("res_exp")) if st.session_state.get("res_exp") in ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"] else None,
                horizontal=True,
                key="res_exp_radio"
            )
            st.session_state["res_exp"] = experience_years
            specific_team = st.text_input("部署名・チーム名 (任意)", placeholder="例: 生産技術部", value=st.session_state.get("res_team", ""))
            st.session_state["res_team"] = specific_team
        
        st.markdown("<hr style='border-color:#1F1F1F; margin:20px 0;'>", unsafe_allow_html=True)
        
        # 設問エリア
        st.markdown("<h4 style='margin-bottom:10px; font-weight:600; font-size:1.1rem; color:#8C9BA5;'>2. 自己成熟度評価</h4>", unsafe_allow_html=True)
        
        # 現在の質問オブジェクトを取得
        current_idx = st.session_state.current_step
        row = q_df.iloc[current_idx]
        qid = row['question_id']
        
        # ステップナビゲーション表示
        st.markdown(
            f"<div style='font-size:0.85rem; color:#0696D7; font-weight:600; text-transform:uppercase; letter-spacing:0.08em;'>"
            f"{row['department']} 領域  ·  STEP {current_idx + 1} / {num_questions}</div>",
            unsafe_allow_html=True
        )
        st.markdown(f"<h3 style='margin-top:2px; font-size:1.6rem; font-weight:600;'>{row['phase']}</h3>", unsafe_allow_html=True)
        
        # 質問文のカード表示
        st.markdown(
            f"<div style='background-color:#141414; padding:20px; border-left:3px solid #0696D7; margin-bottom:20px; font-size:1.05rem; line-height:1.6; color:#D4D4D4;'>"
            f"{row['question_text']}</div>", 
            unsafe_allow_html=True
        )
        
        # スキップトグル
        skip_key = f"skip_{qid}"
        if skip_key not in st.session_state:
            st.session_state[skip_key] = False
        skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key)
        
        # スライダー配置
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
            
        # 動的なレベル定義のテキストカード表示 (st.table を排し、選択された数値の定義のみをクリーンに表示！)
        if not skip:
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            
            # As-Is の定義テキスト
            asis_text = row['levels'][f"L{as_is_val}"]
            st.markdown(
                f"<div class='level-desc-box'>"
                f"<b>現在の評価 (Level {as_is_val}) の定義:</b><br>{asis_text}"
                f"</div>",
                unsafe_allow_html=True
            )
            
            # To-Be の定義テキスト
            tobe_text = row['levels'][f"L{to_be_val}"]
            st.markdown(
                f"<div class='level-desc-box-target'>"
                f"<b>目標の評価 (Level {to_be_val}) の定義:</b><br>{tobe_text}"
                f"</div>",
                unsafe_allow_html=True
            )
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ステップ送りボタンのレイアウト
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            prev_disabled = st.session_state.current_step == 0
            if st.button("⬅️ 前の設問", disabled=prev_disabled, use_container_width=True):
                st.session_state.current_step -= 1
                st.rerun()
                
        with col_btn2:
            next_disabled = st.session_state.current_step == num_questions - 1
            if st.button("次の設問 ➡️", disabled=next_disabled, use_container_width=True):
                st.session_state.current_step += 1
                st.rerun()
                
        with col_btn3:
            # 全問回答完了時の送信アクション
            is_last_step = st.session_state.current_step == num_questions - 1
            submit_disabled = not is_last_step
            submit_clicked = st.button("🏁 アセスメント結果を最終送信する", type="primary", disabled=submit_disabled, use_container_width=True)

    # 右カラム: ヒーローイメージ（現在ステップ同期） ＆ リアルタイムレーダーチャート
    with col_right_chart:
        # 現在アクティブな設問のヒーロービジュアルを上部にクリーンに固定表示
        render_hero_image(qid)
        
        st.markdown("<h4 style='margin-bottom:5px; font-weight:600; font-size:1.1rem; color:#8C9BA5;'>🛰️ ライブ成熟度プロファイル</h4>", unsafe_allow_html=True)
        
        # リアルタイムで現在までの回答状態をマージしてプロット
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
            # 閉じたラインにするために最初の要素を末尾に追加
            fig.add_trace(go.Scatterpolar(
                r=plot_asis + [plot_asis[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='現在の評価 (As-Is)',
                line_color='#0696D7',
                fillcolor='rgba(6, 150, 215, 0.15)',
                line=dict(width=2),
                opacity=0.7
            ))
            fig.add_trace(go.Scatterpolar(
                r=plot_tobe + [plot_tobe[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='将来の目標 (To-Be)',
                line_color='#8C9BA5',
                fillcolor='rgba(140, 155, 165, 0.08)',
                line=dict(width=1.5, dash='dash'),
                opacity=0.5
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickvals=[1, 2, 3, 4, 5],
                        gridcolor='#1C1C1C',
                        linecolor='#1C1C1C',
                        tickfont=dict(color='#8C9BA5', size=9)
                    ),
                    angularaxis=dict(
                        gridcolor='#1C1C1C',
                        linecolor='#1C1C1C',
                        tickfont=dict(color='#E6E6E6', size=9)
                    ),
                    bgcolor='#0E0E0E'
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(color='#E6E6E6', size=10)
                ),
                paper_bgcolor='#0B0B0B',
                margin=dict(l=50, r=50, t=10, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # リアルタイム簡易進捗インジケーター（1問1答形式での進捗）
            answered_count = sum(1 for idx, r in q_df.iterrows() if st.session_state.get(f"asis_{r['question_id']}") is not None or st.session_state.get(f"skip_{r['question_id']}"))
            st.progress(answered_count / num_questions)
            st.markdown(f"<div style='text-align:right; font-size:0.75rem; color:#8C9BA5; margin-top:2px;'>回答進捗: {answered_count} / {num_questions} 問</div>", unsafe_allow_html=True)

    # 送信処理のバリデーションと実行
    if submit_clicked:
        if not respondent_name.strip():
            st.error("❌ 回回答者名を入力してください。")
        elif not email_input.strip() or not is_valid_email(email_input):
            st.error("❌ 有効なメールアドレスを入力してください。")
        elif not experience_years:
            st.error("❌ 勤続年数を選択してください。")
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
                    "respondent": respondent_name.strip(),
                    "email": email_input.strip(),
                    "experience_years": experience_years,
                    "department": r['department'],
                    "team": specific_team.strip(),
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
                "respondent": respondent_name.strip(),
                "email": email_input.strip(),
                "experience_years": experience_years,
                "team": specific_team.strip(),
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
                        line_color='#0696D7',
                        fillcolor='rgba(6, 150, 215, 0.2)'
                    ))
                    fig.add_trace(go.Scatterpolar(
                        r=agg_a['to_be'].tolist() + [agg_a['to_be'].tolist()[0]],
                        theta=theta_labels + [theta_labels[0]],
                        fill='toself',
                        name='グループA: 将来の目標',
                        line_color='#8C9BA5',
                        fillcolor='rgba(140, 155, 165, 0.1)'
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
                            line_color='#E58C00',
                            fillcolor='rgba(229, 140, 0, 0.2)'
                        ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 5], gridcolor='#232323'),
                        angularaxis=dict(gridcolor='#232323', tickfont=dict(color='#EAEAEA')),
                        bgcolor='#111111'
                    ),
                    paper_bgcolor='#0E0E0E',
                    font=dict(color='#EAEAEA')
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
                        prod_url = f"https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/autodesk_assessment?survey_id={sid}"
                        local_url = f"http://localhost:8501/autodesk_assessment?survey_id={sid}"
                        
                        st.info("📋 **顧客配信用リンク (本番環境):**")
                        st.code(prod_url, language=None)
                        st.info("💻 **テスト用リンク (ローカル環境):**")
                        st.code(local_url, language=None)
        else:
            if admin_pw != "":
                st.error("パスワードが正しくありません。")
