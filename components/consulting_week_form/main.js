(() => {
  "use strict";

  const app = document.getElementById("app");
  const RESPONDENT_KEY = "consulting_week_2026_respondent_id";
  const ANSWERS_KEY = "consulting_week_2026_answers";
  const DIRTY_KEY = "consulting_week_2026_dirty";
  const ACTIVE_PART_KEY = "consulting_week_2026_active_part";
  const LANGUAGE_KEY = "consulting_week_2026_language";
  const MIN_SYNC_INTERVAL_MS = 5000;
  const SYNC_DEBOUNCE_MS = 1000;
  const AUTO_ADVANCE_DELAY_MS = 1800;

  let renderArgs = null;
  let eventConfig = null;
  let logoDataUri = "";
  let respondentId = "";
  let answers = {};
  let dirty = new Set();
  let activePart = Number(localStorage.getItem(ACTIVE_PART_KEY) || "1");
  let language = localStorage.getItem(LANGUAGE_KEY) === "en" ? "en" : "ja";
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
  const advanceTimers = new Map();

  const COPY = {
    ja: {
      purpose: "各セッションについて、タイトルから抱いた期待と、実際に聞いた後の実感を記録する簡素なフォームです。登壇者のランキングを目的としたものではありません。聞いていない発表はスキップできます。",
      autoSaveLabel: "自動保存について",
      noSubmit: "Submitボタンはありません",
      autoSaveBody: "入力内容はすぐにこの端末へ保存され、一定間隔で自動同期されます。同じ端末・ブラウザから開くと続きから回答できます。",
      dirty: "端末に保存済み",
      skipped: "聞いていない",
      answered: "回答済み",
      partial: "入力途中",
      unanswered: "未回答",
      offline: "オフライン・端末保存済み",
      retrying: "同期を再試行します",
      synced: "同期済み",
      checking: "前回回答を確認中",
      expectation: "タイトルからの期待",
      actual: "聞いた後の実感",
      sliderHint: "中央の丸を動かして採点",
      sliderAria: "未評価・中央位置",
      skip: "この発表は聞いていない",
      savePending: "端末に保存済み・同期待ち",
      saveSynced: "サーバー同期済み",
      savePrompt: "入力すると端末へ保存されます",
      progress: "回答済み",
      eventNav: "イベント構成",
      partNav: "部を切り替える",
      allComplete: "16セッションの入力が完了しました",
      noSendNeeded: "送信操作は必要ありません",
      completeSynced: "すべてサーバーへ同期済みです。これで完了です。画面を閉じて大丈夫です。",
      completePending: "回答は端末へ保存済みです。上の表示が「同期済み」になれば、画面を閉じて大丈夫です。",
      incompleteBody: "入力のたびに端末へ保存され、変更分だけがまとめて同期されます。途中で閉じても同じブラウザから続けられます。",
      privacy: "氏名、メールアドレス、会社名、自由記述は収集しません。回答者は他の回答や集計結果を閲覧できません。",
    },
    en: {
      purpose: "Record your expectations from each session title and how the session felt afterward. This is not a presenter ranking. Skip any session you did not attend.",
      autoSaveLabel: "About automatic saving",
      noSubmit: "No Submit button needed",
      autoSaveBody: "Your answers are saved on this device immediately and synced automatically. Reopen this page in the same browser to continue.",
      dirty: "Saved on this device",
      skipped: "Not attended",
      answered: "Answered",
      partial: "In progress",
      unanswered: "Not answered",
      offline: "Offline · saved on device",
      retrying: "Sync will retry",
      synced: "Synced",
      checking: "Checking previous answers",
      expectation: "Expectation from the title",
      actual: "After-session impression",
      sliderHint: "Move the center circle to rate",
      sliderAria: "Not rated · center position",
      skip: "I did not attend this session",
      savePending: "Saved on device · waiting to sync",
      saveSynced: "Synced to server",
      savePrompt: "Your input will be saved on this device",
      progress: "answered",
      eventNav: "Event sections",
      partNav: "Switch section",
      allComplete: "All 16 sessions are complete",
      noSendNeeded: "No submission action is needed",
      completeSynced: "Everything is synced. You may close this page.",
      completePending: "Your answers are saved on this device. Please wait until the status shows “Synced” before closing.",
      incompleteBody: "Each change is saved on this device and synced automatically. You can close the page and continue later in the same browser.",
      privacy: "We do not collect names, email addresses, company names, or free-text comments. Respondents cannot view other answers or aggregate results.",
    },
  };

  const t = (key) => COPY[language][key] || COPY.ja[key] || key;
  const partName = (part) => language === "en" ? `Part ${part}` : `第${part}部`;

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
      syncError = language === "en"
        ? "Could not sync. Your answers remain on this device."
        : (response.error || "同期できませんでした。");
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
      language,
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
      language,
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

  const cancelScheduledAdvance = (sessionId) => {
    const timer = advanceTimers.get(sessionId);
    if (timer) window.clearTimeout(timer);
    advanceTimers.delete(sessionId);
  };

  const scheduleAdvance = (sessionId) => {
    cancelScheduledAdvance(sessionId);
    const answer = answers[sessionId];
    if (!isComplete(answer)) return;
    const expectedUpdatedAt = answer.client_updated_at;
    const timer = window.setTimeout(() => {
      advanceTimers.delete(sessionId);
      const session = eventConfig.sessions.find(
        (candidate) => candidate.session_id === sessionId,
      );
      if (
        !session
        || activePart !== session.part
        || !expanded.has(sessionId)
        || !isComplete(answers[sessionId])
        || answers[sessionId].client_updated_at !== expectedUpdatedAt
      ) {
        return;
      }
      advanceToNextIncomplete(sessionId);
      renderApp();
    }, AUTO_ADVANCE_DELAY_MS);
    advanceTimers.set(sessionId, timer);
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
    if (answer[field] !== value) {
      answer[field] = value;
      answer[timestampField] = nowIso();
      markChanged(sessionId);
    }

    const range = document.querySelector(
      `input[data-session="${CSS.escape(sessionId)}"][data-field="${field}"]`,
    );
    const valueNode = document.querySelector(
      `[data-value-for="${CSS.escape(sessionId)}-${field}"]`,
    );
    const hintNode = document.querySelector(
      `[data-hint-for="${CSS.escape(sessionId)}-${field}"]`,
    );
    if (range) range.classList.remove("unanswered");
    if (range) range.setAttribute("aria-valuetext", String(value));
    if (valueNode) {
      valueNode.textContent = String(value);
      valueNode.classList.remove("unanswered");
    }
    if (hintNode) hintNode.hidden = true;
    if (finalChange) {
      if (isComplete(answer)) scheduleAdvance(sessionId);
      if (!wasComplete && isComplete(answer)) renderApp();
    }
  };

  const primeRangeFromPointer = (range, event) => {
    if (
      range.disabled
      || (event.button !== undefined && event.button !== 0)
    ) {
      return;
    }
    const bounds = range.getBoundingClientRect();
    if (!bounds.width) return;
    const ratio = Math.min(
      1,
      Math.max(0, (event.clientX - bounds.left) / bounds.width),
    );
    const minimum = Number(range.min);
    const maximum = Number(range.max);
    const step = Number(range.step) || 1;
    const rawValue = minimum + ratio * (maximum - minimum);
    const nextValue = Math.round(rawValue / step) * step;
    range.value = String(
      Math.min(maximum, Math.max(minimum, nextValue)),
    );
    updateSlider(
      range.dataset.session,
      range.dataset.field,
      range.value,
      false,
    );
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
    if (dirty.has(sessionId)) return { text: t("dirty"), kind: "dirty" };
    if (answer.skipped) return { text: t("skipped"), kind: "complete" };
    if (isComplete(answer)) return { text: t("answered"), kind: "complete" };
    if (isPartial(answer)) return { text: t("partial"), kind: "partial" };
    return { text: t("unanswered"), kind: "" };
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
          <span class="slider-value ${unanswered ? "unanswered" : ""}"
            data-value-for="${escapeHtml(sessionId)}-${field}">
            ${unanswered ? "-" : value}
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
            aria-valuetext="${unanswered ? escapeHtml(t("sliderAria")) : value}"
            ${answer.skipped ? "disabled" : ""}
          >
          <span aria-hidden="true">10</span>
        </div>
        <span class="slider-hint"
          data-hint-for="${escapeHtml(sessionId)}-${field}"
          ${unanswered ? "" : "hidden"}>
          ${escapeHtml(t("sliderHint"))}
        </span>
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
      ? t("savePending")
      : (hasSavedContent ? t("saveSynced") : t("savePrompt"));

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
            <span class="session-title">${escapeHtml(
              language === "en" ? (session.title_en || session.title) : session.title
            )}</span>
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
            ${sliderHtml(sessionId, "expectation_score", t("expectation"), answer)}
            ${sliderHtml(sessionId, "actual_score", t("actual"), answer)}
            <label class="skip-row">
              <input type="checkbox"
                data-skip="${escapeHtml(sessionId)}"
                ${answer.skipped ? "checked" : ""}>
              <span>${escapeHtml(t("skip"))}</span>
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
      ? t("offline")
      : syncError
        ? t("retrying")
        : (dirty.size || sending)
          ? t("dirty")
          : renderArgs?.server_bundle?.loaded
            ? t("synced")
            : t("checking");

    app.innerHTML = `
      <div class="shell">
        <header class="brand-header">
          <img class="brand-logo" src="${escapeHtml(logoDataUri)}" alt="Autodesk">
          <span class="header-actions">
            <span class="event-kicker">Internal Event · 28 JUL 2026</span>
            <span class="language-toggle" role="group" aria-label="Language">
              <button type="button" data-language="ja"
                aria-pressed="${language === "ja"}">JP</button>
              <button type="button" data-language="en"
                aria-pressed="${language === "en"}">EN</button>
            </span>
          </span>
        </header>

        <h1>${escapeHtml(eventConfig.display_name)}</h1>
        <p class="purpose">${escapeHtml(t("purpose"))}</p>

        <section class="auto-save-note" aria-label="${escapeHtml(t("autoSaveLabel"))}">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12.5l4 4L19 6.5" stroke="currentColor" stroke-width="2.2"
              stroke-linecap="square" stroke-linejoin="miter"/>
            <path d="M3 3h18v18H3z" stroke="currentColor" stroke-width="1.4"/>
          </svg>
          <div>
            <strong>${escapeHtml(t("noSubmit"))}</strong>
            <p>${escapeHtml(t("autoSaveBody"))}</p>
          </div>
        </section>

        <section class="answer-summary" data-state="${global.state}" aria-live="polite">
          <span>${compactSyncLabel}</span>
          <span>${total.complete} / ${total.total} ${escapeHtml(t("progress"))}</span>
        </section>

        <div class="progress-track" aria-hidden="true">
          <div class="progress-fill" style="width:${(total.complete / total.total) * 100}%"></div>
        </div>

        <nav class="part-tabs" role="tablist" aria-label="${escapeHtml(t("eventNav"))}">
          ${[1, 2, 3].map((part) => {
            const progress = progressForPart(part);
            return `
              <button class="part-tab"
                type="button"
                role="tab"
                data-part="${part}"
                aria-selected="${part === activePart}">
                <span class="part-name">${partName(part)}</span>
                <span class="part-count">${progress.complete} / ${progress.total}</span>
              </button>
            `;
          }).join("")}
        </nav>

        <section role="tabpanel" aria-label="${partName(activePart)}">
          <div class="part-heading">
            <h2>${partName(activePart)}</h2>
            <span>${partProgress.complete} / ${partProgress.total} ${escapeHtml(t("progress"))}</span>
          </div>
          <div class="session-list">
            ${activeSessions.map(cardHtml).join("")}
          </div>
          <nav class="part-bottom-nav" aria-label="${escapeHtml(t("partNav"))}">
            ${[1, 2, 3].map((part) => `
              <button type="button"
                data-part="${part}"
                ${part === activePart ? "disabled" : ""}>
                ${partName(part)}
              </button>
            `).join("")}
          </nav>
        </section>

        <section class="completion-card ${safelySynced ? "complete" : ""}">
          <h3>${allComplete ? t("allComplete") : t("noSendNeeded")}</h3>
          <p>
            ${safelySynced
              ? t("completeSynced")
              : allComplete
                ? t("completePending")
                : t("incompleteBody")}
          </p>
        </section>

        <p class="footer-note">
          ${escapeHtml(t("privacy"))}
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
    document.querySelectorAll("[data-language]").forEach((button) => {
      button.addEventListener("click", () => {
        language = button.dataset.language === "en" ? "en" : "ja";
        localStorage.setItem(LANGUAGE_KEY, language);
        document.documentElement.lang = language;
        renderApp();
      });
    });
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
        range.dataset.interactionFinalized = "false";
      };
      const finalizeInteraction = () => {
        if (range.dataset.interactionFinalized === "true") return;
        range.dataset.interactionFinalized = "true";
        const wasComplete = range.dataset.completeBefore === "true";
        delete range.dataset.completeBefore;
        updateSlider(
          range.dataset.session,
          range.dataset.field,
          range.value,
          true,
          wasComplete,
        );
      };
      range.addEventListener("pointerdown", rememberCompletion);
      range.addEventListener("pointerdown", (event) => {
        cancelScheduledAdvance(range.dataset.session);
        primeRangeFromPointer(range, event);
      });
      range.addEventListener("pointerup", finalizeInteraction);
      range.addEventListener("keydown", rememberCompletion);
      range.addEventListener("keydown", () => {
        cancelScheduledAdvance(range.dataset.session);
      });
      range.addEventListener("input", () => {
        updateSlider(range.dataset.session, range.dataset.field, range.value, false);
      });
      range.addEventListener("change", finalizeInteraction);
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
