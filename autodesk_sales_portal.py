import streamlit as st
import pandas as pd
from pathlib import Path
from db_helper import (
    verify_or_register_sales_user,
    get_surveys_by_owner,
    load_responses_from_firestore,
    update_survey_status
)
import plotly.graph_objects as go

try:
    st.set_page_config(page_title="営業マイポータル | IFM Maturity Assessment", layout="wide")
except Exception:
    pass

# Theme setup (Autodesk Black/Yellow modern dark theme)
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: Arial, system-ui, -apple-system, "Segoe UI", sans-serif !important;
        font-size: 16px !important;
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    .portal-card {
        background-color: #121212;
        border: 1px solid #333333;
        border-left: 5px solid #FFFF00;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #FFFF00 !important;
        color: #000000 !important;
        font-weight: 800 !important;
        border: none !important;
        border-radius: 4px !important;
    }
    div.stButton > button[data-testid="stBaseButton-primary"] * {
        color: #000000 !important;
    }
    
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# Header
st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
            <div style="font-size:0.85rem; color:#FFFF00; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;">SALES PERSONAL PORTAL</div>
            <h2 style="margin:0; font-weight:700;"> 営業専用マイポータル</h2>
        </div>
        <div>
            <a href="/?brand=autodesk&app=portal" target="_self" style="background-color:#333; color:#FFF; padding:8px 16px; border-radius:4px; text-decoration:none; font-size:0.85rem; font-weight:600;">← ポータル画面へ戻る</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("---")

if "sales_email" not in st.session_state:
    st.session_state.sales_email = None

if not st.session_state.sales_email:
    st.markdown("###  営業ログイン ＆ マイポータル開設")
    st.caption("メールアドレスと簡易暗証番号（4桁以上のPIN）を入力してログインしてください。初回は自動登録されます。")
    
    col_l1, col_l2 = st.columns([1, 1])
    with col_l1:
        login_email = st.text_input(" メールアドレス *", placeholder="example@autodesk.com")
        login_pin = st.text_input(" 簡易暗証番号 (PIN) *", type="password", placeholder="例: 1234")
        
        if st.button(" ログイン / マイアカウント開設", type="primary", use_container_width=True):
            if not login_email.strip() or not login_pin.strip():
                st.error("メールアドレスと暗証番号の両方を入力してください。")
            else:
                ok, msg = verify_or_register_sales_user(login_email, login_pin)
                if ok:
                    st.session_state.sales_email = login_email.strip().lower()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
else:
    user_email = st.session_state.sales_email
    col_u1, col_u2 = st.columns([3, 1])
    with col_u1:
        st.markdown(f"ログイン中: **{user_email}**")
    with col_u2:
        if st.button(" ログアウト", type="secondary"):
            st.session_state.sales_email = None
            st.rerun()
            
    st.markdown("---")
    
    # Quick action banner
    st.markdown(
        """
        <div style="background-color:#0d1b2a; border:1px solid #1e3a8a; border-left:5px solid #00F0FF; padding:18px; border-radius:6px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h4 style="margin:0 0 6px; color:#00F0FF;"> 新しいAIカスタムアンケートを発行・調整する</h4>
                    <p style="margin:0; font-size:0.92rem; color:#CCCCCC;">顧客の業界用語や商談文脈に合わせた設問プロンプトを生成し、難読化URLを発行できます。</p>
                </div>
                <a href="/?brand=autodesk&app=product_mapping" target="_self" style="background-color:#00F0FF; color:#000; padding:10px 20px; border-radius:4px; font-weight:800; text-decoration:none;">AI調整ツールを開く →</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Load user's custom surveys
    my_surveys = get_surveys_by_owner(user_email)
    
    st.markdown("###  あなたが発行したアンケート一覧")
    st.caption("顧客へ送付した難読化URLと、これまでの回答状況を管理できます。")
    
    if not my_surveys:
        st.info("まだ発行したカスタムアンケートはありません。「AI調整ツール」から新しいアンケートを発行してください。")
    else:
        # Load all responses for stats
        all_responses_df = load_responses_from_firestore()
        
        for sv in my_surveys:
            sid = sv.get("survey_id")
            cname = sv.get("client_name") or "未設定"
            status = sv.get("status", "draft")
            module = sv.get("module_name", "AI Custom Survey")
            clean_url = f"https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?brand=autodesk&survey_id={sid}"
            
            # Count responses for this survey
            resp_count = 0
            if not all_responses_df.empty and "survey_id" in all_responses_df.columns:
                resp_count = len(all_responses_df[all_responses_df["survey_id"] == sid]["timestamp"].unique())
                
            status_badge = '<span style="background-color:#666666; color:#FFF; font-size:0.75rem; padding:2px 8px; border-radius:3px;">下書き</span>'
            if status == "pending_approval":
                status_badge = '<span style="background-color:#FFFF00; color:#000; font-size:0.75rem; font-weight:bold; padding:2px 8px; border-radius:3px;">正規化申請中</span>'
            elif status == "approved":
                status_badge = '<span style="background-color:#4dff88; color:#000; font-size:0.75rem; font-weight:bold; padding:2px 8px; border-radius:3px;">公式採用済み</span>'
                
            with st.container():
                st.markdown(
                    f"""
                    <div class="portal-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <div>
                                {status_badge}
                                <strong style="font-size:1.1rem; color:#FFFF00; margin-left:8px;">{cname}</strong>
                                <span style="font-size:0.85rem; color:#AAAAAA; margin-left:12px;">(ID: {sid} · {module})</span>
                            </div>
                            <div style="font-size:0.9rem; color:#4dff88; font-weight:bold;">
                                獲得回答数: {resp_count} 件
                            </div>
                        </div>
                        <div style="margin-bottom:10px;">
                            <span style="font-size:0.88rem; color:#CCCCCC;">顧客送付用URL: </span>
                            <a href="{clean_url}" target="_blank" style="color:#FFFF00; font-size:0.9rem;">{clean_url}</a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if status == "draft":
                        if st.button(f"★ このアンケートを正規化申請", key=f"req_{sid}"):
                            if update_survey_status(sid, "pending_approval"):
                                st.success("申請しました！")
                                st.rerun()
                with col_b2:
                    with st.expander(f" 回答データ・詳細を表示 ({resp_count}件)"):
                        if resp_count == 0:
                            st.write("まだ回答データはありません。")
                        else:
                            sub_df = all_responses_df[all_responses_df["survey_id"] == sid]
                            st.dataframe(sub_df[["timestamp", "respondent", "email", "question_id", "as_is", "to_be"]])
