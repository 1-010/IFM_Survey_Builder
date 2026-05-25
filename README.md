# Trace Visualizer (MVP)

Streamlit UI that reads JSONL audit logs in `.ai-bridge/audit/`, the inbox files
(`inbox_claude.jsonl`, `inbox_gemini.jsonl`), and the structured trace JSON in
`.ai-bridge/traces/`. It surfaces both an **at-a-glance coordination dashboard**
(when does the human actually need to step in?) and a **trace-analysis suite**
(detours, wrong doors, human rescues, recoveries).

No live integration with Claude or Antigravity. Agents append events to the JSONL
files; the visualizer just reads.

## Run

From the `.ai-bridge/visualizer/` directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or with uv:

```bash
uv pip install -r requirements.txt
uv run streamlit run app.py
```

The default view is **🛰️ Command Center**. Use the sidebar radio to switch to
the analysis pages.

## Views

- **🛰️ Command Center** *(default)* — at-a-glance coordination status:
  - Top status bar — `→ Claude 待ち` / `→ Antigravity 待ち` / `✅ 両者アイドル`
    (decided by whether the latest message in each inbox has a `read_at` field),
    plus age of the most recent activity.
  - Left: 🔴 human review queue — unread Claude-inbox messages with
    `needs_review: true`. Empty (green panel) means nothing for the human to do.
  - Right: 💬 recent messages — last 5 messages across both inboxes, with a 🔴
    icon on items flagged for review.
  - Bottom (collapsed): tasks & metrics — active `task_id`s with their last
    event, plus event count / detour ratio / first-correct-door latency from
    `audit/action_events.jsonl`.
  - Auto-refresh: 15s normally, 5s when the review queue is non-empty.
- **Timeline** — chronological events table + phase strip. Color = outcome.
- **File path graph** — order in which targets were touched. Bigger node = touched more.
- **Sankey** — phase → outcome flow. Where each phase routed.
- **Heatmap** — target × outcome counts and waste ratio per target.
- **Metrics detail** — all six metrics with definitions, plus the structured trace JSON if selected.
- **Approvals & tasks** — `approval_events.jsonl` and `task_events.jsonl` raw views.

## Sample data

Loads `audit/sample_task_events.jsonl` by default — the T-001 VRED companion-anchor
trace, with one wrong door (ComfyUI custom-node scan), one scope explosion (broad
glob), one human rescue (redirect to `vred_runtime/companion_anchor.py`), and a
clean recovery → patch → tests-green path.
