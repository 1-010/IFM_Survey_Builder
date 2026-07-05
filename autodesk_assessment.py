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

# Page Config
st.set_page_config(page_title="Autodesk IFM Maturity Assessment", layout="wide")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"
IMAGES_DIR = SCRIPT_DIR / "data" / "images"

# Autodesk Brand Global CSS Styling Injection
st.markdown(
    """
    <style>
    /* Autodesk Brand Theme Overrides */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0E0E0E !important; /* Deep Charcoal/Black */
        color: #EAEAEA !important; /* Clay Light Gray */
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Input & Text Colors */
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #EAEAEA !important;
    }
    
    /* Subheaders & secondary labels */
    div[data-testid="stMarkdownContainer"] p {
        color: #EAEAEA;
    }
    
    /* Sharp edges and flat industrial border */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 4px !important;
        border: 1px solid #232323 !important;
        background-color: #161616 !important;
        padding: 18px !important;
        box-shadow: none !important;
    }
    
    /* Hide Streamlit Default branding & menus globally */
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    [class^="viewerBadge"] {display: none !important;}
    [class*="viewerBadge"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden; display: none !important;}
    
    /* Custom Slider Accent */
    div[role="slider"] {
        background-color: #0696D7 !important;
    }
    .stSlider > div {
        color: #0696D7 !important;
    }
    
    /* Primary buttons brand theme */
    div.stButton > button:first-child {
        background-color: #0696D7 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        transition: background-color 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #0080B8 !important;
    }
    
    /* Tab bar color override */
    button[data-baseweb="tab"] {
        color: #8C9BA5 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #0696D7 !important;
        border-bottom-color: #0696D7 !important;
    }
    
    /* Clean up st.table styling to match Clay/Charcoal */
    .stTable table {
        background-color: #1A1A1A !important;
        border: 1px solid #2A2A2A !important;
        color: #EAEAEA !important;
    }
    .stTable th {
        background-color: #232323 !important;
        color: #EAEAEA !important;
        border-bottom: 1px solid #2A2A2A !important;
    }
    .stTable td {
        border-bottom: 1px solid #232323 !important;
        color: #D4D4D4 !important;
    }
    
    /* Make the right radar chart sticky on large screens */
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

def render_question_image(qid):
    img_filename = IMAGE_MAPPING.get(qid)
    if img_filename:
        img_path = IMAGES_DIR / img_filename
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
            return
    # Default fall-back visual (grid outline container via html)
    st.markdown(
        """
        <div style="
            border: 1px dashed #2A2A2A; 
            background: linear-gradient(135deg, #161616 25%, #222222 25%, #222222 50%, #161616 50%, #161616 75%, #222222 75%, #222222 100%);
            background-size: 20px 20px;
            height: 160px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            border-radius: 4px;
            color: #5F6B73;
            font-size: 0.9rem;
            font-family: monospace;
            margin-bottom: 12px;
        ">
        [ AUTODESK // PRECISION_DRAFT_BG ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand Header Layout
col_header_logo, col_header_text = st.columns([1, 6])
with col_header_logo:
    logo_svg_path = IMAGES_DIR / "autodesk_logo_white.svg"
    if logo_svg_path.exists():
        with open(logo_svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        st.markdown(f'<div style="margin-top: 12px; width: 150px;">{svg_content}</div>', unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='color:#0696D7; margin:0;'>AUTODESK</h2>", unsafe_allow_html=True)

with col_header_text:
    st.markdown("<h1 style='margin:0; font-weight:700;'>IFM Maturity Assessment System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0; color:#8C9BA5;'>Integrated Factory Management - Self Diagnostic Platform</p>", unsafe_allow_html=True)

st.markdown("---")

# Hide Navigation Tabs for Clients
is_client_access = "survey_id" in st.query_params

if is_client_access:
    tabs = st.tabs(["📝 アセスメント回答入力"])
    tab_input = tabs[0]
    tab_dashboard = None
    tab_admin = None
else:
    tabs = st.tabs(["📝 アセスメント回答入力", "📊 結果分析ダッシュボード", "🔧 営業管理（カスタム発行）"])
    tab_input = tabs[0]
    tab_dashboard = tabs[1]
    tab_admin = tabs[2]

### 📝 Tab 1: 回答入力フォーム ###
with tab_input:
    if client_name:
        st.markdown(f"### 🤝 **{client_name} 様向け自己アセスメント**")
    
    # 2カラムレイアウト構築 (左: 回答 / 右: リアルタイムレーダーチャート)
    col_left_form, col_right_chart = st.columns([3, 2])
    
    # ユーザー属性入力
    with col_left_form:
        with st.container():
            st.markdown("#### 1. 回答者情報の入力")
            col_attr1, col_attr2 = st.columns(2)
            with col_attr1:
                respondent_name = st.text_input("回答者名 *", placeholder="例: 佐々木 秀成")
                email_input = st.text_input("メールアドレス *", placeholder="例: sasaki@example.com")
            with col_attr2:
                experience_years = st.radio(
                    "勤続年数 *",
                    ["0～2年", "2～5年", "5～10年", "10～15年", "15年以上"],
                    index=None,
                    horizontal=True
                )
                specific_team = st.text_input("部署名・チーム名（任意）", placeholder="例: 第一生産技術部")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 2. 成熟度自己アセスメント")
        st.markdown("現在のレベル（As-Is）と将来目指す目標（To-Be）を回答してください。")
        
        questions_by_dept = q_df.groupby("department")
        
        # ユーザー回答の一時保存辞書
        current_answers = {}
        
        for dept_name, group in questions_by_dept:
            st.markdown(f"### [ {dept_name} 領域 ]")
            
            for _, row in group.iterrows():
                qid = row['question_id']
                with st.container():
                    # 左右配置（左: 設問 & スライダー、右: 製品画像）
                    col_q_text, col_q_img = st.columns([3, 2])
                    
                    with col_q_text:
                        st.markdown(f"##### **{row['phase']}** ({qid})")
                        st.markdown(
                            f"<div style='border-left: 2px solid #0696D7; padding-left: 10px; color:#D4D4D4; font-size:0.95rem; margin-bottom:10px;'>{row['question_text']}</div>", 
                            unsafe_allow_html=True
                        )
                        
                        skip = st.toggle("自身の職務には該当しない (スキップ)", key=f"skip_{qid}")
                    
                    with col_q_img:
                        render_question_image(qid)
                    
                    # レベル定義表の表示 (st.table を使用してクリックやソートを完全無効化)
                    levels_df = pd.DataFrame([
                        {"レベル": "L1", "定義": row['levels']['L1']},
                        {"レベル": "L2", "定義": row['levels']['L2']},
                        {"レベル": "L3", "定義": row['levels']['L3']},
                        {"レベル": "L4", "定義": row['levels']['L4']},
                        {"レベル": "L5", "定義": row['levels']['L5']}
                    ])
                    st.table(levels_df.set_index("レベル"))
                    
                    # スライダー
                    col_slide1, col_slide2 = st.columns(2)
                    with col_slide1:
                        as_is_val = st.slider(
                            f"現状の評価 (As-Is) - {row['phase']}", 
                            1, 5, 2, 
                            key=f"asis_{qid}", 
                            disabled=skip
                        )
                    with col_slide2:
                        to_be_val = st.slider(
                            f"将来の目標 (To-Be) - {row['phase']}", 
                            1, 5, 4, 
                            key=f"tobe_{qid}", 
                            disabled=skip
                        )
                    
                    current_answers[qid] = {
                        "phase": row['phase'],
                        "as_is": None if skip else as_is_val,
                        "to_be": None if skip else to_be_val
                    }
                st.markdown("<hr style='border-color: #232323;'>", unsafe_allow_html=True)
                
        # 送信ボタン
        submit_clicked = st.button("アセスメント結果を送信する", type="primary", use_container_width=True)

    # 右カラム: リアルタイムレーダーチャート表示 (Sticky)
    with col_right_chart:
        st.markdown("#### 🛰️ ライブ成熟度プロファイル")
        st.markdown("スライダーの変更がリアルタイムに反映されます。")
        
        # 動的にプロットデータを集約
        plot_categories = []
        plot_asis = []
        plot_tobe = []
        
        for qid in sorted(current_answers.keys()):
            ans = current_answers[qid]
            plot_categories.append(f"{ans['phase']}\n({qid})")
            plot_asis.append(ans["as_is"] if ans["as_is"] is not None else 0)
            plot_tobe.append(ans["to_be"] if ans["to_be"] is not None else 0)
            
        if plot_categories:
            fig = go.Figure()
            # 閉じたラインにするために最初の要素を末尾に追加
            fig.add_trace(go.Scatterpolar(
                r=plot_asis + [plot_asis[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='現在の評価 (As-Is)',
                line_color='#0696D7',
                fillcolor='rgba(6, 150, 215, 0.2)',
                opacity=0.6
            ))
            fig.add_trace(go.Scatterpolar(
                r=plot_tobe + [plot_tobe[0]],
                theta=plot_categories + [plot_categories[0]],
                fill='toself',
                name='将来の目標 (To-Be)',
                line_color='#8C9BA5',
                fillcolor='rgba(140, 155, 165, 0.1)',
                opacity=0.4
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickvals=[1, 2, 3, 4, 5],
                        gridcolor='#232323',
                        linecolor='#232323',
                        tickfont=dict(color='#8C9BA5')
                    ),
                    angularaxis=dict(
                        gridcolor='#232323',
                        linecolor='#232323',
                        tickfont=dict(color='#EAEAEA', size=10)
                    ),
                    bgcolor='#111111'
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5,
                    font=dict(color='#EAEAEA')
                ),
                paper_bgcolor='#0E0E0E',
                margin=dict(l=40, r=40, t=20, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # リアルタイム簡易フィードバック
            with st.container():
                st.markdown("##### ⚡ リアルタイム進捗")
                answered_count = sum(1 for val in plot_asis if val > 0)
                total_count = len(plot_asis)
                st.progress(answered_count / total_count if total_count > 0 else 0.0)
                st.markdown(f"<small style='color:#8C9BA5;'>回答状況: {answered_count} / {total_count} 問完了</small>", unsafe_allow_html=True)

    # 送信処理のバリデーションと実行
    if submit_clicked:
        if not respondent_name.strip():
            st.error("❌ 回答者名を入力してください。")
        elif not email_input.strip() or not is_valid_email(email_input):
            st.error("❌ 有効なメールアドレスを入力してください。")
        elif not experience_years:
            st.error("❌ 勤続年数を選択してください。")
        else:
            timestamp = datetime.now().isoformat()
            records = []
            answers_list = []
            
            for _, row in q_df.iterrows():
                qid = row['question_id']
                ans_data = current_answers[qid]
                as_is_val = "N/A" if ans_data["as_is"] is None else ans_data["as_is"]
                to_be_val = "N/A" if ans_data["to_be"] is None else ans_data["to_be"]
                
                records.append({
                    "timestamp": timestamp,
                    "respondent": respondent_name.strip(),
                    "email": email_input.strip(),
                    "experience_years": experience_years,
                    "department": row['department'],
                    "team": specific_team.strip(),
                    "question_id": qid,
                    "phase": row['phase'],
                    "as_is": as_is_val,
                    "to_be": to_be_val
                })
                
                answers_list.append({
                    "question_id": qid,
                    "phase": row['phase'],
                    "department": row['department'],
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
                
            with st.spinner("アセスメント結果を送信中..."):
                fs_success = save_response_to_firestore(firestore_doc)
                sheets_success = False
                if fs_success:
                    sheets_success = save_response_to_sheets(records)
                
                if fs_success:
                    st.balloons()
                    st.success("🎉 アセスメント回答が安全に送信されました！ありがとうございます。")
                else:
                    st.error("❌ データベースへの保存に失敗しました。管理者にお問い合わせください。")


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
