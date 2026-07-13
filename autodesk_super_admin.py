import streamlit as st
import pandas as pd
from datetime import datetime
import re

from ifm_guardrails import get_secret_password

# Import Firestore helpers
from db_helper import (
    get_firestore_client,
    get_all_custom_survey_ids
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

# The IFM service identity stays primary; Autodesk is referenced descriptively.
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
        
    tabs = st.tabs([" アンケートID管理", " 回答データ一括クレンジング", " Autodesk製品提案マッピング", " システムステータス"])
    
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
                            db.collection("surveys").document(s['survey_id']).delete()
                            st.session_state.pop(pending_key, None)
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
                st.markdown("###  アンケートIDごとの回答蓄積状況")
                summary_grp = resp_df.groupby('survey_id').agg(
                    回答者ユニーク数=('email', 'nunique'),
                    送信件数=('doc_id', 'count')
                ).reset_index()
                st.dataframe(summary_grp, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.markdown("###  アンケートID単位での回答データ一括削除")
                target_del_sid = st.selectbox("一括削除対象のアンケートIDを選択してください", sorted(list(resp_df['survey_id'].unique())))
                
                # 削除ボタン
                st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                confirm_phrase = st.text_input(
                    "確認のためアンケートIDを入力してください",
                    key="bulk_delete_confirmation",
                )
                target_count = int((resp_df['survey_id'] == target_del_sid).sum())
                confirm_del_btn = st.button(
                    f"アンケートID '{target_del_sid}' の回答 {target_count} 件を完全削除する",
                    key="btn_bulk_delete_responses",
                    disabled=confirm_phrase != target_del_sid,
                )
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
                st.markdown("###  個別回答レコードの一覧と個別削除")
                for r in responses_list:
                    col_r_info, col_r_del = st.columns([8, 2])
                    with col_r_info:
                        st.markdown(
                            f" **回答者**: {r['respondent']} ({r['email']})  ·  **部署**: {r['team']}  ·  **アンケートID**: `{r['survey_id']}`  ·  **日時**: {r['timestamp'][:19].replace('T', ' ')}"
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
            
    # --- Tab 3: Autodesk製品提案マッピング ---
    with tabs[2]:
        st.subheader(" アンケート設問とAutodeskプロダクトの関連性（営業用製品提案マッピング）")
        st.write("各アセスメント設問が「どのAutodesk製品の提案や価値訴求に結びつくか」を整理したセールスチートシートです。顧客のスコア（As-Is/To-Be）に応じて提案アプローチを決定するための判断基準としてご利用ください。")
        
        # Mapping definition
        product_mapping = {
            "PE01": {
                "dept": "生産技術",
                "phase": "計画",
                "title": "PE01 (計画): 生産・工程計画やレイアウト設備検討におけるデータ活用",
                "products": "Factory Design Utilities (FDU), AutoCAD Architecture, Inventor",
                "value_pitch": "2D-3D双方向同期レイアウト設計による手戻り防止。2Dでの簡易配置が3Dへ即座に反映され、設備干渉の早期発見が可能。",
                "sales_hint": "L1-L2レベル（2D中心）の顧客には、FDUを用いた2D-3Dレイアウト同期と、標準アセットライブラリによる配置設計の高速化を提案。"
            },
            "PE02": {
                "dept": "生産技術",
                "phase": "設計",
                "title": "PE02 (設計): 設備やラインの設計プロセスにおけるデータ活用",
                "products": "Autodesk Inventor, iLogic, Informed Design",
                "value_pitch": "パラメータ駆動設計とモデリングルールの標準化。Informed Designにより製造可能な設計条件をパラメータとしてロックし、Revitへ出力可能。",
                "sales_hint": "L2-L3の顧客には、iLogicによる定型モデリングの自動化、およびInformed Designによるモジュール製品のデジタルカタログ化・Revitファミリ化を提案。"
            },
            "PE03": {
                "dept": "生産技術",
                "phase": "検証",
                "title": "PE03 (検証): 設計内容の検証やシミュレーションにおけるデータ活用",
                "products": "Autodesk Navisworks Manage, Inventor Simulation",
                "value_pitch": "マルチサプライヤ設備データの統合、および自動干渉チェックによる施工前エラー検出。構造シミュレーションによる動作検証。",
                "sales_hint": "L3-L4の顧客には、Navisworksを用いた干渉チェック自動化と設計変更プロセスのデジタル追跡（Issues連携）を提案。"
            },
            "PE04": {
                "dept": "生産技術",
                "phase": "建設",
                "title": "PE04 (建設): 設備の導入や建設段階の進捗管理におけるデータ活用",
                "products": "Autodesk Construction Cloud (ACC) / Build, Navisworks (4D)",
                "value_pitch": "現場設備導入の進捗と計画のデジタル管理、4D施工シミュレーションによる現場干渉と作業順序の可視化・最適化。",
                "sales_hint": "施工段階の情報分断があるL2-L3にはACCによるチェックリスト管理、L4以上には4D連動施工計画を提案して現場手戻りを防止。"
            },
            "PE05": {
                "dept": "生産技術",
                "phase": "運用",
                "title": "PE05 (運用): 設備や生産ラインの運用・保全管理におけるデータ活用",
                "products": "Autodesk Tandem, MES Integration APIs",
                "value_pitch": "竣工BIMモデルからデジタルツインへの移行。工場内IoTセンサーや生産設備データ（MES）と連携し、稼働保全・予知保全を実現。",
                "sales_hint": "運用フェーズのL3-L4顧客へTandemを訴求し、設備状態モニタリングからデジタルツインでの自動最適化へのロードマップを提示。"
            },
            "FI01": {
                "dept": "工場建築・建設",
                "phase": "計画",
                "title": "FI01 (計画): 工場建築の計画策定や空間検討におけるデータ活用",
                "products": "Autodesk Revit, FormIt, Autodesk Docs",
                "value_pitch": "工場建築の初期コンセプト空間計画のデジタル可視化と、共通データ環境（CDE）による要件情報の一元管理・共有。",
                "sales_hint": "L1-L2レベルの建築計画検討をRevitの初期ボリュームスタディとDocsによる要件管理でデジタル化することを提案。"
            },
            "FI02": {
                "dept": "工場建築・建設",
                "phase": "設計",
                "title": "FI02 (設計): 工場建築の設計プロセスにおけるデータ活用",
                "products": "Autodesk Revit (BIM), BIM Collaborate Pro",
                "value_pitch": "属性（メタデータ）情報を持つインテリジェントBIMモデルの構築と、意匠・構造・設備（MEP）間のクラウドリアルタイム共同設計設計。",
                "sales_hint": "L2-L3の3Dモデリングから、属性情報を付与したBIM設計（Revit）とクラウド共同設計（BIM Collaborate Pro）への移行を推進。"
            },
            "FI03": {
                "dept": "工場建築・建設",
                "phase": "検証",
                "title": "FI03 (検証): 工場建築の検証（干渉チェックや施工性確認）におけるデータ活用",
                "products": "Autodesk Navisworks Manage, BIM Collaborate (Coordination)",
                "value_pitch": "建物構造と付帯・製造設備間の自動衝突検出（干渉チェック）。VR検証による設計不整合の現場着工前クリア。",
                "sales_hint": "L2-L3の目視チェックから、Navisworks/BIM Collaborateを用いた自動衝突検出と指摘事項（Issues）ワークフローの運用を提案。"
            },
            "FI04": {
                "dept": "工場建築・建設",
                "phase": "建設",
                "title": "FI04 (建設): 工場建築の施工計画や現場管理におけるデータ活用",
                "products": "Autodesk Build, ReCap Pro (Point Cloud)",
                "value_pitch": "3Dレーザースキャン点群（ReCap）とBIMモデルの重ね合わせによる出来形検査。現場施工計画のリアルタイム更新管理。",
                "sales_hint": "L3-L4の出来形検証・進捗管理に対して、ReCapの点群とAutodesk Buildによる現場施工管理の組み合わせを提案。"
            },
            "FI05": {
                "dept": "工場建築・建設",
                "phase": "運用",
                "title": "FI05 (運用): 工場の建物・設備の運用や保守管理におけるデータ活用",
                "products": "Autodesk Tandem, Facility Manager APIs",
                "value_pitch": "建物ファシリティマネジメント用のデジタルツイン。ライフサイクル管理や修繕履歴の紐付けによる、建物の省エネ・運用効率最適化。",
                "sales_hint": "L3-L4の建物保全業務に対し、Tandemを用いた空間・アセットの一元的なFM運用と、将来的なスマートビルディング化を推進。"
            }
        }
        
        # Filter UI
        selected_dept = st.selectbox("表示する部門でフィルタリング", ["すべて", "生産技術", "工場建築・建設"], key="super_admin_solution_dept")
        
        for qid, info in product_mapping.items():
            if selected_dept != "すべて" and info["dept"] != selected_dept:
                continue
                
            with st.container(border=True):
                st.markdown(f"####  **{qid}**  **{info['dept']} - {info['phase']}**")
                st.markdown(f"**設問概要:** {info['title']}")
                
                # Product Badge Style
                st.markdown(
                    f'<div style="background-color: #1A1A1A; border-left: 4px solid #FFFF00; padding: 12px; margin: 10px 0; border-radius: 4px;">'
                    f'<span style="color: #FFFF00; font-weight: bold; font-size: 0.85rem; letter-spacing: 0.05em; text-transform: uppercase;"> 提案対象 Autodesk 製品</span><br>'
                    f'<span style="color: #FFFFFF; font-weight: 600; font-size: 1.05rem;">{info["products"]}</span>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
                
                col_v, col_s = st.columns(2)
                with col_v:
                    st.markdown("** バリューピッチ（価値訴求）:**")
                    st.write(info["value_pitch"])
                with col_s:
                    st.markdown("** セールスヒント（レベル別提案）:**")
                    st.write(info["sales_hint"])

    # --- Tab 4: システムステータス ---
    with tabs[3]:
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
