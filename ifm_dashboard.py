import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import re

# Page Config
st.set_page_config(page_title="IFM Maturity Assessment", layout="wide")
st.title("🏭 IFM Maturity Assessment System")
st.markdown("IFM（Integrated Factory Management）の成熟度自己診断システムです。現状のレベルと将来の目標を可視化します。")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"

@st.cache_data
def load_questions():
    if not DATA_JSON.exists():
        st.error(f"質問定義ファイルが見つかりません: {DATA_JSON}")
        return pd.DataFrame()
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data["questions"])

q_df = load_questions()

# Google Sheets Helper Functions
def get_gspread_client():
    if "gserviceaccount" not in st.secrets:
        st.error("Streamlit Secrets に Google Service Account の情報が設定されていません。")
        return None
    
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        creds_dict = dict(st.secrets["gserviceaccount"])
        # PEMキーの改行コードの表記のブレを補正
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").replace("\r\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google IAM 認証エラー: {e}")
        return None

def get_worksheet():
    client = get_gspread_client()
    if not client:
        return None
        
    spreadsheet_id = st.secrets["gserviceaccount"].get("spreadsheet_id")
    if not spreadsheet_id:
        st.error("Secrets に spreadsheet_id が定義されていません。")
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
    except Exception as e:
        sa_email = st.secrets["gserviceaccount"].get("client_email", "サービスアカウント")
        st.error(f"スプレッドシートへのアクセスに失敗しました。")
        st.info(f"💡 対処法: スプレッドシートの右上にある「共有」ボタンを押し、以下のサービスアカウントを **「編集者」** として追加してください：\n\n`{sa_email}`")
        return None

def load_responses_from_sheets():
    ws = get_worksheet()
    if not ws:
        return pd.DataFrame()
        
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        # 数値へのキャスト。N/Aなどの文字列は NaN (欠損値) に変換されるため、平均値計算時に無視されます
        df["as_is"] = pd.to_numeric(df["as_is"], errors='coerce')
        df["to_be"] = pd.to_numeric(df["to_be"], errors='coerce')
        # メアドからドメインを抽出
        df["domain"] = df["email"].apply(lambda x: x.split("@")[-1].strip() if "@" in str(x) else "")
        return df
    except Exception as e:
        st.error(f"データの読み込み中にエラーが発生しました: {e}")
        return pd.DataFrame()

def save_response_to_sheets(response_records):
    ws = get_worksheet()
    if not ws:
        return False
    try:
        rows_to_append = []
        for r in response_records:
            rows_to_append.append([
                r["timestamp"],
                r["respondent"],
                r["email"],
                r["experience_years"],
                r["department"],
                r["team"],
                r["question_id"],
                r["phase"],
                r["as_is"], # スキップされた場合は "N/A"
                r["to_be"]  # スキップされた場合は "N/A"
            ])
        ws.append_rows(rows_to_append)
        return True
    except Exception as e:
        st.error(f"データの書き込み中にエラーが発生しました: {e}")
        return False

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email.strip()) is not None

if q_df.empty:
    st.stop()

# Tabs
tab_input, tab_dashboard = st.tabs(["📝 アンケート回答入力", "📊 結果分析ダッシュボード"])

### 📝 Tab 1: アンケート回答入力 ###
with tab_input:
    st.header("アンケート回答フォーム")
    st.info("お名前、メールアドレス、勤続年数を入力のうえ、各設問に対する現状の評価と将来の目標を回答してください。")
    
    # ユーザー属性入力
    with st.container(border=True):
        st.subheader("1. 回答者情報の入力（必須）")
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
            
    st.subheader("2. 各フェーズの成熟度診断")
    st.markdown("各業務セクションの設問を読み、現在のレベルと将来目指す目標のレベルを選択してください。  \n※ご自身の担当外や該当しない設問は「**自身の職務には該当しない**」を選択することでスキップできます。")
    
    # 部門でフィルタリングせず、一括で表示（カテゴリごとにヘッダーで区切る）
    questions_by_dept = q_df.groupby("department")
    
    # ユーザーの入力を一時保存するセッション用辞書
    responses_to_save = {}
    
    # 動的なUI制御のため、formを使わずに個々のウィジェットとして作成し、最後に送信ボタンを置く
    for dept_name, group in questions_by_dept:
        st.markdown(f"### ➡️ {dept_name} 部門の設問")
        
        for _, row in group.iterrows():
            qid = row['question_id']
            with st.container(border=True):
                # 設問文の表示 (スプレッドシートのI列)
                st.markdown(f"#### **{row['phase']}** ({qid})")
                st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:5px; margin-bottom:10px;'>{row['question_text']}</div>", unsafe_allow_html=True)
                
                # スキップトグル
                skip = st.toggle("自身の職務には該当しない (この設問をスキップ)", key=f"skip_{qid}")
                
                # レベル定義の表示
                levels_df = pd.DataFrame([
                    {"レベル": "L1", "定義": row['levels']['L1']},
                    {"レベル": "L2", "定義": row['levels']['L2']},
                    {"レベル": "L3", "定義": row['levels']['L3']},
                    {"レベル": "L4", "定義": row['levels']['L4']},
                    {"レベル": "L5", "定義": row['levels']['L5']}
                ])
                st.dataframe(levels_df.set_index("レベル"), use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    as_is = st.slider(
                        f"現状の評価 - {row['phase']}", 
                        1, 5, 2, 
                        key=f"asis_{qid}", 
                        disabled=skip
                    )
                with col2:
                    to_be = st.slider(
                        f"将来の目標 - {row['phase']}", 
                        1, 5, 4, 
                        key=f"tobe_{qid}", 
                        disabled=skip
                    )
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
    # 送信エリア
    st.markdown("---")
    submit_clicked = st.button("回答を送信してスプレッドシートに保存する", type="primary", use_container_width=True)
    
    if submit_clicked:
        # バリデーション
        if not respondent_name.strip():
            st.error("❌ 回答者名を入力してください。")
        elif not email_input.strip() or not is_valid_email(email_input):
            st.error("❌ 有効なメールアドレスを入力してください。")
        elif not experience_years:
            st.error("❌ 勤続年数を選択してください。")
        else:
            timestamp = datetime.now().isoformat()
            records = []
            
            for _, row in q_df.iterrows():
                qid = row['question_id']
                is_skipped = st.session_state[f"skip_{qid}"]
                
                records.append({
                    "timestamp": timestamp,
                    "respondent": respondent_name.strip(),
                    "email": email_input.strip(),
                    "experience_years": experience_years,
                    "department": row['department'],
                    "team": specific_team.strip(),
                    "question_id": qid,
                    "phase": row['phase'],
                    "as_is": "N/A" if is_skipped else st.session_state[f"asis_{qid}"],
                    "to_be": "N/A" if is_skipped else st.session_state[f"tobe_{qid}"]
                })
                
            with st.spinner("スプレッドシートに送信中..."):
                if save_response_to_sheets(records):
                    st.success("🎉 回答がGoogleスプレッドシートへ正常に保存されました！「📊 結果分析ダッシュボード」タブに切り替えて集計結果を確認してください。")


### 📊 Tab 2: 結果分析ダッシュボード ###
with tab_dashboard:
    st.header("成熟度アセスメントの分析・比較")
    
    # リアルタイムで回答を読み込み
    resp_df = load_responses_from_sheets()
    
    if resp_df.empty:
        st.warning("まだ回答データがないか、スプレッドシートの取得に失敗しています。「📝 アンケート回答入力」タブでの回答送信、またはスプレッドシートの共有設定を確認してください。")
    else:
        # グループ比較モード
        st.subheader("📊 絞り込みとグループ比較")
        compare_mode = st.checkbox("👥 2つのグループを比較する（比較モード）", value=False)
        
        # フィルターオプション用のユニーク値リスト
        unique_domains = sorted([str(d) for d in resp_df['domain'].unique() if d and pd.notna(d)])
        unique_years = ["すべて", "0～2年", "2～5年", "5～10年", "10～15年", "15年以上"]
        
        # フィルター適用関数
        def filter_data(data, domain, exp, team_kw, category):
            filtered = data.copy()
            if domain != "すべて":
                filtered = filtered[filtered['domain'] == domain]
            if exp != "すべて":
                filtered = filtered[filtered['experience_years'] == exp]
            if team_kw.strip():
                # フリーワードでチーム・部署名を部分一致検索
                filtered = filtered[filtered['team'].str.contains(team_kw.strip(), case=False, na=False)]
            if category == "生産技術のみ":
                filtered = filtered[filtered['department'] == "生産技術"]
            elif category == "工場建築・建設のみ":
                filtered = filtered[filtered['department'] == "工場建築・建設"]
            return filtered

        # フィルターUIの構築
        if compare_mode:
            col_filter_a, col_filter_b = st.columns(2)
            
            with col_filter_a:
                st.markdown("#### 🔵 グループA の条件")
                domain_a = st.selectbox("ドメイン (グループA)", ["すべて"] + unique_domains, key="domain_a")
                exp_a = st.selectbox("勤続年数 (グループA)", unique_years, key="exp_a")
                team_a = st.text_input("部署名（部分一致・グループA）", key="team_a", placeholder="例: 技術部")
                cat_a = st.radio("表示カテゴリ (グループA)", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="cat_a", horizontal=True)
                
            with col_filter_b:
                st.markdown("#### 🟠 グループB の条件")
                domain_b = st.selectbox("ドメイン (グループB)", ["すべて"] + unique_domains, key="domain_b")
                exp_b = st.selectbox("勤続年数 (グループB)", unique_years, key="exp_b")
                team_b = st.text_input("部署名（部分一致・グループB）", key="team_b", placeholder="例: 建築")
                cat_b = st.radio("表示カテゴリ (グループB)", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="cat_b", horizontal=True)
                
            # データのフィルタリング
            df_a = filter_data(resp_df, domain_a, exp_a, team_a, cat_a)
            df_b = filter_data(resp_df, domain_b, exp_b, team_b, cat_b)
            
        else:
            # 通常の単一フィルターモード
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                domain_a = st.selectbox("メールアドレスのドメイン", ["すべて"] + unique_domains, key="single_domain")
            with col_f2:
                exp_a = st.selectbox("勤続年数", unique_years, key="single_exp")
            with col_f3:
                team_a = st.text_input("部署名（部分一致で検索）", key="single_team", placeholder="例: 生産技術")
                
            cat_a = st.radio("表示カテゴリ", ["両方", "生産技術のみ", "工場建築・建設のみ"], key="single_cat", horizontal=True)
            
            df_a = filter_data(resp_df, domain_a, exp_a, team_a, cat_a)
            df_b = pd.DataFrame() # 空

        # レーダーチャートプロット関数
        def plot_radar_comparison(df_group_a, df_group_b, is_compare):
            fig = go.Figure()
            
            # 各問に対する平均値を集計（N/A値は pandas の mean で自動的に除外されます）
            agg_a = df_group_a.groupby(['question_id', 'phase'])[['as_is', 'to_be']].mean().reset_index()
            # 軸が途切れないようにソート
            agg_a = agg_a.sort_values('question_id')
            
            theta_labels = [f"{row['phase']}\n({row['question_id']})" for _, row in agg_a.iterrows()]
            
            if not agg_a.empty:
                # グループA (As-Is)
                fig.add_trace(go.Scatterpolar(
                    r=agg_a['as_is'].tolist() + [agg_a['as_is'].tolist()[0]],
                    theta=theta_labels + [theta_labels[0]],
                    fill='toself',
                    name='グループA: 現状の評価',
                    line_color='#1f77b4', # 青
                    opacity=0.5
                ))
                # グループA (To-Be)
                fig.add_trace(go.Scatterpolar(
                    r=agg_a['to_be'].tolist() + [agg_a['to_be'].tolist()[0]],
                    theta=theta_labels + [theta_labels[0]],
                    fill='toself',
                    name='グループA: 将来の目標',
                    line_color='#aec7e8', # 水色
                    opacity=0.3
                ))
                
            if is_compare and not df_group_b.empty:
                agg_b = df_group_b.groupby(['question_id', 'phase'])[['as_is', 'to_be']].mean().reset_index()
                agg_b = agg_b.sort_values('question_id')
                theta_labels_b = [f"{row['phase']}\n({row['question_id']})" for _, row in agg_b.iterrows()]
                
                if not agg_b.empty:
                    # グループB (As-Is)
                    fig.add_trace(go.Scatterpolar(
                        r=agg_b['as_is'].tolist() + [agg_b['as_is'].tolist()[0]],
                        theta=theta_labels_b + [theta_labels_b[0]],
                        fill='toself',
                        name='グループB: 現状の評価',
                        line_color='#ff7f0e', # オレンジ
                        opacity=0.5
                    ))
                    # グループB (To-Be)
                    fig.add_trace(go.Scatterpolar(
                        r=agg_b['to_be'].tolist() + [agg_b['to_be'].tolist()[0]],
                        theta=theta_labels_b + [theta_labels_b[0]],
                        fill='toself',
                        name='グループB: 将来の目標',
                        line_color='#ffbb78', # 薄オレンジ
                        opacity=0.3
                    ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5],
                        tickmode='linear',
                        tick0=1,
                        dtick=1
                    )),
                showlegend=True,
                title="成熟度アセスメント レーダー比較",
                margin=dict(l=60, r=60, t=60, b=60),
                height=500
            )
            return fig

        # レーダーチャート表示
        st.markdown("### 📊 分析結果チャート")
        if df_a.empty and (not compare_mode or df_b.empty):
            st.warning("⚠️ 指定された条件に合致する回答データがありません。フィルターの条件を緩めてください。")
        else:
            fig = plot_radar_comparison(df_a, df_b, compare_mode)
            st.plotly_chart(fig, use_container_width=True)

        # 詳細のテーブル分析（グループAベース）
        st.markdown("---")
        st.markdown("### 📝 詳細アセスメントギャップ分析 (グループAの集計値)")
        
        if not df_a.empty:
            agg_a = df_a.groupby(['question_id', 'phase'])[['as_is', 'to_be']].mean().reset_index()
            merged_df = pd.merge(q_df, agg_a, on=["question_id", "phase"])
            
            # 各問ごとの平均を計算して、レベルとマッピング
            for _, row in merged_df.iterrows():
                avg_asis = row['as_is']
                avg_tobe = row['to_be']
                
                # いずれも NaN (該当全員がスキップ) の場合は表示を別にする
                if pd.isna(avg_asis) and pd.isna(avg_tobe):
                    with st.expander(f"【{row['department']}】 {row['phase']} ({row['question_id']}) : 全員が該当なしとしてスキップ"):
                        st.info("この設問はすべての選択回答者によってスキップされました。")
                    continue
                
                asis_str = f"{round(avg_asis, 1)}" if pd.notna(avg_asis) else "該当なし"
                tobe_str = f"{round(avg_tobe, 1)}" if pd.notna(avg_tobe) else "該当なし"
                
                with st.expander(f"【{row['department']}】 {row['phase']} ({row['question_id']}) : 現状の評価平均 {asis_str} ➡️ 将来の目標平均 {tobe_str}"):
                    st.write("**成熟度定義：**")
                    
                    levels_df = pd.DataFrame([
                        {"Level": "L1 (手作業)", "Description": row['levels']['L1']},
                        {"Level": "L2 (デジタル化)", "Description": row['levels']['L2']},
                        {"Level": "L3 (協力/部門間連携)", "Description": row['levels']['L3']},
                        {"Level": "L4 (管理/全社管理)", "Description": row['levels']['L4']},
                        {"Level": "L5 (卓越性/AI)", "Description": row['levels']['L5']}
                    ])
                    
                    closest_asis = round(avg_asis) if pd.notna(avg_asis) else 0
                    closest_tobe = round(avg_tobe) if pd.notna(avg_tobe) else 0
                    
                    def highlight_levels(row_val):
                        idx = row_val.name  # 行のインデックス (0〜4)
                        level_val = idx + 1 # インデックス0がL1、1がL2...に対応
                        styles = [''] * len(row_val)
                        if level_val == closest_asis and level_val == closest_tobe:
                            styles = ['background-color: rgba(255, 255, 0, 0.2); font-weight: bold'] * len(row_val)
                        elif level_val == closest_asis:
                            styles = ['background-color: rgba(0, 0, 255, 0.1); font-weight: bold'] * len(row_val)
                        elif level_val == closest_tobe:
                            styles = ['background-color: rgba(0, 255, 0, 0.1); font-weight: bold'] * len(row_val)
                        return styles
                    
                    styled_df = levels_df.style.apply(highlight_levels, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
