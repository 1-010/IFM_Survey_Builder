import sqlite3
import pandas as pd
import streamlit as st
import datetime
import uuid

DB_PATH = "H:/AI/AgentHub/ledger/context.sqlite"

def load_data():
    conn = sqlite3.connect(DB_PATH)
    try:
        # Load active agents
        agents_df = pd.read_sql_query(
            "SELECT agent_id, display_name, agent_type, host, role FROM agents WHERE active = 1", conn
        )
        
        # Load latest usage reports for each agent and window_key
        query = """
        SELECT r.* FROM agent_usage_reports r
        INNER JOIN (
            SELECT agent_id, window_key, MAX(ts) as max_ts
            FROM agent_usage_reports
            GROUP BY agent_id, window_key
        ) latest ON r.agent_id = latest.agent_id AND r.window_key = latest.window_key AND r.ts = latest.max_ts
        ORDER BY r.ts DESC
        """
        reports_df = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Failed to read from AgentHub database: {e}")
        agents_df = pd.DataFrame()
        reports_df = pd.DataFrame()
    finally:
        conn.close()
    return agents_df, reports_df

def save_report(agent_id, provider, window_key, window_label, used_percent, note):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        report_id = f"usage_{uuid.uuid4().hex[:16]}"
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        cur.execute(
            """
            INSERT INTO agent_usage_reports 
            (id, ts, agent_id, provider, window_key, window_label, metric_kind, used_value, remaining_value, limit_value, unit, used_percent, available, source, note, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, 'quota_percent', ?, ?, 100.0, 'percent', ?, 1, 'manual', ?, '{}')
            """,
            (report_id, ts, agent_id, provider, window_key, window_label, used_percent, 100.0 - used_percent, used_percent, note)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Failed to write to database: {e}")
        return False
    finally:
        conn.close()

def render_page():
    st.subheader("🔋 Agent Limits & Usage Dashboard")
    st.write("AgentHubのDB（`ledger/context.sqlite`）から、各エージェントの API クォータ・消費枠（週制限・5時間制限など）の最新状況を横断的に集計表示しています。")
    
    agents_df, reports_df = load_data()
    
    if agents_df.empty:
        st.warning("登録されているエージェントが見つかりません。")
        return
        
    st.markdown("### 🛰️ エージェント別消費クォータ一覧")
    
    for _, agent in agents_df.iterrows():
        agent_id = agent["agent_id"]
        # Skip human
        if agent_id == "human-hidenari":
            continue
            
        agent_reports = reports_df[reports_df["agent_id"] == agent_id]
        
        with st.container(border=True):
            col_info, col_weekly, col_5hr = st.columns([2, 2, 2])
            
            with col_info:
                st.markdown(f"##### 🤖 **{agent['display_name']}**")
                st.caption(f"ID: `{agent_id}` | Host: `{agent['host'] or 'Unknown'}`")
                st.write(f"_{agent['role'] or 'No role specified'}_")
                
            # Filter reports
            weekly_rep = agent_reports[agent_reports["window_key"].str.contains("weekly", case=False, na=False)]
            five_hour_rep = agent_reports[agent_reports["window_key"].str.contains("five_hour", case=False, na=False)]
            
            # Fallback for old/sample keys
            if weekly_rep.empty:
                weekly_rep = agent_reports[agent_reports["window_key"].str.contains("secondary", case=False, na=False)]
            if five_hour_rep.empty:
                five_hour_rep = agent_reports[agent_reports["window_key"].str.contains("primary", case=False, na=False)]
                
            with col_weekly:
                st.markdown("**📅 週間制限 (Weekly Limit)**")
                if not weekly_rep.empty:
                    val = float(weekly_rep.iloc[0]["used_percent"])
                    note = weekly_rep.iloc[0]["note"] or ""
                    ts_str = weekly_rep.iloc[0]["ts"][:16].replace("T", " ")
                    
                    st.metric(label="消費率", value=f"{val:.1f} %", delta=f"{100-val:.1f}% 残り", delta_color="normal")
                    st.progress(val / 100.0)
                    st.caption(f"更新: {ts_str} | {note}")
                else:
                    st.info("データなし")
                    
            with col_5hr:
                st.markdown("**⚡ 5時間制限 (5-Hour Limit)**")
                if not five_hour_rep.empty:
                    val = float(five_hour_rep.iloc[0]["used_percent"])
                    note = five_hour_rep.iloc[0]["note"] or ""
                    ts_str = five_hour_rep.iloc[0]["ts"][:16].replace("T", " ")
                    
                    st.metric(label="消費率", value=f"{val:.1f} %", delta=f"{100-val:.1f}% 残り", delta_color="normal")
                    st.progress(val / 100.0)
                    st.caption(f"更新: {ts_str} | {note}")
                else:
                    st.info("データなし")
                    
    # Log Form Section
    st.markdown("---")
    st.markdown("### 📝 手動利用状況更新フォーム")
    st.write("設定画面のスクリーンショットなどの最新数値を、エージェントごとに手動でデータベースに上書き登録します。")
    
    with st.form("manual_usage_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            target_agent = st.selectbox(
                "対象エージェント",
                options=agents_df["agent_id"].tolist(),
                format_func=lambda x: f"{agents_df[agents_df['agent_id'] == x]['display_name'].values[0]} ({x})"
            )
        with col2:
            target_window = st.selectbox(
                "制限枠の種類",
                options=[
                    ("weekly", "週間枠 (Weekly Limit)"),
                    ("five_hour", "5時間枠 (5-Hour Limit)"),
                ],
                format_func=lambda x: x[1]
            )
        with col3:
            used_percent_val = st.slider("消費パーセンテージ (%)", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
            
        custom_note = st.text_input("備考メモ", placeholder="設定画面スクリーンショットより登録、等")
        
        submit_btn = st.form_submit_button("データベースに登録・反映する")
        
        if submit_btn:
            provider = "google" if "gemini" in target_agent or "antigravity" in target_agent else "anthropic" if "claude" in target_agent else "openai"
            # Map key correctly
            mapped_key = f"{target_agent.split('-')[0]}.{target_window[0]}"
            success = save_report(
                agent_id=target_agent,
                provider=provider,
                window_key=mapped_key,
                window_label=target_window[1],
                used_percent=used_percent_val,
                note=custom_note
            )
            if success:
                st.success(f"{target_agent} の {target_window[1]} を {used_percent_val}% として登録しました！")
                st.rerun()
