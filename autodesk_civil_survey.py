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
    save_response_to_firestore
)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"
IMAGES_DIR = SCRIPT_DIR / "data" / "images"

# Autodesk Brand Official Color & Layout Guidelines
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 0px !important;
        border: none !important;
        border-left: 1px solid #666666 !important;
        background-color: transparent !important;
        padding: 0px 24px !important;
        box-shadow: none !important;
    }
    
    .stImage img {
        border-radius: 0px !important;
        border: 1px solid #666666 !important;
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
        font-size: 0.92rem !important;
        letter-spacing: 0.05em !important;
        padding: 10px 24px !important;
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
        font-size: 0.92rem !important;
        padding: 10px 24px !important;
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
    
    div[role="slider"] {
        background-color: #FFFF00 !important;
    }
    .stSlider > div {
        color: #FFFF00 !important;
    }
    div[data-testid="stCheckbox"] > label > div:first-child {
        background-color: #FFFF00 !important;
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
    
    @media (min-width: 992px) {
        div[data-testid="stColumn"]:nth-child(2) {
            position: -webkit-sticky;
            position: sticky;
            top: 20px;
            z-index: 999;
        }
    }
    
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

# Load Civil Questions
def get_civil_questions():
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
            
    if DATA_JSON.exists():
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data.get("civil_questions", [])), "default", None
    return pd.DataFrame(), "default", None

q_df, active_survey_id, client_name = get_civil_questions()

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

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email.strip()) is not None

if q_df.empty:
    st.stop()

# Image Mapping for Civil
IMAGE_MAPPING = {
    "CI01": "fy27-aec-forma-industry-cloud-imagery.webp",
    "CI02": "brand-image-prototype-1-dark.webp",
    "CI03": "brand-image-prototype-4-dark.webp",
    "CI04": "fy27-dm-digital-factory-campaign-visual-01.webp",
    "CI05": "fy27-water-image-02.webp",
    "CI06": "fy27-aec-forma-industry-cloud-imagery.webp",
    "CI07": "Construction-CCEED-China-0644_with_overlay.webp",
    "CI08": "fy27-dm-fusion-industry-cloud-imagery.webp"
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
        <div style="border: 1px solid #666666; background-color: #121212; height: 220px; display: flex; align-items: center; justify-content: center; border-radius: 0px; color: #D5D5CB; font-size: 0.9rem; font-family: monospace; margin-bottom: 20px;">
        [ AUTODESK // PRECISION_DESIGN_SYSTEM ]
        </div>
        """,
        unsafe_allow_html=True
    )

# Brand Header Layout
stacked_logo_svg = '<svg width="220" height="85" viewBox="0 0 220 85" fill="none" xmlns="http://www.w3.org/2000/svg"><g transform="scale(2.4) translate(30, 1)"><path d="M0.538536 22.7316L19.9163 10.678H29.9686C30.2781 10.678 30.5561 10.9259 30.5561 11.2662C30.5561 11.5442 30.4321 11.6681 30.2781 11.7605L20.7598 17.4657C20.1416 17.8368 19.9252 18.579 19.9252 19.1356L19.9155 22.7316H32.0097V1.83296C32.0097 1.4303 31.7002 1.09078 31.2367 1.09078H19.6999L0.369995 13.091V22.7316L0.538536 22.7316Z" fill="white"/></g><text x="110" y="74" fill="white" font-family="\'Inter\', sans-serif" font-size="18" font-weight="900" letter-spacing="4.5" text-anchor="middle">AUTODESK</text></svg>'
header_html = f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; margin-bottom: 10px; gap: 20px;"><div style="width: 220px; display: flex; align-items: center;">{stacked_logo_svg}</div><div style="text-align: right; min-width: 250px;"><div style="font-size: 0.75rem; color: #666666; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Maturity Evaluation Platform</div><div style="font-size: 1.7rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.03em;">土木・インフラ CIM適性診断</div></div></div>'
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
            st.markdown("<h3 style='margin-bottom:10px; font-weight:700; color:#FFFFFF;'>アセスメント回答送信完了</h3>", unsafe_allow_html=True)
            st.success("アセスメントの回答が安全に記録されました。ご協力ありがとうございました。")
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#FFFF00; font-weight:700; margin-bottom:10px;'>お客様の回答に基づく最適なソリューション提案</h4>", unsafe_allow_html=True)
            
            # Gap分析
            gaps = []
            for _, r in q_df.iterrows():
                qid = r['question_id']
                is_skipped = st.session_state.get(f"skip_{qid}", False)
                if not is_skipped:
                    as_is = st.session_state.get(f"asis_{qid}", 2)
                    to_be = st.session_state.get(f"tobe_{qid}", 4)
                    gaps.append({
                        "question_id": qid,
                        "gap": to_be - as_is,
                        "to_be": to_be
                    })
            
            gaps_sorted = sorted(gaps, key=lambda x: (x["gap"], x["to_be"]), reverse=True)
            
            PRODUCT_PROPOSALS = {
                "CI01": {
                    "title": "広域インフラ計画・概略設計・ビジュアライゼーション - Autodesk InfraWorks",
                    "desc": "現況地形データやGISを用いた初期の広域インフラ計画・ルート比較に課題が見られます。InfraWorksを使用することで、点群や地図データを瞬時に統合した3D現況モデルを構築し、複数案のルート比較や概略土工設計を圧倒的なビジュアルで進行できます。",
                    "url": "https://www.autodesk.com/products/infraworks/overview"
                },
                "CI02": {
                    "title": "CIM対応土木3D設計プラットフォーム - Autodesk Civil 3D",
                    "desc": "道路や造成、法面展開などの線形・勾配パラメトリック設計に大きなGapがあります。Civil 3Dを導入することで、平面線形の変更に合わせて縦断・横断図、および3D土工形状がリアルタイムに自動更新・一貫維持されます。",
                    "url": "https://www.autodesk.com/products/civil-3d/overview"
                },
                "CI03": {
                    "title": "土木構造物BIMと土工モデルのシームレス統合 - Revit & Civil 3D 連携",
                    "desc": "橋梁や擁壁、トンネルなどの構造物モデルと、土木線形の取り合い・整合性に課題感が見られます。RevitとCivil 3Dを連携させることで、道路線形の勾配や座標変化に沿って構造物が自動配置・更新され、不整合をゼロにします。",
                    "url": "https://www.autodesk.com/products/civil-3d/overview"
                },
                "CI04": {
                    "title": "高精度土量算出と切盛バランス自動最適化 - Autodesk Civil 3D",
                    "desc": "造成的・線形上の土量計算や切盛バランスの調整に大きな乖離が見られます。Civil 3Dの3Dサーフェス比較機能を使用し、線形変更に応じた土量算出を完全自動化し、最も無駄のない計画案を即時シミュレートできます。",
                    "url": "https://www.autodesk.com/products/civil-3d/overview"
                },
                "CI05": {
                    "title": "クラウド型土木CIM協調設計 - ACC Collaboration for Civil 3D",
                    "desc": "大容量の地形データや線形情報を関係者間でリアルタイムに共有・共同編集するCDE環境にGapがあります。ACCのCivil 3D専用連携機能を導入することで、クラウド上で安全にバージョン管理と参照データの動的更新を可能にします。",
                    "url": "https://www.autodesk.com/products/autodesk-construction-cloud/overview"
                },
                "CI06": {
                    "title": "周辺住民・発注者向けビジュアル合意形成 - Autodesk InfraWorks",
                    "desc": "協議や住民説明におけるCIMの視覚的活用度に課題があります。InfraWorksによる周辺環境を含む高精度な3Dビジュアルモデルを活用することで、計画のルート決定や日照・交通影響のプレゼンテーションを劇的に加速できます。",
                    "url": "https://www.autodesk.com/products/infraworks/overview"
                },
                "CI07": {
                    "title": "レーザースキャン点群地形処理 - Autodesk ReCap Pro",
                    "desc": "ドローン点群やレーザースキャナで得られた現況地形の出来形比較に改善の余地があります。ReCap ProとCivil 3Dを組み合わせ、点群データからメッシュ・地形サーフェスを半自動で抽出し、i-Constructionに準拠した施工進捗管理を行えます。",
                    "url": "https://www.autodesk.com/products/recap/overview"
                },
                "CI08": {
                    "title": "電子納品・維持管理アセットデータ連携 - Autodesk Civil 3D & Tandem",
                    "desc": "CIM電子納品モデルのデータ整備および維持管理段階へのデータ引き渡しにGapが見られます。Civil 3Dによる属性情報の自動埋め込みと、デジタルツインプラットフォームへの連携により、ライフサイクル全体の価値を最大化します。",
                    "url": "https://www.autodesk.com/products/civil-3d/overview"
                }
            }
            
            display_count = 0
            for gap_item in gaps_sorted:
                qid = gap_item["question_id"]
                if qid in PRODUCT_PROPOSALS and gap_item["gap"] >= 1:
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
                    if display_count >= 2:
                        break
                        
            if display_count == 0:
                st.markdown(
                    """
                    <div class="proposal-card">
                        <div class="proposal-title">Autodesk Architecture, Engineering & Construction Collection (AEC Collection)</div>
                        <div class="proposal-desc">お客様の土木デジタル推進レベルはすでに素晴らしい高水準にあります。Civil 3D、InfraWorks、Revit、ReCap Proをすべて含んだAECコレクションパッケージにより、国土強靭化・スマートシティ設計におけるすべてのCIMプロセスを高度化できます。</div>
                        <a href="https://www.autodesk.com/collections/design-lifecyle-collection/overview" target="_blank" class="proposal-link-btn">AEC コレクションの詳細を確認する</a>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            if st.button("アセスメントを再回答する", type="secondary"):
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
            
            specific_team = st.text_input("部署名・チーム名 (任意)", placeholder="例: 土木設計部 技術課", value=st.session_state.get("res_team", ""))
            st.session_state["res_team"] = specific_team
            
            st.markdown("<hr style='border-color:#666666; margin:20px 0;'>", unsafe_allow_html=True)
            agree_privacy = st.checkbox("個人情報の取り扱い説明事項を確認し、同意します。 *", value=st.session_state.get("agree_privacy", False), key="agree_privacy_step0")
            st.session_state["agree_privacy"] = agree_privacy
            
            if not agree_privacy:
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                st.markdown("<b style='font-size:0.85rem; color:#666666;'>【確認用：個人情報保護に関する同意文面（法務確認中プレースホルダー）】</b>", unsafe_allow_html=True)
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
            current_idx = st.session_state.current_step - 1
            row = q_df.iloc[current_idx]
            qid = row['question_id']
            
            st.markdown(
                f"<div style='font-size:0.85rem; color:#FFFF00; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;'>"
                f"{row['department']} 領域  ·  STEP {st.session_state.current_step} / {num_questions}</div>",
                unsafe_allow_html=True
            )
            st.markdown(f"<h3 style='margin-top:2px; font-size:1.6rem; font-weight:700;'>{row['question_id']} ({row['phase']})</h3>", unsafe_allow_html=True)
            
            st.markdown(
                f"<div style='background-color:#121212; padding:12px 16px; border-left:3px solid #FFFF00; margin-bottom:12px; font-size:0.95rem; line-height:1.5; color:#FFFFFF;'>"
                f"{row['question_text']} 各レベルの定義を参考に、現状と目標を選択してください。</div>", 
                unsafe_allow_html=True
            )
            
            skip_key = f"skip_{qid}"
            if skip_key not in st.session_state:
                st.session_state[skip_key] = False
            skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=skip_key)
            
            levels_container = st.container()
            profile_container = st.container()
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
                    edit_agree = st.checkbox("個人情報の取り扱い説明事項に同意します *", value=st.session_state.get("agree_privacy", False), key="edit_agree")
                    st.session_state["agree_privacy"] = edit_agree
                    
                    if not edit_agree:
                        st.markdown("<div style='margin-top:5px;'></div>", unsafe_allow_html=True)
                        st.info("[法務確認済みの個人情報保護方針に関する詳細な同意文面がここに入ります。]")
                
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            
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
        if st.session_state.is_submitted:
            render_hero_image("CI01")
        elif st.session_state.current_step == 0:
            render_hero_image("CI01") 
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

    # 送信処理
    if not st.session_state.is_submitted and st.session_state.current_step == num_questions and submit_clicked:
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
                fs_success = save_response_to_firestore(firestore_doc)
                sheets_success = False
                if fs_success:
                    sheets_success = save_response_to_sheets(records)
                
                if fs_success:
                    st.balloons()
                    st.session_state.is_submitted = True
                    st.rerun()
                else:
                    st.error("送信に失敗しました。")
