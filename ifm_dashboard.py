import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Page Config
st.set_page_config(page_title="IFM Maturity Assessment", layout="wide")
st.title("🏭 IFM Maturity Assessment System")
st.markdown("IFM（Integrated Factory Management）のアンケート回答フォームと、成熟度の可視化ダッシュボードが一体化したシステムです。")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
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
        # secrets.tomlから認証情報を辞書として取得
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
        # 「成熟度回答」ワークシートを取得、無ければ作成
        try:
            worksheet = sh.worksheet("成熟度回答")
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="成熟度回答", rows="100", cols="8")
            # ヘッダー書き込み
            worksheet.append_row(["timestamp", "respondent", "department", "team", "question_id", "phase", "as_is", "to_be"])
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
        # 型のキャスト
        df["as_is"] = pd.to_numeric(df["as_is"], errors='coerce')
        df["to_be"] = pd.to_numeric(df["to_be"], errors='coerce')
        return df
    except Exception as e:
        st.error(f"データの読み込み中にエラーが発生しました: {e}")
        return pd.DataFrame()

def save_response_to_sheets(response_records):
    ws = get_worksheet()
    if not ws:
        return False
    try:
        # response_records は辞書のリスト
        rows_to_append = []
        for r in response_records:
            rows_to_append.append([
                r["timestamp"],
                r["respondent"],
                r["department"],
                r["team"],
                r["question_id"],
                r["phase"],
                r["as_is"],
                r["to_be"]
            ])
        ws.append_rows(rows_to_append)
        return True
    except Exception as e:
        st.error(f"データの書き込み中にエラーが発生しました: {e}")
        return False

if q_df.empty:
    st.stop()

# Tabs
tab_input, tab_dashboard = st.tabs(["📝 アンケート回答入力", "📊 結果ダッシュボード"])

### 📝 Tab 1: アンケート回答入力 ###
with tab_input:
    st.header("アンケート回答フォーム")
    st.info("あなたの所属する部門を選択し、各業務フェーズの現状（As-Is）と目標（To-Be）のレベルを回答してください。")
    
    # ユーザー属性入力
    with st.container(border=True):
        st.subheader("1. 属性情報の入力")
        respondent_name = st.text_input("回答者名（任意）", placeholder="例: 佐々木 秀成")
        # 質問定義に存在する部門から選択
        available_depts = list(q_df['department'].unique())
        selected_dept = st.selectbox("回答する部門（カテゴリ）", available_depts)
        specific_team = st.text_input("具体的なチーム名（任意）", placeholder="例: 第一生産技術部")
        
    st.subheader("2. 設問への回答")
    st.write("各レベルの定義を参考に、現状と目標を選択してください。")
    
    # 選択された部門の質問をフィルタリング
    dept_questions = q_df[q_df['department'] == selected_dept]
    
    # セッションステートを利用して一括保存用の辞書を作成
    responses_to_save = []
    
    with st.form("assessment_form"):
        for _, row in dept_questions.iterrows():
            st.markdown(f"#### 【{row['phase']}】 ({row['question_id']})")
            
            # レベル定義の表示
            levels_df = pd.DataFrame([
                {"レベル": "L1", "定義": row['levels']['L1']},
                {"レベル": "L2", "定義": row['levels']['L2']},
                {"レベル": "L3", "定義": row['levels']['L3']},
                {"レベル": "L4", "定義": row['levels']['L4']},
                {"レベル": "L5", "定義": row['levels']['L5']}
            ])
            st.table(levels_df.set_index("レベル"))
            
            col1, col2 = st.columns(2)
            with col1:
                as_is = st.slider(f"現状 (As-Is) - {row['phase']}", 1, 5, 2, key=f"asis_{row['question_id']}")
            with col2:
                to_be = st.slider(f"目標 (To-Be) - {row['phase']}", 1, 5, 4, key=f"tobe_{row['question_id']}")
            
            st.markdown("---")
            
        submitted = st.form_submit_button("回答を送信してスプレッドシートに保存する", type="primary")
        
        if submitted:
            timestamp = datetime.now().isoformat()
            
            records = []
            for _, row in dept_questions.iterrows():
                qid = row['question_id']
                ans_asis = st.session_state[f"asis_{qid}"]
                ans_tobe = st.session_state[f"tobe_{qid}"]
                
                records.append({
                    "timestamp": timestamp,
                    "respondent": respondent_name,
                    "department": selected_dept,
                    "team": specific_team,
                    "question_id": qid,
                    "phase": row['phase'],
                    "as_is": ans_asis,
                    "to_be": ans_tobe
                })
                
            if save_response_to_sheets(records):
                st.success("🎉 回答がGoogleスプレッドシートへ正常に保存されました！「📊 結果ダッシュボード」タブから確認できます。")


### 📊 Tab 2: 結果ダッシュボード ###
with tab_dashboard:
    st.header("アセスメント結果の可視化")
    
    resp_df = load_responses_from_sheets()
    
    if resp_df.empty:
        st.warning("まだ回答データがないか、スプレッドシートの取得に失敗しています。「📝 アンケート回答入力」タブでの回答送信、またはスプレッドシートの共有設定を確認してください。")
    else:
        # Sidebar or top filters for dashboard
        st.markdown("#### フィルター")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            dash_dept = st.selectbox("表示する部門カテゴリ", ["すべて"] + list(resp_df['department'].unique()), key="dash_dept")
        
        if dash_dept != "すべて":
            dash_resp_df = resp_df[resp_df['department'] == dash_dept]
        else:
            dash_resp_df = resp_df

        st.markdown("### 📊 Department Maturity Radar")

        def plot_radar(title, dept_resp):
            fig = go.Figure()

            fig.add_trace(go.Scatterpolar(
                r=dept_resp['as_is'].tolist() + [dept_resp['as_is'].tolist()[0]],
                theta=dept_resp['phase'].tolist() + [dept_resp['phase'].tolist()[0]],
                fill='toself',
                name='Current (As-Is)',
                line_color='blue',
                opacity=0.6
            ))

            fig.add_trace(go.Scatterpolar(
                r=dept_resp['to_be'].tolist() + [dept_resp['to_be'].tolist()[0]],
                theta=dept_resp['phase'].tolist() + [dept_resp['phase'].tolist()[0]],
                fill='toself',
                name='Target (To-Be)',
                line_color='green',
                opacity=0.4
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
                title=title,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            return fig

        # 単純に指定されたフィルター範囲での平均値（Mean）を算出
        agg_df = dash_resp_df.groupby(['department', 'phase', 'question_id'])[['as_is', 'to_be']].mean().reset_index()

        departments = agg_df['department'].unique()
        cols = st.columns(len(departments) if len(departments) > 0 else 1)

        for i, dept in enumerate(departments):
            dept_data = agg_df[agg_df['department'] == dept]
            fig = plot_radar(f"{dept} の成熟度ギャップ (平均)", dept_data)
            cols[i % len(cols)].plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📝 Detailed Assessment Gap Analysis (平均値)")

        # Merge questions with aggregated responses
        merged_df = pd.merge(q_df, agg_df, on=["department", "question_id", "phase"])

        for _, row in merged_df.iterrows():
            avg_asis = round(row['as_is'], 1)
            avg_tobe = round(row['to_be'], 1)
            
            with st.expander(f"【{row['department']}】 {row['phase']} ({row['question_id']}) : As-Is 平均 {avg_asis} ➡️ To-Be 平均 {avg_tobe}"):
                st.write("**Maturity Scale Definitions:**")
                
                levels_df = pd.DataFrame([
                    {"Level": "L1 (手作業)", "Description": row['levels']['L1'], "L_val": 1},
                    {"Level": "L2 (デジタル化)", "Description": row['levels']['L2'], "L_val": 2},
                    {"Level": "L3 (協力/部門間連携)", "Description": row['levels']['L3'], "L_val": 3},
                    {"Level": "L4 (管理/全社管理)", "Description": row['levels']['L4'], "L_val": 4},
                    {"Level": "L5 (卓越性/AI)", "Description": row['levels']['L5'], "L_val": 5}
                ])
                
                # Highlight based on the closest integer to the average
                closest_asis = round(avg_asis)
                closest_tobe = round(avg_tobe)
                
                def highlight_levels(row_val):
                    styles = [''] * len(row_val)
                    if row_val['L_val'] == closest_asis and row_val['L_val'] == closest_tobe:
                        styles = ['background-color: rgba(255, 255, 0, 0.2); font-weight: bold'] * len(row_val) # Yellow for both
                    elif row_val['L_val'] == closest_asis:
                        styles = ['background-color: rgba(0, 0, 255, 0.1); font-weight: bold'] * len(row_val)
                    elif row_val['L_val'] == closest_tobe:
                        styles = ['background-color: rgba(0, 255, 0, 0.1); font-weight: bold'] * len(row_val)
                    return styles
                
                styled_df = levels_df.style.apply(highlight_levels, axis=1).hide(subset=['L_val'], axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
