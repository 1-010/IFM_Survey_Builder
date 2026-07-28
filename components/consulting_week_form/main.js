(() => {
  "use strict";

  const app = document.getElementById("app");
  const RESPONDENT_KEY = "consulting_week_2026_respondent_id";
  const ANSWERS_KEY = "consulting_week_2026_answers";
  const DIRTY_KEY = "consulting_week_2026_dirty";
  const ACTIVE_PART_KEY = "consulting_week_2026_active_part";
  const MIN_SYNC_INTERVAL_MS = 5000;
  const SYNC_DEBOUNCE_MS = 1000;

  let renderArgs = null;
  let eventConfig = null;
  let logoDataUri = "";
  let respondentId = "";
  let answers = {};
  let dirty = new Set();
  let activePart = Number(localStorage.getItem(ACTIVE_PART_KEY) || "1");
  let expanded = new Set();
  let initialized = false;
  let hydrateSent = false;
  let sending = false;
  let syncError = "";
  let pendingActionId = "";
  let processedResponseId = "";
  let lastServerAttempt = 0;
  let syncTimer = null;
  let pendingScrollSessionId = "";

  const postStreamlit = (type, payload = {}) => {
    window.parent.postMessage(
      { isStreamlitMessage: true, type, ...payload },
      "*",
    );
  };

  const setComponentValue = (value) => {
    postStreamlit("streamlit:setComponentValue", { value });
  };

  const setFrameHeight = () => {
    const height = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight,
      640,
    );
    postStreamlit("streamlit:setFrameHeight", { height });
  };

  const actionId = () => {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
      const random = Math.random() * 16 | 0;
      const value = char === "x" ? random : (random & 0x3) | 0x8;
      return value.toString(16);
    });
  };

  const newRespondentId = () => actionId();

  const nowIso = () => new Date().toISOString();

  const safeJson = (raw, fallback) => {
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return fallback;
    }
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const timeValue = (isoValue) => new Intl.DateTimeFormat("ja-JP", {
    timeZone: eventConfig.timezone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(isoValue));

  const blankAnswer = () => ({
    expectation_score: null,
    actual_score: null,
    skipped: false,
    expectation_updated_at: null,
    actual_updated_at: null,
    client_updated_at: null,
    stash: null,
  });

  const normalizeLocalAnswer = (raw) => ({
    ...blankAnswer(),
    ...(raw && typeof raw === "object" ? raw : {}),
    expectation_score: Number.isInteger(raw?.expectation_score)
      ? raw.expectation_score
      : null,
    actual_score: Number.isInteger(raw?.actual_score)
      ? raw.actual_score
      : null,
    skipped: raw?.skipped === true,
  });

  const saveLocal = () => {
    localStorage.setItem(RESPONDENT_KEY, respondentId);
    localStorage.setItem(ANSWERS_KEY, JSON.stringify(answers));
    localStorage.setItem(DIRTY_KEY, JSON.stringify([...dirty]));
    localStorage.setItem(ACTIVE_PART_KEY, String(activePart));
  };

  const initializeState = () => {
    respondentId = localStorage.getItem(RESPONDENT_KEY) || newRespondentId();
    localStorage.setItem(RESPONDENT_KEY, respondentId);

    const storedAnswers = safeJson(localStorage.getItem(ANSWERS_KEY), {});
    const storedDirty = safeJson(localStorage.getItem(DIRTY_KEY), []);
    const allowedIds = new Set(eventConfig.sessions.map((session) => session.session_id));
    answers = {};
    eventConfig.sessions.forEach((session) => {
      answers[session.session_id] = normalizeLocalAnswer(
        storedAnswers[session.session_id],
      );
    });
    dirty = new Set(
      Array.isArray(storedDirty)
        ? storedDirty.filter((sessionId) => allowedIds.has(sessionId))
        : [],
    );
    if (![1, 2, 3].includes(activePart)) activePart = 1;

    const firstIncomplete = eventConfig.sessions.find(
      (session) => session.part === activePart && !isComplete(answers[session.session_id]),
    );
    if (firstIncomplete) expanded.add(firstIncomplete.session_id);
    saveLocal();
    initialized = true;
  };

  const isComplete = (answer) => Boolean(
    answer?.skipped
    || (
      answer?.expectation_score !== null
      && answer?.actual_score !== null
    ),
  );

  const isPartial = (answer) => Boolean(
    !answer?.skipped
    && (
      answer?.expectation_score !== null
      || answer?.actual_score !== null
    )
    && !isComplete(answer),
  );

  const mergeServerRecords = (records) => {
    if (!Array.isArray(records)) return;
    records.forEach((record) => {
      const sessionId = record.session_id;
      if (!(sessionId in answers)) return;
      const local = answers[sessionId];
      const serverTime = Date.parse(
        record.client_updated_at || record.updated_at || 0,
      );
      const localTime = Date.parse(local.client_updated_at || 0);
      if (!local.client_updated_at || serverTime > localTime) {
        answers[sessionId] = normalizeLocalAnswer({
          ...local,
          expectation_score: record.expectation_score,
          actual_score: record.actual_score,
          skipped: record.skipped,
          expectation_updated_at: record.expectation_updated_at,
          actual_updated_at: record.actual_updated_at,
          client_updated_at: record.client_updated_at || record.updated_at,
        });
        dirty.delete(sessionId);
      } else if (localTime > serverTime) {
        dirty.add(sessionId);
      }
    });
    saveLocal();
  };

  const applyAcknowledgements = (items) => {
    if (!Array.isArray(items)) return;
    items.forEach((item) => {
      const local = answers[item.session_id];
      if (
        local
        && Date.parse(local.client_updated_at || 0)
          === Date.parse(item.client_updated_at || 0)
        && (item.status === "updated" || item.status === "unchanged")
      ) {
        dirty.delete(item.session_id);
      }
    });
    saveLocal();
  };

  const processServerResponse = (bundle) => {
    const response = bundle?.response;
    if (!response || response.action_id === processedResponseId) return;
    processedResponseId = response.action_id;
    if (pendingActionId && response.action_id !== pendingActionId) return;

    sending = false;
    pendingActionId = "";
    if (!response.ok) {
      syncError = response.error || "同期できませんでした。";
      renderApp();
      scheduleSync(10000);
      return;
    }

    syncError = "";
    if (response.type === "sync") {
      mergeServerRecords(response.records);
      applyAcknowledgements(response.acknowledgements);
    } else {
      mergeServerRecords(response.records);
    }
    renderApp();
    if (dirty.size) scheduleSync();
  };

  const sendHydrate = () => {
    if (hydrateSent) return;
    hydrateSent = true;
    const id = actionId();
    pendingActionId = id;
    sending = true;
    setComponentValue({
      type: "hydrate",
      action_id: id,
      respondent_id: respondentId,
    });
    renderApp();
  };

  const dirtyEntries = () => [...dirty]
    .filter((sessionId) => answers[sessionId])
    .slice(0, 16)
    .map((sessionId) => {
      const answer = answers[sessionId];
      return {
        session_id: sessionId,
        expectation_score: answer.expectation_score,
        actual_score: answer.actual_score,
        skipped: answer.skipped,
        client_updated_at: answer.client_updated_at,
        expectation_updated_at: answer.expectation_updated_at,
        actual_updated_at: answer.actual_updated_at,
      };
    });

  const performSync = () => {
    if (sending || !dirty.size) return;
    if (!navigator.onLine) {
      renderApp();
      return;
    }
    const elapsed = Date.now() - lastServerAttempt;
    if (elapsed < MIN_SYNC_INTERVAL_MS) {
      scheduleSync(MIN_SYNC_INTERVAL_MS - elapsed);
      return;
    }
    const entries = dirtyEntries();
    if (!entries.length) return;

    const id = actionId();
    pendingActionId = id;
    sending = true;
    syncError = "";
    lastServerAttempt = Date.now();
    setComponentValue({
      type: "sync",
      action_id: id,
      respondent_id: respondentId,
      entries,
    });
    renderApp();
  };

  const scheduleSync = (delay = SYNC_DEBOUNCE_MS) => {
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(performSync, delay);
  };

  const markChanged = (sessionId) => {
    answers[sessionId].client_updated_at = nowIso();
    dirty.add(sessionId);
    syncError = "";
    saveLocal();
    scheduleSync();
  };

  const advanceToNextIncomplete = (sessionId) => {
    expanded.delete(sessionId);
    const current = eventConfig.sessions.find(
      (session) => session.session_id === sessionId,
    );
    if (!current) return;
    const nextIncomplete = eventConfig.sessions.find(
      (session) => (
        session.part === current.part
        && session.order > current.order
        && !isComplete(answers[session.session_id])
      ),
    ) || eventConfig.sessions.find(
      (session) => (
        session.part === current.part
        && !isComplete(answers[session.session_id])
      ),
    );
    if (!nextIncomplete) return;
    [...expanded].forEach((expandedId) => {
      const expandedSession = eventConfig.sessions.find(
        (session) => session.session_id === expandedId,
      );
      if (expandedSession?.part === current.part) {
        expanded.delete(expandedId);
      }
    });
    expanded.add(nextIncomplete.session_id);
    pendingScrollSessionId = nextIncomplete.session_id;
  };

  const updateSlider = (
    sessionId,
    field,
    rawValue,
    finalChange,
    wasComplete = false,
  ) => {
    const answer = answers[sessionId];
    if (!answer || answer.skipped) return;
    const value = Number(rawValue);
    const timestampField = field === "expectation_score"
      ? "expectation_updated_at"
      : "actual_updated_at";
    answer[field] = value;
    answer[timestampField] = nowIso();
    markChanged(sessionId);

    const range = document.querySelector(
      `input[data-session="${CSS.escape(sessionId)}"][data-field="${field}"]`,
    );
    const valueNode = document.querySelector(
      `[data-value-for="${CSS.escape(sessionId)}-${field}"]`,
    );
    if (range) range.classList.remove("unanswered");
    if (valueNode) valueNode.textContent = String(value);
    if (finalChange) {
      if (!wasComplete && isComplete(answer)) {
        advanceToNextIncomplete(sessionId);
      }
      renderApp();
    }
  };

  const toggleSkipped = (sessionId, checked) => {
    const answer = answers[sessionId];
    if (checked) {
      answer.stash = {
        expectation_score: answer.expectation_score,
        actual_score: answer.actual_score,
        expectation_updated_at: answer.expectation_updated_at,
        actual_updated_at: answer.actual_updated_at,
      };
      answer.expectation_score = null;
      answer.actual_score = null;
      answer.expectation_updated_at = null;
      answer.actual_updated_at = null;
      answer.skipped = true;
    } else {
      const stash = answer.stash || {};
      answer.expectation_score = stash.expectation_score ?? null;
      answer.actual_score = stash.actual_score ?? null;
      answer.expectation_updated_at = stash.expectation_updated_at ?? null;
      answer.actual_updated_at = stash.actual_updated_at ?? null;
      answer.skipped = false;
      answer.stash = null;
    }
    markChanged(sessionId);
    if (checked) advanceToNextIncomplete(sessionId);
    renderApp();
  };

  const progressForPart = (part) => {
    const sessions = eventConfig.sessions.filter((session) => session.part === part);
    const complete = sessions.filter(
      (session) => isComplete(answers[session.session_id]),
    ).length;
    return { complete, total: sessions.length };
  };

  const totalProgress = () => {
    const complete = eventConfig.sessions.filter(
      (session) => isComplete(answers[session.session_id]),
    ).length;
    return { complete, total: eventConfig.sessions.length };
  };

  const statusForCard = (sessionId) => {
    const answer = answers[sessionId];
    if (dirty.has(sessionId)) return { text: "端末に保存済み", kind: "dirty" };
    if (answer.skipped) return { text: "聞いていない", kind: "complete" };
    if (isComplete(answer)) return { text: "回答済み", kind: "complete" };
    if (isPartial(answer)) return { text: "入力途中", kind: "partial" };
    return { text: "未回答", kind: "" };
  };

  const globalStatus = () => {
    if (!navigator.onLine) {
      return {
        state: "offline",
        title: "端末に保存済み",
        detail: "オフラインです。接続が戻ると自動同期します。",
      };
    }
    if (syncError) {
      return {
        state: "error",
        title: "同期できませんでした",
        detail: "回答は端末に残っています。後で自動再試行します。",
      };
    }
    if (sending) {
      return {
        state: "syncing",
        title: "同期中",
        detail: "このままお待ちください。",
      };
    }
    if (dirty.size) {
      return {
        state: "pending",
        title: "端末に保存済み",
        detail: `${dirty.size}件をまとめて自動同期します。`,
      };
    }
    if (renderArgs?.server_bundle?.loaded) {
      return {
        state: "synced",
        title: "同期済み",
        detail: "Submit操作は不要です。",
      };
    }
    return {
      state: "local",
      title: "端末へ保存します",
      detail: "前回の回答を確認しています。",
    };
  };

  const sliderHtml = (sessionId, field, label, answer) => {
    const value = answer[field];
    const unanswered = value === null;
    return `
      <div class="slider-block">
        <div class="slider-label-row">
          <label class="slider-label" for="${escapeHtml(sessionId)}-${field}">
            ${escapeHtml(label)}
          </label>
          <span class="slider-value"
            data-value-for="${escapeHtml(sessionId)}-${field}">
            ${unanswered ? "未回答" : value}
          </span>
        </div>
        <div class="slider-scale">
          <span aria-hidden="true">0</span>
          <input
            id="${escapeHtml(sessionId)}-${field}"
            type="range"
            min="0"
            max="10"
            step="1"
            value="${unanswered ? 5 : value}"
            class="${unanswered ? "unanswered" : ""}"
            data-session="${escapeHtml(sessionId)}"
            data-field="${field}"
            aria-valuetext="${unanswered ? "未回答" : value}"
            ${answer.skipped ? "disabled" : ""}
          >
          <span aria-hidden="true">10</span>
        </div>
      </div>
    `;
  };

  const cardHtml = (session) => {
    const sessionId = session.session_id;
    const answer = answers[sessionId];
    const isExpanded = expanded.has(sessionId);
    const status = statusForCard(sessionId);
    const hasSavedContent = isComplete(answer) || isPartial(answer);
    const cardSaveClass = dirty.has(sessionId)
      ? "dirty"
      : (hasSavedContent ? "synced" : "");
    const cardSaveText = dirty.has(sessionId)
      ? "端末に保存済み・同期待ち"
      : (hasSavedContent ? "サーバー同期済み" : "入力すると端末へ保存されます");

    return `
      <article class="session-card"
        data-card-id="${escapeHtml(sessionId)}"
        data-complete="${isComplete(answer)}"
        data-dirty="${dirty.has(sessionId)}">
        <button class="card-head"
          type="button"
          data-toggle-card="${escapeHtml(sessionId)}"
          aria-expanded="${isExpanded}"
          aria-controls="body-${escapeHtml(sessionId)}">
          <span>
            <span class="session-order">SESSION ${session.order}</span>
            <span class="session-title">${escapeHtml(session.title)}</span>
            <span class="session-meta">
              <span>${escapeHtml(session.presenter)}</span>
              <span>${timeValue(session.start_at)}–${timeValue(session.end_at)}</span>
            </span>
          </span>
          <span class="head-status">
            <span class="status-chip ${status.kind}">${status.text}</span>
            <span class="chevron" aria-hidden="true"></span>
          </span>
        </button>
        ${isExpanded ? `
          <div class="card-body" id="body-${escapeHtml(sessionId)}">
            ${sliderHtml(sessionId, "expectation_score", "タイトルからの期待", answer)}
            ${sliderHtml(sessionId, "actual_score", "聞いた後の実感", answer)}
            <label class="skip-row">
              <input type="checkbox"
                data-skip="${escapeHtml(sessionId)}"
                ${answer.skipped ? "checked" : ""}>
              <span>この発表は聞いていない</span>
            </label>
            <div class="card-save-state ${cardSaveClass}">
              ${cardSaveText}
            </div>
          </div>
        ` : ""}
      </article>
    `;
  };

  const renderApp = () => {
    if (!initialized || !eventConfig) return;
    const partProgress = progressForPart(activePart);
    const total = totalProgress();
    const global = globalStatus();
    const activeSessions = eventConfig.sessions.filter(
      (session) => session.part === activePart,
    );
    const allComplete = total.complete === total.total;
    const safelySynced = allComplete && !dirty.size && !sending && !syncError;
    const compactSyncLabel = !navigator.onLine
      ? "オフライン・端末保存済み"
      : syncError
        ? "同期を再試行します"
        : (dirty.size || sending)
          ? "端末に保存済み"
          : renderArgs?.server_bundle?.loaded
            ? "同期済み"
            : "前回回答を確認中";

    app.innerHTML = `
      <div class="shell">
        <header class="brand-header">
          <img class="brand-logo" src="${escapeHtml(logoDataUri)}" alt="Autodesk">
          <span class="event-kicker">Internal Event · 28 JUL 2026</span>
        </header>

        <h1>${escapeHtml(eventConfig.display_name)}</h1>
        <p class="purpose">
          各セッションについて、タイトルから抱いた期待と、実際に聞いた後の実感を記録する簡素なフォームです。
          登壇者のランキングを目的としたものではありません。聞いていない発表はスキップできます。
        </p>

        <section class="auto-save-note" aria-label="自動保存について">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12.5l4 4L19 6.5" stroke="currentColor" stroke-width="2.2"
              stroke-linecap="square" stroke-linejoin="miter"/>
            <path d="M3 3h18v18H3z" stroke="currentColor" stroke-width="1.4"/>
          </svg>
          <div>
            <strong>Submitボタンはありません</strong>
            <p>
              入力内容はすぐにこの端末へ保存され、一定間隔で自動同期されます。
              同じ端末・ブラウザから開くと続きから回答できます。
            </p>
          </div>
        </section>

        <section class="answer-summary" data-state="${global.state}" aria-live="polite">
          <span>${compactSyncLabel}</span>
          <span>${total.complete} / ${total.total} 回答済み</span>
        </section>

        <div class="progress-track" aria-hidden="true">
          <div class="progress-fill" style="width:${(total.complete / total.total) * 100}%"></div>
        </div>

        <nav class="part-tabs" role="tablist" aria-label="イベント構成">
          ${[1, 2, 3].map((part) => {
            const progress = progressForPart(part);
            return `
              <button class="part-tab"
                type="button"
                role="tab"
                data-part="${part}"
                aria-selected="${part === activePart}">
                <span class="part-name">第${part}部</span>
                <span class="part-count">${progress.complete} / ${progress.total}</span>
              </button>
            `;
          }).join("")}
        </nav>

        <section role="tabpanel" aria-label="第${activePart}部">
          <div class="part-heading">
            <h2>第${activePart}部</h2>
            <span>${partProgress.complete} / ${partProgress.total} 回答済み</span>
          </div>
          <div class="session-list">
            ${activeSessions.map(cardHtml).join("")}
          </div>
          <nav class="part-bottom-nav" aria-label="部を切り替える">
            ${[1, 2, 3].map((part) => `
              <button type="button"
                data-part="${part}"
                ${part === activePart ? "disabled" : ""}>
                第${part}部
              </button>
            `).join("")}
          </nav>
        </section>

        <section class="completion-card ${safelySynced ? "complete" : ""}">
          <h3>${allComplete ? "16セッションの入力が完了しました" : "送信操作は必要ありません"}</h3>
          <p>
            ${safelySynced
              ? "すべてサーバーへ同期済みです。これで完了です。画面を閉じて大丈夫です。"
              : allComplete
                ? "回答は端末へ保存済みです。上の表示が「同期済み」になれば、画面を閉じて大丈夫です。"
                : "入力のたびに端末へ保存され、変更分だけがまとめて同期されます。途中で閉じても同じブラウザから続けられます。"}
          </p>
        </section>

        <p class="footer-note">
          氏名、メールアドレス、会社名、自由記述は収集しません。
          回答者は他の回答や集計結果を閲覧できません。
        </p>
      </div>
    `;

    bindInteractions();
    window.requestAnimationFrame(() => {
      setFrameHeight();
      if (pendingScrollSessionId) {
        const target = document.querySelector(
          `[data-card-id="${CSS.escape(pendingScrollSessionId)}"]`,
        );
        pendingScrollSessionId = "";
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  };

  const bindInteractions = () => {
    document.querySelectorAll("[data-part]").forEach((button) => {
      button.addEventListener("click", () => {
        activePart = Number(button.dataset.part);
        const firstIncomplete = eventConfig.sessions.find(
          (session) => session.part === activePart && !isComplete(answers[session.session_id]),
        );
        if (firstIncomplete) expanded.add(firstIncomplete.session_id);
        saveLocal();
        renderApp();
      });
    });

    document.querySelectorAll("[data-toggle-card]").forEach((button) => {
      button.addEventListener("click", () => {
        const sessionId = button.dataset.toggleCard;
        if (expanded.has(sessionId)) expanded.delete(sessionId);
        else {
          const selected = eventConfig.sessions.find(
            (session) => session.session_id === sessionId,
          );
          [...expanded].forEach((expandedId) => {
            const expandedSession = eventConfig.sessions.find(
              (session) => session.session_id === expandedId,
            );
            if (expandedSession?.part === selected?.part) {
              expanded.delete(expandedId);
            }
          });
          expanded.add(sessionId);
        }
        renderApp();
      });
    });

    document.querySelectorAll('input[type="range"][data-session]').forEach((range) => {
      const rememberCompletion = () => {
        range.dataset.completeBefore = String(
          isComplete(answers[range.dataset.session]),
        );
      };
      range.addEventListener("pointerdown", rememberCompletion);
      range.addEventListener("keydown", rememberCompletion);
      range.addEventListener("input", () => {
        updateSlider(range.dataset.session, range.dataset.field, range.value, false);
      });
      range.addEventListener("change", () => {
        const wasComplete = range.dataset.completeBefore === "true";
        delete range.dataset.completeBefore;
        updateSlider(
          range.dataset.session,
          range.dataset.field,
          range.value,
          true,
          wasComplete,
        );
      });
    });

    document.querySelectorAll("[data-skip]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        toggleSkipped(checkbox.dataset.skip, checkbox.checked);
      });
    });

    document.querySelector("[data-retry]")?.addEventListener("click", () => {
      syncError = "";
      lastServerAttempt = 0;
      performSync();
    });
  };

  const onRender = (args) => {
    renderArgs = args;
    eventConfig = args.event;
    logoDataUri = args.logo_data_uri || "";
    try {
      window.parent.document.title = eventConfig.display_name;
    } catch (_error) {
      // The form remains fully usable if a future host isolates component origins.
    }
    if (!initialized) initializeState();
    processServerResponse(args.server_bundle);
    renderApp();

    if (!args.server_bundle?.loaded) {
      sendHydrate();
    } else if (dirty.size && !sending) {
      scheduleSync();
    }
  };

  window.addEventListener("message", (event) => {
    if (event.data?.type === "streamlit:render") {
      onRender(event.data.args || {});
    }
  });

  window.addEventListener("online", () => {
    syncError = "";
    lastServerAttempt = 0;
    renderApp();
    performSync();
  });

  window.addEventListener("offline", renderApp);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && dirty.size) {
      performSync();
    }
  });

  new ResizeObserver(() => setFrameHeight()).observe(document.body);
  postStreamlit("streamlit:componentReady", { apiVersion: 1 });
  setFrameHeight();
})();
