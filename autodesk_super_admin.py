import streamlit as st
import pandas as pd
from datetime import datetime
import re

# Import Firestore helpers
from db_helper import (
    get_firestore_client,
    get_all_custom_survey_ids
)

# Page configuration for Autodesk Brand Look
st.set_page_config(page_title="Autodesk Platform - Super Admin Panel", layout="wide")

# Theme setup (Autodesk Black/Yellow)
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
    
    div[data-baseweb="input"], select, textarea {
        border-radius: 4px !important;
        border: 1px solid #666666 !important;
        background-color: #121212 !important;
        color: #FFFFFF !important;
    }
    
    div.stButton > button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid #666666 !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        padding: 8px 20px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button:hover {
        border-color: #FF5252 !important;
        color: #FF5252 !important;
    }
    
    .danger-btn > div.stButton > button {
        background-color: #8B0000 !important;
        color: #FFFFFF !important;
        border: 1px solid #FF5252 !important;
    }
    .danger-btn > div.stButton > button:hover {
        background-color: #FF5252 !important;
        color: #000000 !important;
        border-color: #FF5252 !important;
    }
    
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# Header
stacked_logo_svg = '<svg width="220" height="85" viewBox="0 0 220 85" fill="none" xmlns="http://www.w3.org/2000/svg"><g transform="scale(2.4) translate(30, 1)"><path d="M0.538536 22.7316L19.9163 10.678H29.9686C30.2781 10.678 30.5561 10.9259 30.5561 11.2662C30.5561 11.5442 30.4321 11.6681 30.2781 11.7605L20.7598 17.4657C20.1416 17.8368 19.9252 18.579 19.9252 19.1356L19.9155 22.7316H32.0097V1.83296C32.0097 1.4303 31.7002 1.09078 31.2367 1.09078H19.6999L0.369995 13.091V22.7316L0.538536 22.7316Z" fill="white"/></g><text x="110" y="74" fill="white" font-family="\'Inter\', sans-serif" font-size="18" font-weight="900" letter-spacing="4.5" text-anchor="middle">AUTODESK</text></svg>'
header_html = f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; margin-bottom: 10px; gap: 20px;"><div style="width: 220px; display: flex; align-items: center;">{stacked_logo_svg}</div><div style="text-align: right; min-width: 250px;"><div style="font-size: 0.75rem; color: #FF5252; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Database Maintenance Portal</div><div style="font-size: 1.7rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.03em;">超管理者用システムメンテナンス</div></div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Authentication
super_pw = st.text_input("超管理者専用パスワードを入力してください", type="password", key="super_admin_pw_input")

if super_pw == "ifm-super-admin-root":
    st.success("認証完了。メンテナンスメニューが利用可能です。")
    db = get_firestore_client()
    
    if not db:
        st.error("データベースへの接続が確立できません。")
        st.stop()
        
    tabs = st.tabs(["📁 アンケートID管理", "📝 回答データ一括クレンジング", "📊 システムステータス"])
    
    # --- Tab 1: アンケートID管理 ---
    with tabs[0]:
        st.subheader("カスタムアンケートID (surveys) の一覧 ＆ 削除")
        st.write("営業管理画面で過去に発行されたすべてのカスタムアンケート定義の一覧です。テスト用や誤作動の不要データを削除できます。")
        
        try:
            surveys_ref = db.collection("surveys").stream()
            surveys_list = []
            for doc in surveys_ref:
                d = doc.to_dict()
                created_at_val = d.get("created_at")
                if created_at_val:
                    # Firestoreのtimestamp型をパース
                    try:
                        created_at_str = str(created_at_val.isoformat())[:19].replace("T", " ")
                    except:
                        created_at_str = str(created_at_val)
                else:
                    created_at_str = "不明"
                    
                surveys_list.append({
                    "doc_id": doc.id,
                    "survey_id": d.get("survey_id"),
                    "client_name": d.get("client_name"),
                    "creator": d.get("creator"),
                    "created_at": created_at_str,
                    "num_questions": len(d.get("questions", []))
                })
                
            if not surveys_list:
                st.info("登録されているカスタムアンケートはありません。")
            else:
                surveys_df = pd.DataFrame(surveys_list)
                
                # 表示用テーブルのレンダリング
                for s in surveys_list:
                    col_info, col_del = st.columns([8, 2])
                    with col_info:
                        st.markdown(
                            f"📌 **アンケートID**: `{s['survey_id']}`  ·  **顧客企業名**: {s['client_name']}  ·  **作成者**: {s['creator']}  ·  **作成日時**: {s['created_at']}  ·  **設問数**: {s['num_questions']}問"
                        )
                    with col_del:
                        st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                        if st.button(f"削除: {s['survey_id']}", key=f"del_survey_{s['survey_id']}"):
                            # 削除確認処理
                            db.collection("surveys").document(s['survey_id']).delete()
                            st.success(f"ID: `{s['survey_id']}` を削除しました。画面を再読み込みしてください。")
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"アンケート一覧取得エラー: {e}")
            
    # --- Tab 2: 回答データ一括クレンジング ---
    with tabs[1]:
        st.subheader("送信済み回答データ (responses) の一括削除・クリーニング")
        st.warning("【注意】回答データを削除すると復元できません。テスト用の回答やデモでの不要データを削除する目的にのみ使用してください。")
        
        try:
            # responses コレクションの概要把握
            responses_ref = db.collection("responses").stream()
            responses_list = []
            for doc in responses_ref:
                d = doc.to_dict()
                responses_list.append({
                    "doc_id": doc.id,
                    "timestamp": d.get("timestamp"),
                    "respondent": d.get("respondent"),
                    "email": d.get("email"),
                    "survey_id": d.get("survey_id", "default"),
                    "team": d.get("team", ""),
                    "num_answers": len(d.get("answers", []))
                })
                
            if not responses_list:
                st.info("格納されている回答データはありません。")
            else:
                resp_df = pd.DataFrame(responses_list)
                
                # アンケートID（survey_id）ごとにグルーピングした件数表示
                st.markdown("### 📊 アンケートIDごとの回答蓄積状況")
                summary_grp = resp_df.groupby('survey_id').agg(
                    回答者ユニーク数=('email', 'nunique'),
                    送信件数=('doc_id', 'count')
                ).reset_index()
                st.dataframe(summary_grp, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.markdown("### 🚨 アンケートID単位での回答データ一括削除")
                target_del_sid = st.selectbox("一括削除対象のアンケートIDを選択してください", sorted(list(resp_df['survey_id'].unique())))
                
                # 削除ボタン
                st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                confirm_del_btn = st.button(f"🔴 アンケートID '{target_del_sid}' のすべての回答データを一括削除する", key="btn_bulk_delete_responses")
                if confirm_del_btn:
                    # Firestoreクエリで該当ドキュメントを抽出して削除
                    docs_to_delete = db.collection("responses").where("survey_id", "==", target_del_sid).stream()
                    deleted_count = 0
                    for doc in docs_to_delete:
                        db.collection("responses").document(doc.id).delete()
                        deleted_count += 1
                    st.success(f"アンケートID: `{target_del_sid}` に紐づく {deleted_count} 件の回答データを一括削除しました！")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("### 📄 個別回答レコードの一覧と個別削除")
                for r in responses_list:
                    col_r_info, col_r_del = st.columns([8, 2])
                    with col_r_info:
                        st.markdown(
                            f"👤 **回答者**: {r['respondent']} ({r['email']})  ·  **部署**: {r['team']}  ·  **アンケートID**: `{r['survey_id']}`  ·  **日時**: {r['timestamp'][:19].replace('T', ' ')}"
                        )
                    with col_r_del:
                        st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                        if st.button("削除", key=f"del_resp_{r['doc_id']}"):
                            db.collection("responses").document(r['doc_id']).delete()
                            st.success(f"ドキュメントID: `{r['doc_id']}` を個別削除しました。")
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"回答データ一覧取得エラー: {e}")
            
    # --- Tab 3: システムステータス ---
    with tabs[2]:
        st.subheader("データベース接続情報 ＆ サーバー環境ステータス")
        st.write(f"**データベース**: Google Cloud Firestore (プロジェクトID: `{db.project}`)")
        st.write(f"**現在のローカル時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.write("**Firestore コレクションステータス**:")
        
        try:
            surveys_cnt = sum(1 for _ in db.collection("surveys").select([]).stream())
            responses_cnt = sum(1 for _ in db.collection("responses").select([]).stream())
            st.write(f"- surveys（アンケートID定義数）: `{surveys_cnt}` 件")
            st.write(f"- responses（送信済み回答ドキュメント数）: `{responses_cnt}` 件")
        except Exception as e:
            st.write(f"ステータス取得エラー: {e}")
            
else:
    if super_pw != "":
        st.error("超管理者専用パスワードが正しくありません。")
