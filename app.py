"""Streamlit visualizer for the Traceable Multi-Agent Collaboration Platform.

Run with:
    streamlit run .ai-bridge/visualizer/app.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from trace_loader import (
    get_available_logs,
    get_available_traces,
    load_action_events,
    load_approval_events,
    load_inbox,
    load_task_events,
    load_trace_json,
)
from metrics import calculate_metrics

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.append(str(ROOT / "scripts"))
try:
    from sanity_checker import run_sanity_check
except ImportError:
    run_sanity_check = None

st.set_page_config(page_title="AI Trace Visualizer", layout="wide")

AUDIT_DIR = ROOT / "audit"
TRACES_DIR = ROOT / "traces"
INSIGHTS_DIR = ROOT / "insights"
INBOX_CLAUDE = ROOT / "inbox_claude.jsonl"
INBOX_GEMINI = ROOT / "inbox_gemini.jsonl"


def _load_jsonl_safe(path: Path) -> list[dict]:
    """Read a JSONL file as a list of dicts. Bad lines are skipped."""
    if not path.exists():
        return []
    import json
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows

OUTCOME_COLORS = {
    "useful": "#4caf50",
    "resolution_step": "#2e7d32",
    "recovery": "#81c784",
    "detour": "#ff9800",
    "wrong_door": "#e53935",
    "rejected": "#b71c1c",
}
PHASE_ORDER = ["explore", "diagnose", "plan", "implement", "test", "review", "recover", "resolve"]


# ---------- sidebar ----------
st.sidebar.title("AI Trace Visualizer")
st.sidebar.caption("Observing wrong doors, recoveries, and human rescues.")

PAGES = [
    "🛰️ Command Center",
    "Timeline",
    "File path graph",
    "Sankey",
    "Heatmap",
    "Metrics detail",
    "Approvals & tasks",
    "Insights (passive)",
    "Provenance (passive)",
]
page = st.sidebar.radio("Page", PAGES, index=0)
st.sidebar.divider()

logs = get_available_logs(AUDIT_DIR)
if not logs:
    st.error(f"No JSONL logs found in {AUDIT_DIR}.")
    st.stop()

default_idx = 0
for i, p in enumerate(logs):
    if "sample_task_events" in p:
        default_idx = i
        break

selected_log = st.sidebar.selectbox(
    "Action events log",
    logs,
    index=default_idx,
    format_func=lambda p: Path(p).name,
)

df = load_action_events(selected_log)
if df.empty:
    st.warning("Selected log is empty.")
    st.stop()

task_options = ["(all tasks)"] + sorted(df["task_id"].dropna().unique().tolist())
selected_task = st.sidebar.selectbox("Filter by task", task_options)
if selected_task != "(all tasks)":
    task_df = df[df["task_id"] == selected_task].reset_index(drop=True)
else:
    task_df = df.reset_index(drop=True)

st.sidebar.divider()
st.sidebar.markdown("### Companion logs")
approval_path = AUDIT_DIR / "approval_events.jsonl"
task_path = AUDIT_DIR / "task_events.jsonl"
st.sidebar.write(f"approvals: {'yes' if approval_path.exists() else 'no'}")
st.sidebar.write(f"task_events: {'yes' if task_path.exists() else 'no'}")

trace_files = get_available_traces(TRACES_DIR)
selected_trace_json = None
if trace_files:
    pick = st.sidebar.selectbox(
        "Structured trace JSON",
        ["(none)"] + trace_files,
        format_func=lambda p: Path(p).name if p != "(none)" else p,
    )
    if pick != "(none)":
        selected_trace_json = load_trace_json(pick)

st.sidebar.divider()
st.sidebar.markdown("### Settings")
auto_refresh = st.sidebar.toggle("Auto-Refresh (10s)", value=False)
if auto_refresh:
    st_autorefresh(interval=10000, key="data_refresh")

st.sidebar.divider()
st.sidebar.markdown("### Reality Check")
st.sidebar.caption("Is the AI lost? Push this to force a self-reflection.")
if st.sidebar.button("🚨 Run Sanity Check", type="primary"):
    if run_sanity_check:
        st.session_state["sanity_prompt"] = run_sanity_check(lookback=5)
    else:
        st.sidebar.error("sanity_checker.py not found.")

if "sanity_prompt" in st.session_state:
    st.sidebar.markdown("**Copy and paste to AI:**")
    st.sidebar.code(st.session_state["sanity_prompt"], language="markdown")


# ---------- helpers ----------
def _row_style(row):
    color = OUTCOME_COLORS.get(str(row.get("outcome_label")), "")
    if not color:
        return [""] * len(row)
    return [f"background-color: {color}33"] * len(row)


def _is_unread(read_at) -> bool:
    """A message is unread if read_at is missing or empty."""
    if read_at is None:
        return True
    try:
        if pd.isna(read_at):
            return True
    except (TypeError, ValueError):
        pass
    s = str(read_at).strip()
    return s == "" or s.lower() in {"none", "nan", "nat"}


def _truthy(v) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes"}


def _human_age(ts) -> str:
    if ts is None:
        return "—"
    try:
        if pd.isna(ts):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(ts, str):
        ts = pd.to_datetime(ts, utc=True, errors="coerce")
        if pd.isna(ts):
            return "—"
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize("UTC")
    delta = datetime.now(timezone.utc) - ts.to_pydatetime()
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


# ---------- Command Center page ----------
if page == "🛰️ Command Center":
    st.title("🛰️ AI Coordination — Command Center")
    st.caption("At-a-glance view of the Claude ↔ Antigravity (Gemini) loop. Quiet means quiet.")

    inbox_claude_df = load_inbox(INBOX_CLAUDE, inbox_name="claude") if INBOX_CLAUDE.exists() else pd.DataFrame()
    inbox_gemini_df = load_inbox(INBOX_GEMINI, inbox_name="gemini") if INBOX_GEMINI.exists() else pd.DataFrame()

    def _latest_unread(df: pd.DataFrame):
        if df.empty:
            return None
        if "read_at" not in df.columns:
            return df.iloc[-1] if len(df) else None
        unread = df[df["read_at"].apply(_is_unread)]
        if unread.empty:
            return None
        return unread.iloc[-1]

    claude_unread = _latest_unread(inbox_claude_df)
    gemini_unread = _latest_unread(inbox_gemini_df)

    review_queue = pd.DataFrame()
    if not inbox_claude_df.empty and "needs_review" in inbox_claude_df.columns:
        review_queue = inbox_claude_df[
            inbox_claude_df["needs_review"].apply(_truthy)
            & inbox_claude_df["read_at"].apply(_is_unread)
        ].copy()

    # Status bar
    status_col, age_col = st.columns([3, 1])
    with status_col:
        if claude_unread is not None:
            st.markdown(
                "<div style='padding:18px;border-radius:8px;background:#fff3cd;"
                "border-left:6px solid #ff9800;font-size:22px;font-weight:600;'>"
                "→ Claude 待ち</div>",
                unsafe_allow_html=True,
            )
        elif gemini_unread is not None:
            st.markdown(
                "<div style='padding:18px;border-radius:8px;background:#e3f2fd;"
                "border-left:6px solid #1976d2;font-size:22px;font-weight:600;'>"
                "→ Antigravity 待ち</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='padding:18px;border-radius:8px;background:#e8f5e9;"
                "border-left:6px solid #2e7d32;font-size:22px;font-weight:600;'>"
                "✅ 両者アイドル</div>",
                unsafe_allow_html=True,
            )
    with age_col:
        timestamps = []
        for d in (inbox_claude_df, inbox_gemini_df):
            if not d.empty and "timestamp" in d.columns:
                last = d["timestamp"].dropna()
                if len(last):
                    timestamps.append(last.iloc[-1])
        latest_ts = max(timestamps) if timestamps else None
        st.metric("最終アクティビティ", _human_age(latest_ts))

    st.divider()

    # Middle row: review queue (left) + recent messages (right)
    left, right = st.columns([1, 1])

    with left:
        st.subheader("🔴 人間の判断キュー")
        if review_queue.empty:
            st.markdown(
                "<div style='padding:14px;border-radius:8px;background:#e8f5e9;"
                "border-left:6px solid #2e7d32;font-weight:600;'>"
                "✅ 人間の判断待ちはありません</div>",
                unsafe_allow_html=True,
            )
            st.caption("ここが空ならヒデナリは何もしなくていい。")
        else:
            for _, r in review_queue.iloc[::-1].iterrows():
                from_ = r.get("from", "?")
                type_ = r.get("type", "?")
                content = str(r.get("content", "") or "")
                snippet = content if len(content) <= 400 else content[:400] + "…"
                ts_age = _human_age(r.get("timestamp"))
                st.markdown(
                    f"<div style='padding:12px;margin-bottom:8px;border-radius:8px;"
                    f"background:#ffebee;border-left:6px solid #c62828;'>"
                    f"<div style='font-size:12px;color:#555;'>"
                    f"<b>{from_}</b> → claude · {type_} · {ts_age}</div>"
                    f"<div style='margin-top:6px;white-space:pre-wrap;'>{snippet}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with right:
        st.subheader("💬 最近のメッセージ")
        combined = pd.concat([inbox_claude_df, inbox_gemini_df], ignore_index=True)
        if combined.empty or "timestamp" not in combined.columns:
            st.info("inbox メッセージはまだありません。")
        else:
            recent = combined.sort_values("timestamp").tail(5).iloc[::-1]
            for _, r in recent.iterrows():
                from_ = r.get("from", "?")
                to_ = r.get("to", "?")
                type_ = r.get("type", "?")
                content = str(r.get("content", "") or "")
                snippet = content[:100] + ("…" if len(content) > 100 else "")
                ts_age = _human_age(r.get("timestamp"))
                review_icon = "🔴 " if _truthy(r.get("needs_review")) else ""
                st.markdown(
                    f"<div style='padding:8px 10px;margin-bottom:6px;border-radius:6px;"
                    f"background:#f5f5f5;border-left:3px solid #888;'>"
                    f"<div style='font-size:12px;color:#555;'>{review_icon}"
                    f"<b>{from_}</b> → {to_} · {type_} · {ts_age}</div>"
                    f"<div style='margin-top:4px;font-size:13px;'>{snippet}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Tasks & metrics (collapsed)
    with st.expander("📊 タスク & メトリクス", expanded=False):
        m_cc = calculate_metrics(task_df)
        ev_col, det_col, lat_col = st.columns(3)
        ev_col.metric("Events (selected log)", m_cc["total_events"])
        det_col.metric("Detour ratio (selected)", f"{m_cc['detour_ratio']:.0%}")
        lat_col.metric("First correct door", f"{m_cc['first_correct_door_latency']} steps")

        st.markdown("**アクティブ task_id と最終イベント** (audit/action_events.jsonl)")
        action_path_cc = AUDIT_DIR / "action_events.jsonl"
        if not action_path_cc.exists():
            st.info("audit/action_events.jsonl が見つかりません。")
        else:
            action_df = load_action_events(action_path_cc)
            if action_df.empty or "task_id" not in action_df.columns:
                st.info("action_events.jsonl が空、または task_id 列がありません。")
            else:
                detour_set = {"detour", "wrong_door", "rejected"}
                rows_tm = []
                for tid, group in action_df.groupby("task_id"):
                    if pd.isna(tid):
                        continue
                    g = group.sort_values("timestamp")
                    last = g.iloc[-1]
                    last_ts = last.get("timestamp")
                    if "outcome_label" in g.columns:
                        reviewed = g.dropna(subset=["outcome_label"])
                    else:
                        reviewed = pd.DataFrame()
                    if not reviewed.empty:
                        d_n = reviewed["outcome_label"].isin(detour_set).sum()
                        detour_ratio = f"{d_n / len(reviewed):.0%}"
                    else:
                        detour_ratio = "—"
                    last_outcome = last.get("outcome_label", pd.NA)
                    rows_tm.append({
                        "task_id": tid,
                        "events": len(g),
                        "last_event": last.get("event_id", ""),
                        "last_phase": last.get("phase", ""),
                        "last_outcome": str(last_outcome) if not pd.isna(last_outcome) else "—",
                        "last_ts": (
                            last_ts.strftime("%Y-%m-%d %H:%M")
                            if last_ts is not None and not pd.isna(last_ts) else "—"
                        ),
                        "age": _human_age(last_ts),
                        "reviewed": len(reviewed),
                        "detour_ratio": detour_ratio,
                    })
                if rows_tm:
                    tm_df = pd.DataFrame(rows_tm).sort_values("last_ts", ascending=False)
                    st.dataframe(tm_df, use_container_width=True, hide_index=True)
                else:
                    st.info("アクティブなタスクがありません。")

    # ---- Wake Lock (active) ----
    st.divider()
    st.subheader("🔒 Wake Lock — current decision")
    st.caption("Live evaluation of bridge_status.json via scripts/wake_lock.py. "
               "Shows WHY an agent is sleeping right now.")
    import sys as _sys, json as _json
    _sys.path.append(str(ROOT / "scripts"))
    try:
        from wake_lock import evaluate as _wake_eval  # type: ignore
    except Exception as e:
        _wake_eval = None
        st.error(f"wake_lock.py failed to import: {e}")

    bridge_status_path = ROOT / "bridge_status.json"
    if bridge_status_path.exists() and _wake_eval is not None:
        try:
            _bs = _json.loads(bridge_status_path.read_text(encoding="utf-8"))
        except Exception as e:
            _bs = None
            st.error(f"bridge_status.json parse error: {e}")
        if _bs is not None:
            agents = ["claude", "antigravity", "gpt"]
            cols = st.columns(len(agents))
            for col, agent in zip(cols, agents):
                d = _wake_eval(_bs, agent)
                bg = "#e8f5e9" if d.allowed else "#fff8e1"
                border = "#2e7d32" if d.allowed else "#f9a825"
                icon = "🟢 ALLOWED" if d.allowed else "🔒 SLEEPING"
                hold = d.hold_reason or "—"
                col.markdown(
                    f"<div style='padding:12px;border-radius:8px;"
                    f"background:{bg};border-left:6px solid {border};'>"
                    f"<div style='font-size:12px;color:#555;'><b>{agent}</b></div>"
                    f"<div style='margin-top:6px;font-weight:700;'>{icon}</div>"
                    f"<div style='margin-top:4px;font-size:12px;'>state: <code>{d.task_state}</code></div>"
                    f"<div style='margin-top:4px;font-size:12px;'>reason: <code>{d.reason}</code></div>"
                    f"<div style='margin-top:6px;font-size:13px;color:#444;'>"
                    f"<b>Why sleeping:</b> {hold}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.info("bridge_status.json not found — Wake Lock cannot evaluate.")

    # ---- Held Tasks (audit history) ----
    st.divider()
    st.subheader("⏸ Held Tasks (history)")
    st.caption("`task_state` is HOLD_* in audit/task_events.jsonl. Historical view; not the live wake decision.")
    task_rows = _load_jsonl_safe(AUDIT_DIR / "task_events.jsonl")
    held_latest: dict[str, dict] = {}
    for row in task_rows:
        state = str(row.get("task_state", "")).upper()
        if not state.startswith("HOLD_"):
            continue
        tid = row.get("task_id")
        if not tid:
            continue
        prev = held_latest.get(tid)
        if prev is None or str(row.get("timestamp", "")) >= str(prev.get("timestamp", "")):
            held_latest[tid] = row

    if not held_latest:
        st.markdown(
            "<div style='padding:10px;border-radius:6px;background:#e8f5e9;"
            "border-left:4px solid #2e7d32;'>HOLD中のタスクなし</div>",
            unsafe_allow_html=True,
        )
    else:
        for tid, row in held_latest.items():
            state = row.get("task_state", "")
            hold_reason = row.get("hold_reason") or row.get("summary", "")
            requested = row.get("requested_action", "")
            preferred = row.get("preferred_agent", "?")
            st.markdown(
                f"<div style='padding:12px;margin-bottom:8px;border-radius:8px;"
                f"background:#fff8e1;border-left:6px solid #f9a825;'>"
                f"<div style='font-size:12px;color:#555;'>"
                f"<b>{tid}</b> · state: <code>{state}</code> · preferred: {preferred}</div>"
                f"<div style='margin-top:6px;'><b>Hold reason:</b> {hold_reason}</div>"
                f"<div style='margin-top:4px;font-size:13px;color:#444;'>"
                f"<b>Requested:</b> {requested}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ---- Milestone Candidates (PASSIVE PLACEHOLDER) ----
    # Insight Router is not part of the active MVP. The block below intentionally
    # does not render rows — see the "Insights (passive)" page for the placeholder.

    # Auto-refresh: 5s if review queue non-empty, otherwise 15s.
    refresh_interval = 5000 if not review_queue.empty else 15000
    st_autorefresh(interval=refresh_interval, key="command_center_refresh")
    st.caption(
        f"自動更新: {refresh_interval // 1000}秒ごと"
        f"{'（🔴 人間の判断キューに項目あり — 高頻度モード）' if not review_queue.empty else ''}"
    )

    st.stop()


# ---------- header (analysis pages only) ----------
st.title("Traceable Multi-Agent Collaboration: Visualizer MVP")
st.caption(
    "Behavioral traces only. We do not extract chain-of-thought — we observe what each agent "
    "tried to read, run, or modify, and what the human decided."
)

m = calculate_metrics(task_df)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Events", m["total_events"])
c2.metric("First correct door", f"{m['first_correct_door_latency']} steps")
c3.metric("Detour ratio", f"{m['detour_ratio']:.0%}")
c4.metric("Backtracks", m["backtrack_count"])
c5.metric("Scope explosion", m["scope_explosion_score"])
c6.metric("Approval friction", f"{m['approval_friction_score']:.2f}")

c7, c8 = st.columns(2)
c7.metric("Human rescues", m["human_rescues"])
c8.metric("Human rescue Δ", f"{m['human_rescue_delta']:+.0%}")

st.divider()


# ---------- analysis pages ----------
if page == "Timeline":
    st.subheader("Timeline")
    st.caption("Chronological action events. Color = outcome label.")
    cols = [
        "event_id", "timestamp", "actor", "phase", "operation",
        "target", "outcome_label", "human_feedback", "outcome_notes",
    ]
    show = task_df[[c for c in cols if c in task_df.columns]].copy()
    if "timestamp" in show.columns:
        show["timestamp"] = show["timestamp"].dt.strftime("%H:%M:%S")
    st.dataframe(
        show.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    if "phase" in task_df.columns and "timestamp" in task_df.columns:
        st.markdown("**Phase strip**")
        strip = task_df.copy()
        strip["idx"] = range(len(strip))
        fig = px.scatter(
            strip,
            x="idx",
            y="phase",
            color="outcome_label",
            color_discrete_map=OUTCOME_COLORS,
            hover_data=["target", "declared_intent", "human_feedback"],
            category_orders={"phase": PHASE_ORDER},
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color="black")))
        fig.update_layout(height=320, xaxis_title="event index", yaxis_title="phase")
        st.plotly_chart(fig, use_container_width=True)


elif page == "File path graph":
    st.subheader("File / command access path")
    st.caption("Sequence of touched targets. Color = outcome. Bigger node = touched more often.")

    if "target" not in task_df.columns:
        st.info("No target column.")
    else:
        nodes = task_df["target"].fillna("(none)").tolist()
        labels = task_df["outcome_label"].fillna("").tolist()
        counts = pd.Series(nodes).value_counts().to_dict()

        # Plotly scatter with arrows between consecutive touches.
        xs = list(range(len(nodes)))
        ys = nodes
        fig = go.Figure()
        for i, (x, y, lab) in enumerate(zip(xs, ys, labels)):
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode="markers+text",
                marker=dict(
                    size=12 + 4 * counts.get(y, 1),
                    color=OUTCOME_COLORS.get(lab, "#888"),
                    line=dict(width=1, color="black"),
                ),
                text=[task_df.iloc[i].get("event_id", "")],
                textposition="top center",
                hovertext=(
                    f"{task_df.iloc[i].get('event_id','')}<br>"
                    f"phase: {task_df.iloc[i].get('phase','')}<br>"
                    f"op: {task_df.iloc[i].get('operation','')}<br>"
                    f"intent: {task_df.iloc[i].get('declared_intent','')}<br>"
                    f"outcome: {lab}"
                ),
                hoverinfo="text",
                showlegend=False,
            ))
        for i in range(len(nodes) - 1):
            fig.add_annotation(
                x=xs[i + 1], y=ys[i + 1],
                ax=xs[i], ay=ys[i],
                xref="x", yref="y", axref="x", ayref="y",
                arrowhead=2, arrowsize=1, arrowwidth=1, arrowcolor="#888",
                showarrow=True,
            )
        fig.update_layout(
            height=max(360, 28 * len(set(nodes)) + 120),
            xaxis_title="event order",
            yaxis_title="target",
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)


elif page == "Sankey":
    st.subheader("Phase → outcome flow")
    st.caption("Where does each phase route — useful path or detour?")

    if {"phase", "outcome_label"}.issubset(task_df.columns):
        flow = task_df.groupby(["phase", "outcome_label"]).size().reset_index(name="count")
        labels = list(dict.fromkeys(flow["phase"].tolist() + flow["outcome_label"].tolist()))
        idx = {label: i for i, label in enumerate(labels)}
        def _to_rgba(hex_color, alpha=0.6):
            h = hex_color.lstrip("#")
            if len(h) == 3: h = "".join(c+c for c in h)
            if len(h) != 6: return f"rgba(128,128,128,{alpha})"
            return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"

        link_colors = [
            _to_rgba(OUTCOME_COLORS.get(o, "#888")) for o in flow["outcome_label"]
        ]
        node_colors = [
            OUTCOME_COLORS.get(label, "#5b8dee") for label in labels
        ]
        sankey = go.Sankey(
            node=dict(label=labels, pad=20, thickness=18, color=node_colors),
            link=dict(
                source=[idx[p] for p in flow["phase"]],
                target=[idx[o] for o in flow["outcome_label"]],
                value=flow["count"].tolist(),
                color=link_colors,
            ),
        )
        fig = go.Figure(sankey)
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Phase or outcome_label missing.")


elif page == "Heatmap":
    st.subheader("Target × outcome heatmap")
    st.caption("Where the agent spent its attention vs whether it paid off.")

    if {"target", "outcome_label"}.issubset(task_df.columns):
        pivot = (
            task_df.groupby(["target", "outcome_label"]).size().unstack(fill_value=0)
        )
        # waste ratio
        useful_cols = [c for c in pivot.columns if c in {"useful", "recovery", "resolution_step"}]
        detour_cols = [c for c in pivot.columns if c in {"detour", "wrong_door", "rejected"}]
        pivot["_useful"] = pivot[useful_cols].sum(axis=1) if useful_cols else 0
        pivot["_detour"] = pivot[detour_cols].sum(axis=1) if detour_cols else 0
        pivot["waste_ratio"] = pivot["_detour"] / (pivot["_useful"] + pivot["_detour"]).replace(0, 1)

        st.markdown("**Counts**")
        display_cols = [c for c in pivot.columns if not c.startswith("_") and c != "waste_ratio"]
        fig = px.imshow(
            pivot[display_cols].T,
            aspect="auto",
            color_continuous_scale="Reds",
            labels=dict(x="target", y="outcome", color="count"),
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Waste ratio per target** (1.0 = pure detour, 0.0 = pure useful)")
        st.dataframe(
            pivot[["_useful", "_detour", "waste_ratio"]]
            .rename(columns={"_useful": "useful", "_detour": "detour"})
            .sort_values("waste_ratio", ascending=False)
            .style.background_gradient(subset=["waste_ratio"], cmap="Reds"),
            use_container_width=True,
        )
    else:
        st.info("Target or outcome_label missing.")


elif page == "Metrics detail":
    st.subheader("Metrics detail")
    st.caption("Definitions are in `.ai-bridge/visualizer/metrics.py`.")

    rows = [
        ("Total events", m["total_events"], "Count of action events in scope."),
        ("First correct door latency", m["first_correct_door_latency"],
         "1-based index of the first useful/recovery/resolution_step event."),
        ("Detour ratio", f"{m['detour_ratio']:.0%}",
         "(detour + wrong_door) / total events."),
        ("Wrong-door count", m["wrong_door_count"], "Events labeled wrong_door."),
        ("Detour count", m["detour_count"], "Events labeled detour."),
        ("Backtrack count", m["backtrack_count"],
         "Transitions from detour/wrong_door state into useful path."),
        ("Scope explosion score", m["scope_explosion_score"],
         "Search/read events whose target broadens (`**/*` or shallower depth)."),
        ("Human rescues", m["human_rescues"],
         "Rejected events that carried human feedback."),
        ("Human rescue Δ", f"{m['human_rescue_delta']:+.0%}",
         "Useful-rate after the last rescue minus before it."),
        ("Approval friction score", f"{m['approval_friction_score']:.2f}",
         "Approval requests / useful approved actions."),
    ]
    df_metrics = pd.DataFrame(rows, columns=["metric", "value", "definition"])
    df_metrics["value"] = df_metrics["value"].astype(str)
    st.dataframe(
        df_metrics,
        use_container_width=True,
        hide_index=True,
    )

    if selected_trace_json is not None:
        st.markdown("### Structured trace JSON")
        st.json(selected_trace_json)


elif page == "Approvals & tasks":
    col_a, col_t = st.columns(2)
    with col_a:
        st.subheader("Approvals")
        if approval_path.exists():
            adf = load_approval_events(approval_path)
            if not adf.empty:
                st.dataframe(adf, use_container_width=True, hide_index=True)
            else:
                st.info("approval_events.jsonl is empty.")
        else:
            st.info("No approval_events.jsonl yet.")

    with col_t:
        st.subheader("Task events")
        if task_path.exists():
            tdf = load_task_events(task_path)
            if not tdf.empty:
                st.dataframe(tdf, use_container_width=True, hide_index=True)
            else:
                st.info("task_events.jsonl is empty.")
        else:
            st.info("No task_events.jsonl yet.")


elif page == "Insights (passive)":
    st.subheader("Insights — PASSIVE SCAFFOLD")
    st.warning(
        "This tab is an inert placeholder. The Insight Router (capture → milestone → "
        "accept → distribute) is **not active** in the current MVP. Files exist so the "
        "shape is agreed across agents; nothing reads them automatically."
    )
    st.markdown(
        "**Files in scope (all passive):**\n"
        "- `insights/insight_log.jsonl`\n"
        "- `insights/milestone_candidates.jsonl`\n"
        "- `insights/accepted_insights.md`\n"
        "- `exports/context_delta_for_*.md`\n\n"
        "Activate in a later milestone — only after Wake Lock has proved itself in practice."
    )

elif page == "Provenance (passive)":
    st.subheader("Provenance — PASSIVE SCAFFOLD")
    st.warning(
        "This tab is an inert placeholder. The Reality-Anchored Judge / provenance fields "
        "(`schemas/action_event.schema.json` → `provenance`) are defined but **not consumed** "
        "by the active MVP. No automated trust-level rendering."
    )
    st.markdown(
        "**Defined but inert:**\n"
        "- `provenance.claimed_from / verified_from / transport_verified / human_pasted / "
        "source_tool / edited_by_human / trust_level`\n"
        "- `templates/reality_judge_template.md` (manual use only)\n"
        "- `Bias Declaration` blocks in `capabilities/*_capability_manifest.md`\n\n"
        "Activate when there is a concrete provenance dispute the team needs to resolve."
    )

st.divider()
st.caption(
    "MVP. No live integration with Claude or Antigravity — visualizer reads JSONL only. "
    "Agents are expected to append events themselves; the human is the final approver."
)
