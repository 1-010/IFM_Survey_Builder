import streamlit as st
import pandas as pd
from datetime import datetime
import re

from ifm_guardrails import get_secret_password

# Import Firestore helpers
from db_helper import (
    get_firestore_client,
    get_all_custom_survey_ids,
    get_all_custom_surveys,
    update_survey_status
)

# Theme setup (Autodesk Black/Yellow)
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: Arial, system-ui, -apple-system, "Segoe UI", sans-serif !important;
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

header_html = '<div style="display:flex;align-items:end;justify-content:space-between;flex-wrap:wrap;margin:12px 0 16px;gap:16px;"><div><div style="font-size:.78rem;color:#FF8A80;letter-spacing:.12em;text-transform:uppercase;font-weight:600;">IFM Database Maintenance</div><div style="font-size:1.85rem;font-weight:700;color:#FFFFFF;letter-spacing:-.03em;">超管理者用システムメンテナンス</div></div><div style="font-size:.8rem;color:#D5D5CB;">for Autodesk Design &amp; Make workflows</div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Authentication
super_pw = st.text_input("超管理者専用パスワードを入力してください", type="password", key="super_admin_pw_input")

correct_pw = get_secret_password(st.secrets, "super_admin")

if correct_pw is None:
    st.error("超管理者認証が設定されていません。Secrets の super_admin.password を設定してください。")
elif super_pw == correct_pw:
    st.success("認証完了。メンテナンスメニューが利用可能です。")
    db = get_firestore_client()
    
    if not db:
        st.error("データベースへの接続が確立できません。")
        st.stop()
        
    tabs = st.tabs([" 営業AI設問の監査 ＆ 正規化承認", " アンケートID管理", " 回答データ一括クレンジング", " Autodesk製品提案マッピング"])
    
    # --- Tab 0: 営業AI設問の監査 ＆ 正規化承認 ---
    with tabs[0]:
        st.subheader(" 営業作成AIアンケートの監査・正規化承認コンソール")
        st.write("各営業担当がAIを使ってカスタマイズしたアンケートのプロンプト・設問定義を監査し、優秀なものを公式モジュールとして承認・昇格させます。")
        
        all_surveys = get_all_custom_surveys()
        
        if not all_surveys:
            st.info("現在データベ―スに登録されているカスタムアンケートはありません。")
        else:
            filter_status = st.radio("表示フィルタ:", ["すべて", "正規化申請中 (pending_approval)", "公式採用済み (approved)", "下書き (draft)"], horizontal=True)
            
            filtered = all_surveys
            if "申請中" in filter_status:
                filtered = [s for s in all_surveys if s.get("status") == "pending_approval"]
            elif "採用済み" in filter_status:
                filtered = [s for s in all_surveys if s.get("status") == "approved"]
            elif "下書き" in filter_status:
                filtered = [s for s in all_surveys if s.get("status") == "draft"]
                
            st.markdown(f"**該当件数: {len(filtered)} 件**")
            st.markdown("---")
            
            for s in filtered:
                sid = s.get("survey_id")
                cname = s.get("client_name") or "未設定"
                owner = s.get("owner_email") or s.get("creator") or "不明"
                status = s.get("status", "draft")
                prompt = s.get("ai_prompt") or "プロンプト記録なし"
                questions = s.get("questions", [])
                
                status_color = "#666"
                status_text = "下書き"
                if status == "pending_approval":
                    status_color = "#FFFF00"
                    status_text = "★ 正規化申請中"
                elif status == "approved":
                    status_color = "#4dff88"
                    status_text = "公式採用済み"
                    
                with st.expander(f"【{status_text}】 ID: {sid} | 顧客名: {cname} | 作成営業: {owner}"):
                    st.markdown(f"**作成営業**: `{owner}`")
                    st.markdown(f"**顧客/案件メモ**: `{cname}`")
                    st.markdown(f"**難読化URL**: `https://ifmsurveybuilder-dm4twazgypcxpcagcebod5.streamlit.app/?brand=autodesk&survey_id={sid}`")
                    
                    st.markdown("** AI指示プロンプト監査:**")
                    st.code(prompt, language="markdown")
                    
                    st.markdown(f"** 設問数 ({len(questions)}問):**")
                    for q in questions[:3]:
                        st.markdown(f"- **[{q.get('question_id')}]**: {q.get('question_text')}")
                    if len(questions) > 3:
                        st.caption(f"...他 {len(questions)-3} 問")
                        
                    st.markdown("---")
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if status != "approved":
                            if st.button(f"★ このAIアンケートを公式モジュールとして承認・昇格 ({sid})", key=f"appr_{sid}"):
                                if update_survey_status(sid, "approved"):
                                    st.success(f"アンケート {sid} を公式採用に更新しました！")
                                    st.rerun()
                    with c_btn2:
                        if status == "pending_approval":
                            if st.button(f" 申請を却下（下書きに戻す） ({sid})", key=f"rej_{sid}"):
                                if update_survey_status(sid, "draft"):
                                    st.info(f"アンケート {sid} を下書きに戻しました。")
                                    st.rerun()

    # --- Tab 1: アンケートID管理 ---
    with tabs[1]:
        st.subheader("カスタムアンケートID (surveys) の一覧 ＆ 削除")
        st.write("営業管理画面で過去に発行されたすべてのカスタムアンケート定義の一覧です。テスト用や誤作動の不要データを削除できます。")
        
        try:
            surveys_ref = db.collection("surveys").stream()
            surveys_list = []
            for doc in surveys_ref:
                d = doc.to_dict()
                created_at_val = d.get("created_at")
                if created_at_val:
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
                for s in surveys_list:
                    col_info, col_del = st.columns([8, 2])
                    with col_info:
                        st.markdown(
                            f" **アンケートID**: `{s['survey_id']}`  ·  **顧客企業名**: {s['client_name']}  ·  **作成者**: {s['creator']}  ·  **作成日時**: {s['created_at']}  ·  **設問数**: {s['num_questions']}問"
                        )
                    with col_del:
                        st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                        pending_key = f"confirm_survey_{s['survey_id']}"
                        if st.session_state.get(pending_key):
                            st.warning("もう一度押すと完全に削除します。")
                        if st.button(
                            f"{'完全削除を確定' if st.session_state.get(pending_key) else '削除を確認'}: {s['survey_id']}",
                            key=f"del_survey_{s['survey_id']}",
                        ):
                            if not st.session_state.get(pending_key):
                                st.session_state[pending_key] = True
                                st.rerun()
                            else:
                                try:
                                    db.collection("surveys").document(s['survey_id']).delete()
                                    st.success(f"アンケート `{s['survey_id']}` を削除しました。")
                                    st.session_state.pop(pending_key, None)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"削除エラー: {e}")
                        st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Firestore取得エラー: {e}")

    # --- Tab 2: 回答データ一括クレンジング ---
    with tabs[2]:
        st.subheader("回答データ (responses) の一括削除・メンテナンス")
        st.warning(" 警告: ここでの操作は復元できません。動作テスト用データや誤入力データをクレンジングする場合のみ実行してください。")
        
        try:
            resp_docs = list(db.collection("responses").stream())
            total_responses = len(resp_docs)
            st.info(f"現在データベースに保存されている総回答ドキュメント数: **{total_responses}** 件")
            
            if total_responses > 0:
                st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                pending_clean_key = "confirm_all_responses_clean"
                if st.session_state.get(pending_clean_key):
                    st.error("【注意】本当に全回答データを削除します。この操作は取り消せません。")
                if st.button(
                    "【注意】すべての回答データを一括削除する" if not st.session_state.get(pending_clean_key) else "【確定】すべての回答データを即時消去する",
                    key="btn_clean_all_responses"
                ):
                    if not st.session_state.get(pending_clean_key):
                        st.session_state[pending_clean_key] = True
                        st.rerun()
                    else:
                        try:
                            batch = db.batch()
                            count = 0
                            for doc in resp_docs:
                                batch.delete(doc.reference)
                                count += 1
                                if count % 450 == 0:
                                    batch.commit()
                                    batch = db.batch()
                            batch.commit()
                            st.success(f"全 {total_responses} 件の回答データを安全に消去しました。")
                            st.session_state.pop(pending_clean_key, None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"一括削除処理エラー: {e}")
                st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Firestore取得エラー: {e}")

    # --- Tab 3: Autodesk製品提案マッピング ---
    with tabs[3]:
        st.subheader("Autodeskソリューション・製品提案マスタ管理")
        st.caption("各部門・フェーズごとの推奨Autodesk製品（Revit, Inventor, Navisworks, ACC, Tandem 等）のマッピング設定です。")
        st.info("現在は JSON マスタ (`ifm_questions.json`) および製品マッピングテーブルで自動制御されています。")

st.caption("IFM Database Maintenance | Autodesk Design & Make Solutions")
