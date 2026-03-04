function resolveApiBase() {
  const defaultHostedApi = "https://asserk-asseri.hf.space";
  const isGitHubPages =
    window.location.hostname === "asserkdev.github.io" &&
    window.location.pathname.toLowerCase().includes("/asseri-master");
  const isFirebaseHosting =
    window.location.hostname.endsWith(".web.app") || window.location.hostname.endsWith(".firebaseapp.com");
  const params = new URLSearchParams(window.location.search);
  const fromQuery = (params.get("api") || "").trim();
  const fromStorage = (localStorage.getItem("asseri_api_base") || "").trim();
  const fromWindow = (window.APP_API_BASE || "").trim();
  const fromFirebase = (window.ASSERI_FIREBASE_API_BASE || "").trim();
  const fromDefault = isFirebaseHosting ? (fromFirebase || defaultHostedApi) : isGitHubPages ? defaultHostedApi : "";
  const chosen = fromQuery || fromWindow || fromDefault || fromStorage;
  if (chosen) {
    localStorage.setItem("asseri_api_base", chosen);
  }
  return chosen.replace(/\/+$/, "");
}

const API_BASE = resolveApiBase();
const AUTH_TOKEN_KEY = "asseri_auth_token";
const AUTH_USER_KEY = "asseri_auth_user";
const DRAFT_KEY_PREFIX = "asseri_draft_";
const TONE_MODE_KEY = "asseri_tone_mode";
const UI_PREFS_KEY_PREFIX = "asseri_ui_prefs_";
const PROFILE_STORE_KEY_PREFIX = "asseri_profile_";

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

const api = {
  async json(url, options = {}) {
    const response = await fetch(apiUrl(url), options);
    const raw = await response.text();
    let payload = {};
    if (raw.trim()) {
      try {
        payload = JSON.parse(raw);
      } catch (_error) {
        payload = { detail: raw.slice(0, 500) };
      }
    }
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || `Request failed (${response.status})`);
    }
    return payload;
  },
};

const state = {
  authToken: null,
  userId: null,
  sessionId: null,
  sessions: [],
  lastAssistantTopic: null,
  messageCounter: 0,
  sessionTags: [],
  sessionPins: [],
  toneMode: "friendly",
  safetyActive: false,
  uiPrefs: {
    showConfidence: true,
    compactMessages: false,
    autoScroll: true,
  },
  profileData: {
    email: "",
    notes: "",
  },
};

const ui = {
  brandLogo: document.getElementById("brandLogo"),
  sessionsList: document.getElementById("sessionsList"),
  messages: document.getElementById("messages"),
  chatForm: document.getElementById("chatForm"),
  messageInput: document.getElementById("messageInput"),
  statusText: document.getElementById("statusText"),
  chatTitle: document.getElementById("chatTitle"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  loadingRow: document.getElementById("loadingRow"),
  authForm: document.getElementById("authForm"),
  authUsername: document.getElementById("authUsername"),
  authPassword: document.getElementById("authPassword"),
  signUpBtn: document.getElementById("signUpBtn"),
  signOutBtn: document.getElementById("signOutBtn"),
  authState: document.getElementById("authState"),
  authBadge: document.getElementById("authBadge"),
  safetyBadge: document.getElementById("safetyBadge"),
  toneSelect: document.getElementById("toneSelect"),
  applyToneBtn: document.getElementById("applyToneBtn"),
  continueBtn: document.getElementById("continueBtn"),
  regenerateBtn: document.getElementById("regenerateBtn"),
  exportBtn: document.getElementById("exportBtn"),
  deleteSessionBtn: document.getElementById("deleteSessionBtn"),
  profileBtn: document.getElementById("profileBtn"),
  pinsBtn: document.getElementById("pinsBtn"),
  tagsBtn: document.getElementById("tagsBtn"),
  goalsBtn: document.getElementById("goalsBtn"),
  searchInput: document.getElementById("searchInput"),
  searchBtn: document.getElementById("searchBtn"),
  profileCard: document.getElementById("profileCard"),
  profilePanel: document.querySelector(".profile-panel"),
  profileAvatar: document.getElementById("profileAvatar"),
  profileDisplayName: document.getElementById("profileDisplayName"),
  profileHint: document.getElementById("profileHint"),
  profileDetails: document.getElementById("profileDetails"),
  profileEmail: document.getElementById("profileEmail"),
  profileNotes: document.getElementById("profileNotes"),
  saveProfileBtn: document.getElementById("saveProfileBtn"),
  toggleConfidence: document.getElementById("toggleConfidence"),
  toggleCompact: document.getElementById("toggleCompact"),
  toggleAutoscroll: document.getElementById("toggleAutoscroll"),
  sidebar: document.getElementById("sidebar"),
  mobileMenuBtn: document.getElementById("mobileMenuBtn"),
  mobileSidebarBackdrop: document.getElementById("mobileSidebarBackdrop"),
};
ui.chatSendBtn = ui.chatForm ? ui.chatForm.querySelector("button[type='submit']") : null;

function setStatus(text) {
  ui.statusText.textContent = text;
}

function setSafetyBadge(active) {
  state.safetyActive = Boolean(active);
  if (!ui.safetyBadge) {
    return;
  }
  ui.safetyBadge.textContent = state.safetyActive ? "Safety: Active" : "Safety: Normal";
  ui.safetyBadge.classList.toggle("alert", state.safetyActive);
}

function setLoading(flag) {
  ui.loadingRow.classList.toggle("hidden", !flag);
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setMobileSidebarOpen(open) {
  const active = Boolean(open) && isMobileViewport();
  document.body.classList.toggle("mobile-sidebar-open", active);
  if (ui.mobileMenuBtn) {
    ui.mobileMenuBtn.setAttribute("aria-expanded", active ? "true" : "false");
  }
}

function closeMobileSidebar() {
  setMobileSidebarOpen(false);
}

function setStoredAuth(token, userId) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
  if (userId) {
    localStorage.setItem(AUTH_USER_KEY, userId);
  } else {
    localStorage.removeItem(AUTH_USER_KEY);
  }
}

function setStoredToneMode(tone) {
  if (!tone) {
    localStorage.removeItem(TONE_MODE_KEY);
    return;
  }
  localStorage.setItem(TONE_MODE_KEY, tone);
}

function currentProfileKey() {
  return String(state.userId || "guest").trim().toLowerCase() || "guest";
}

function uiPrefsKey() {
  return `${UI_PREFS_KEY_PREFIX}${currentProfileKey()}`;
}

function profileStoreKey() {
  return `${PROFILE_STORE_KEY_PREFIX}${currentProfileKey()}`;
}

function parseJsonSafe(raw, fallback) {
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return fallback;
  }
}

function clampBool(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }
  return fallback;
}

function loadUiPrefs() {
  const raw = localStorage.getItem(uiPrefsKey());
  const payload = raw ? parseJsonSafe(raw, {}) : {};
  state.uiPrefs = {
    showConfidence: clampBool(payload.showConfidence, true),
    compactMessages: clampBool(payload.compactMessages, false),
    autoScroll: clampBool(payload.autoScroll, true),
  };
}

function saveUiPrefs() {
  localStorage.setItem(uiPrefsKey(), JSON.stringify(state.uiPrefs));
}

function applyUiPrefs() {
  document.body.classList.toggle("compact-mode", Boolean(state.uiPrefs.compactMessages));
  document.body.classList.toggle("hide-confidence", !state.uiPrefs.showConfidence);
  if (ui.toggleConfidence) ui.toggleConfidence.checked = state.uiPrefs.showConfidence;
  if (ui.toggleCompact) ui.toggleCompact.checked = state.uiPrefs.compactMessages;
  if (ui.toggleAutoscroll) ui.toggleAutoscroll.checked = state.uiPrefs.autoScroll;
}

function loadProfileData() {
  const raw = localStorage.getItem(profileStoreKey());
  const payload = raw ? parseJsonSafe(raw, {}) : {};
  state.profileData = {
    email: typeof payload.email === "string" ? payload.email : "",
    notes: typeof payload.notes === "string" ? payload.notes : "",
  };
  if (ui.profileEmail) ui.profileEmail.value = state.profileData.email;
  if (ui.profileNotes) ui.profileNotes.value = state.profileData.notes;
}

function saveProfileData() {
  state.profileData = {
    email: ui.profileEmail ? String(ui.profileEmail.value || "").trim() : "",
    notes: ui.profileNotes ? String(ui.profileNotes.value || "").trim() : "",
  };
  localStorage.setItem(profileStoreKey(), JSON.stringify(state.profileData));
  setStatus("Profile notes saved.");
}

function syncProfileCard() {
  const name = state.userId || "Guest";
  const initials = name
    .replace(/[^a-z0-9]+/gi, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "G";
  if (ui.profileAvatar) ui.profileAvatar.textContent = initials;
  if (ui.profileDisplayName) ui.profileDisplayName.textContent = name;
  if (ui.profileHint) {
    ui.profileHint.textContent = state.authToken ? "Signed in profile" : "Guest profile (local)";
  }
}

function setProfileDetailsOpen(open) {
  if (!ui.profileDetails) {
    return;
  }
  ui.profileDetails.classList.toggle("hidden", !open);
  if (ui.profileCard) {
    ui.profileCard.classList.toggle("open", open);
  }
}

function initLogoFallback() {
  if (!ui.brandLogo) {
    return;
  }
  const candidates = [
    "./logo.svg",
    "logo.svg",
    "../logo.svg",
    "/logo.svg",
    "/asseri-master/logo.svg",
    "/asseri-master/docs/logo.svg",
    "/asseri-master/frontend/logo.svg",
    "./logo.png",
    "logo.png",
    "../logo.png",
    "/logo.png",
    "/asseri-master/logo.png",
    "/asseri-master/docs/logo.png",
    "/asseri-master/frontend/logo.png",
  ];
  let index = 0;
  ui.brandLogo.addEventListener("error", () => {
    index += 1;
    if (index < candidates.length) {
      ui.brandLogo.src = candidates[index];
    }
  });
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.authToken) {
    headers.Authorization = `Bearer ${state.authToken}`;
  }
  return headers;
}

function setChatEnabled(flag) {
  if (ui.newSessionBtn) ui.newSessionBtn.disabled = !flag;
  if (ui.messageInput) ui.messageInput.disabled = !flag;
  if (ui.continueBtn) ui.continueBtn.disabled = !flag;
  if (ui.regenerateBtn) ui.regenerateBtn.disabled = !flag;
  if (ui.exportBtn) ui.exportBtn.disabled = !flag;
  if (ui.deleteSessionBtn) ui.deleteSessionBtn.disabled = !flag;
  if (ui.profileBtn) ui.profileBtn.disabled = !flag;
  if (ui.pinsBtn) ui.pinsBtn.disabled = !flag;
  if (ui.tagsBtn) ui.tagsBtn.disabled = !flag;
  if (ui.goalsBtn) ui.goalsBtn.disabled = !flag;
  if (ui.searchInput) ui.searchInput.disabled = !flag;
  if (ui.searchBtn) ui.searchBtn.disabled = !flag;
  if (ui.chatSendBtn) {
    ui.chatSendBtn.disabled = !flag;
  }
  if (ui.toneSelect) ui.toneSelect.disabled = !flag;
  if (ui.applyToneBtn) ui.applyToneBtn.disabled = !flag;
}

function setAuthUI(isSignedIn) {
  if (isSignedIn && state.userId) {
    ui.authState.textContent = `Signed in as ${state.userId}`;
    ui.authBadge.textContent = state.userId;
    ui.signOutBtn.classList.remove("hidden");
    ui.signUpBtn.classList.add("hidden");
    ui.authUsername.value = state.userId;
    ui.authUsername.disabled = true;
    ui.authPassword.value = "";
    ui.authPassword.disabled = true;
    setChatEnabled(true);
    setSafetyBadge(false);
  closeMobileSidebar();
  } else {
    ui.authState.textContent = "Signed out";
    ui.authBadge.textContent = "Signed out";
    ui.signOutBtn.classList.add("hidden");
    ui.signUpBtn.classList.remove("hidden");
    ui.authUsername.disabled = false;
    ui.authPassword.disabled = false;
    setChatEnabled(false);
    setSafetyBadge(false);
  closeMobileSidebar();
  }
  syncProfileCard();
  loadUiPrefs();
  loadProfileData();
  applyUiPrefs();
}

function syncToneUI() {
  if (ui.toneSelect) {
    ui.toneSelect.value = state.toneMode;
  }
}

function clearMessages() {
  ui.messages.innerHTML = "";
  state.messageCounter = 0;
}

function draftKey() {
  const user = state.userId || "anon";
  const sid = state.sessionId || "new";
  return `${DRAFT_KEY_PREFIX}${user}_${sid}`;
}

function loadDraft() {
  ui.messageInput.value = localStorage.getItem(draftKey()) || "";
}

function saveDraft() {
  localStorage.setItem(draftKey(), ui.messageInput.value || "");
}

function clearDraft() {
  localStorage.removeItem(draftKey());
}

function formatTimeStamp(timestamp) {
  if (!timestamp) {
    return "";
  }
  const dt = new Date(timestamp);
  if (Number.isNaN(dt.getTime())) {
    return "";
  }
  return dt.toLocaleString();
}

function stripConfidenceText(text) {
  const lines = String(text || "").split(/\r?\n/);
  const kept = [];
  for (const line of lines) {
    const t = line.trim().toLowerCase();
    if (/^i'?m\s+\d+%\s+sure this is correct\.?$/.test(t)) {
      continue;
    }
    if (/^confidence:\s*\d+%$/.test(t)) {
      continue;
    }
    kept.push(line);
  }
  return kept.join("\n").trim();
}

function extractConfidenceFromText(text) {
  const raw = String(text || "");
  let match = raw.match(/confidence:\s*(\d+)%/i);
  if (match) {
    return Math.max(0, Math.min(100, Number(match[1])));
  }
  match = raw.match(/i'?m\s*(\d+)%\s*sure this is correct/i);
  if (match) {
    return Math.max(0, Math.min(100, Number(match[1])));
  }
  return null;
}

function formatAssistantText(payload) {
  const parts = [payload.answer || ""];
  const intent = String(payload.intent || "");
  const showTrace = localStorage.getItem("asseri_debug_trace") === "1";
  if (showTrace && Array.isArray(payload.reflection_steps) && payload.reflection_steps.length) {
    const steps = payload.reflection_steps.map((step, idx) => `${idx + 1}. ${step}`).join("\n");
    parts.push(`Reasoning trace:\n${steps}`);
  }
  const showRelated = intent === "knowledge" || intent === "problem_solving";
  if (showRelated && Array.isArray(payload.related_concepts) && payload.related_concepts.length) {
    const related = payload.related_concepts
      .slice(0, 4)
      .map((edge) => `${edge.source} ${edge.relation} ${edge.target}`)
      .join("\n");
    parts.push(`Related concepts:\n${related}`);
  }
  return parts.filter(Boolean).join("\n\n");
}

async function sendFeedback(signal, topic, note = "") {
  if (!state.sessionId || !state.authToken) {
    return;
  }
  try {
    await api.json("/api/chat/feedback", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        session_id: state.sessionId,
        topic: topic || null,
        signal,
        note,
      }),
    });
    setStatus(signal === "up" ? "Feedback saved (helpful)." : "Feedback saved (needs correction).");
  } catch (_error) {
    setStatus("Feedback could not be saved.");
  }
}

async function searchInSession(query) {
  const term = String(query || "").trim();
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!state.sessionId) {
    renderMessage("assistant", "Start a chat first.");
    return;
  }
  if (!term) {
    renderMessage("assistant", "Type a search term first.");
    return;
  }
  setStatus("Searching...");
  setLoading(true);
  try {
    const payload = await api.json(
      `/api/sessions/${encodeURIComponent(state.sessionId)}/search?q=${encodeURIComponent(term)}&limit=20`,
      { headers: authHeaders() }
    );
    const results = Array.isArray(payload.results) ? payload.results : [];
    if (!results.length) {
      renderMessage("assistant", `No messages matched "${term}" in this chat.`, [], { timestamp: new Date().toISOString() });
      return;
    }
    const lines = [`Search results for "${term}" (${results.length}):`];
    for (const item of results.slice(0, 10)) {
      const role = String(item.role || "").toUpperCase();
      const when = formatTimeStamp(item.timestamp || "");
      const excerpt = String(item.excerpt || "").replace(/\s+/g, " ").trim();
      lines.push(`- [${role}${when ? ` @ ${when}` : ""}] ${excerpt}`);
    }
    renderMessage(
      "assistant",
      lines.join("\n"),
      [{ title: "Session Search", url: "internal://session-search" }],
      { timestamp: new Date().toISOString() }
    );
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

function renderMessage(role, text, references = [], meta = null) {
  const el = document.createElement("article");
  el.className = `msg ${role}`;
  const cleanedText = role === "assistant" ? stripConfidenceText(text) : String(text || "");

  const body = document.createElement("div");
  body.className = "msg-body";
  body.textContent = cleanedText;
  el.appendChild(body);

  if (meta && typeof meta === "object") {
    if (role === "assistant" && typeof meta.confidence === "number" && state.uiPrefs.showConfidence) {
      const confidenceWrap = document.createElement("div");
      confidenceWrap.className = "confidence-wrap";
      confidenceWrap.title = `${meta.confidence}% confidence`;
      const confidenceMeter = document.createElement("div");
      confidenceMeter.className = "confidence-meter";
      const confidenceMarker = document.createElement("div");
      confidenceMarker.className = "confidence-marker";
      const pct = Math.max(0, Math.min(100, Number(meta.confidence)));
      confidenceMarker.style.left = `${pct}%`;
      confidenceMeter.appendChild(confidenceMarker);
      confidenceWrap.appendChild(confidenceMeter);
      el.appendChild(confidenceWrap);
    }
  }

  if (Array.isArray(references) && references.length) {
    const refs = document.createElement("div");
    refs.className = "refs";
    refs.innerHTML = "<strong>References:</strong><br>";
    for (const ref of references) {
      const title = ref.title || ref.url;
      if (typeof ref.url === "string" && (ref.url.startsWith("memory://") || ref.url.startsWith("internal://"))) {
        const row = document.createElement("span");
        row.textContent = `${title} (${ref.url})`;
        refs.appendChild(row);
      } else {
        const link = document.createElement("a");
        link.href = ref.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = title;
        refs.appendChild(link);
      }
      refs.appendChild(document.createElement("br"));
    }
    el.appendChild(refs);
  }

  if (role === "assistant") {
    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.className = "msg-action-btn";
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(cleanedText);
        setStatus("Copied.");
      } catch (_error) {
        setStatus("Copy failed.");
      }
    });
    actions.appendChild(copyBtn);

    if (Number.isInteger(meta && meta.messageIndex)) {
      const pinBtn = document.createElement("button");
      pinBtn.className = "msg-action-btn";
      pinBtn.type = "button";
      pinBtn.textContent = "Pin";
      pinBtn.addEventListener("click", async () => {
        await pinMessageAt(meta.messageIndex);
      });
      actions.appendChild(pinBtn);
    }

    const upBtn = document.createElement("button");
    upBtn.className = "msg-action-btn";
    upBtn.type = "button";
    upBtn.textContent = "Helpful";
    upBtn.addEventListener("click", async () => {
      await sendFeedback("up", meta && meta.topic ? meta.topic : state.lastAssistantTopic);
      upBtn.disabled = true;
      downBtn.disabled = true;
    });
    actions.appendChild(upBtn);

    const downBtn = document.createElement("button");
    downBtn.className = "msg-action-btn";
    downBtn.type = "button";
    downBtn.textContent = "Needs fix";
    downBtn.addEventListener("click", async () => {
      await sendFeedback("down", meta && meta.topic ? meta.topic : state.lastAssistantTopic);
      upBtn.disabled = true;
      downBtn.disabled = true;
    });
    actions.appendChild(downBtn);

    const timeEl = document.createElement("span");
    timeEl.className = "msg-time";
    timeEl.textContent = formatTimeStamp(meta && meta.timestamp ? meta.timestamp : new Date().toISOString());
    actions.appendChild(timeEl);
    el.appendChild(actions);
  } else if (role === "user") {
    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "msg-action-btn";
    editBtn.type = "button";
    editBtn.textContent = "Edit & resend";
    editBtn.addEventListener("click", async () => {
      const next = window.prompt("Edit your message before resending:", cleanedText);
      if (next === null) {
        return;
      }
      const revised = String(next || "").trim();
      if (!revised) {
        setStatus("Edit canceled.");
        return;
      }
      await sendChatMessage(revised);
    });
    actions.appendChild(editBtn);

    const copyBtn = document.createElement("button");
    copyBtn.className = "msg-action-btn";
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(cleanedText);
        setStatus("Copied.");
      } catch (_error) {
        setStatus("Copy failed.");
      }
    });
    actions.appendChild(copyBtn);

    if (Number.isInteger(meta && meta.messageIndex)) {
      const pinBtn = document.createElement("button");
      pinBtn.className = "msg-action-btn";
      pinBtn.type = "button";
      pinBtn.textContent = "Pin";
      pinBtn.addEventListener("click", async () => {
        await pinMessageAt(meta.messageIndex);
      });
      actions.appendChild(pinBtn);
    }

    const timeEl = document.createElement("span");
    timeEl.className = "msg-time";
    timeEl.textContent = formatTimeStamp(meta && meta.timestamp ? meta.timestamp : new Date().toISOString());
    actions.appendChild(timeEl);
    el.appendChild(actions);
  }

  ui.messages.appendChild(el);
  if (state.uiPrefs.autoScroll) {
    ui.messages.scrollTop = ui.messages.scrollHeight;
  }
}

function normalizeUserMessage(raw) {
  const text = raw.trim().replace(/\s+/g, " ");
  const lower = text.toLowerCase();
  if (lower === "this is wrong" || lower === "wrong") {
    return "that is wrong";
  }
  if (lower === "this is correct" || lower === "correct answer") {
    return "correct";
  }
  if (lower.startsWith("the correct answer is ")) {
    return `correct answer is ${text.slice("the correct answer is ".length)}`;
  }
  return text;
}

function isLikelySafetyMessage(text) {
  const low = String(text || "").toLowerCase();
  return (
    low.includes("cannot help with harmful or illegal actions") ||
    low.includes("cannot assist with violence or harm") ||
    low.includes("suicide & crisis lifeline") ||
    low.includes("call or text 988")
  );
}

async function applyToneMode(mode) {
  const valid = ["formal", "friendly", "casual", "chill", "direct"];
  const tone = String(mode || "").trim().toLowerCase();
  if (!valid.includes(tone)) {
    renderMessage("assistant", "Tone must be one of: formal, friendly, casual, chill, direct.");
    return;
  }
  state.toneMode = tone;
  setStoredToneMode(tone);
  syncToneUI();
  if (!state.authToken) {
    setStatus(`Tone set to ${tone} locally.`);
    return;
  }
  setStatus("Applying tone...");
  try {
    await api.json("/api/preferences/tone", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ tone }),
    });
    setStatus(`Tone set to ${tone}.`);
  } catch (error) {
    setStatus(`Tone saved locally, server apply failed: ${error.message}`);
  }
}

function renderSessions() {
  ui.sessionsList.innerHTML = "";
  for (const session of state.sessions) {
    const li = document.createElement("li");
    li.className = "session-item";
    const row = document.createElement("div");
    row.className = "session-row";

    const btn = document.createElement("button");
    btn.className = "session-open";
    const tags = Array.isArray(session.tags) && session.tags.length ? ` [${session.tags.slice(0, 2).join(", ")}]` : "";
    const pins = Number(session.pin_count || 0) > 0 ? ` #${session.pin_count}` : "";
    btn.textContent = `${session.title || session.session_id}${tags}${pins}`;
    if (session.session_id === state.sessionId) {
      btn.classList.add("active");
    }
    btn.addEventListener("click", () => {
      closeMobileSidebar();
      loadSession(session.session_id);
    });

    const delBtn = document.createElement("button");
    delBtn.className = "session-delete";
    delBtn.type = "button";
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await deleteSession(session.session_id);
    });

    row.appendChild(btn);
    row.appendChild(delBtn);
    li.appendChild(row);
    ui.sessionsList.appendChild(li);
  }
}

function resetChatState() {
  state.sessionId = null;
  state.sessions = [];
  state.lastAssistantTopic = null;
  state.sessionTags = [];
  state.sessionPins = [];
  setSafetyBadge(false);
  closeMobileSidebar();
  ui.chatTitle.textContent = "Session";
  clearMessages();
  renderSessions();
  loadDraft();
}

function forceSignedOut(note = "Please sign in to continue.") {
  state.authToken = null;
  state.userId = null;
  setStoredAuth(null, null);
  resetChatState();
  setAuthUI(false);
  setStatus("Signed out");
  renderMessage("assistant", note, [], { timestamp: new Date().toISOString() });
}

function isAuthError(error) {
  const txt = String((error && error.message) || "").toLowerCase();
  return txt.includes("authentication required") || txt.includes("401");
}

function applyChatPayload(payload) {
  state.sessionId = payload.session_id;
  ui.chatTitle.textContent = payload.session_id;
  state.lastAssistantTopic = payload.topic || null;
  setSafetyBadge(String(payload.intent || "").toLowerCase() === "safety");
  renderMessage("assistant", formatAssistantText(payload), payload.references || [], {
    confidence: payload.confidence,
    intent: payload.intent,
    topic: payload.topic || null,
    timestamp: new Date().toISOString(),
    messageIndex: state.messageCounter++,
  });
}

async function refreshSessions() {
  const payload = await api.json("/api/sessions", { headers: authHeaders() });
  state.sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
  renderSessions();
}

async function deleteSession(sessionId = null) {
  const target = sessionId || state.sessionId;
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!target) {
    renderMessage("assistant", "No active chat to delete.");
    return;
  }
  const ok = window.confirm(`Delete chat ${target}?`);
  if (!ok) {
    return;
  }
  setStatus("Deleting chat...");
  setLoading(true);
  try {
    await api.json(`/api/sessions/${encodeURIComponent(target)}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (state.sessionId === target) {
      state.sessionId = null;
      state.lastAssistantTopic = null;
      state.sessionTags = [];
      state.sessionPins = [];
      ui.chatTitle.textContent = "New Session";
      clearMessages();
      renderMessage("assistant", "Chat deleted. Start a new message to open a new session.", [], {
        timestamp: new Date().toISOString(),
      });
    }
    await refreshSessions();
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function loadSession(sessionId) {
  const payload = await api.json(`/api/sessions/${encodeURIComponent(sessionId)}`, { headers: authHeaders() });
  state.sessionId = payload.session_id;
  ui.chatTitle.textContent = payload.session_id;
  state.sessionTags = Array.isArray(payload.tags) ? payload.tags : [];
  state.sessionPins = Array.isArray(payload.pins) ? payload.pins : [];
  setSafetyBadge(false);
  closeMobileSidebar();
  clearMessages();
  for (let idx = 0; idx < (payload.history || []).length; idx += 1) {
    const msg = payload.history[idx];
    const role = msg.role === "user" ? "user" : "assistant";
    const storedConfidence =
      role === "assistant" && typeof msg.confidence === "number"
        ? Math.max(0, Math.min(100, Number(msg.confidence)))
        : null;
    const meta = {
      confidence: role === "assistant" ? (storedConfidence !== null ? storedConfidence : extractConfidenceFromText(msg.content || "")) : null,
      timestamp: msg.timestamp || "",
      topic: role === "assistant" ? (msg.topic || null) : null,
      messageIndex: idx,
    };
    const refs = role === "assistant" && Array.isArray(msg.references) ? msg.references : [];
    renderMessage(role, msg.content || "", refs, meta);
    if (role === "assistant" && isLikelySafetyMessage(msg.content || "")) {
      setSafetyBadge(true);
    }
    state.messageCounter = idx + 1;
  }
  renderSessions();
  loadDraft();
}

async function handleSignIn(username, password) {
  const payload = await api.json("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  state.authToken = payload.token || null;
  state.userId = payload.user_id || username;
  setStoredAuth(state.authToken, state.userId);
  setAuthUI(true);
  resetChatState();
  await refreshSessions();
  renderMessage("assistant", `Signed in as ${state.userId}. You can start chatting now.`, [], { timestamp: new Date().toISOString() });
}

async function handleSignUp(username, password) {
  const payload = await api.json("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  state.authToken = payload.token || null;
  state.userId = payload.user_id || username;
  setStoredAuth(state.authToken, state.userId);
  setAuthUI(true);
  resetChatState();
  await refreshSessions();
  renderMessage("assistant", `Account created. Signed in as ${state.userId}.`, [], { timestamp: new Date().toISOString() });
}

async function handleSignOut() {
  try {
    if (state.authToken) {
      await api.json("/api/auth/logout", { method: "POST", headers: authHeaders() });
    }
  } catch (_error) {
    // Keep local signout even on network errors.
  }
  forceSignedOut("Signed out.");
}

async function sendChatMessage(rawMessage) {
  const message = normalizeUserMessage(rawMessage);
  if (!message) {
    return;
  }
  renderMessage("user", rawMessage.trim(), [], { timestamp: new Date().toISOString(), messageIndex: state.messageCounter++ });
  ui.messageInput.value = "";
  clearDraft();
  setStatus("Thinking...");
  setLoading(true);
  try {
    const payload = await api.json("/api/chat", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message, session_id: state.sessionId }),
    });
    applyChatPayload(payload);
    await refreshSessions();
  } catch (error) {
    if (isAuthError(error)) {
      forceSignedOut("Session expired. Please sign in again.");
    } else {
      renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
    }
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function runSessionAction(endpoint, workingStatus) {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!state.sessionId) {
    renderMessage("assistant", "Start a chat first.");
    return;
  }
  setStatus(workingStatus);
  setLoading(true);
  try {
    const payload = await api.json(endpoint, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    applyChatPayload(payload);
    await refreshSessions();
  } catch (error) {
    if (isAuthError(error)) {
      forceSignedOut("Session expired. Please sign in again.");
    } else {
      renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
    }
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function requestContinue() {
  await runSessionAction("/api/chat/continue", "Continuing...");
}

async function requestRegenerate() {
  await runSessionAction("/api/chat/regenerate", "Regenerating...");
}

async function pinMessageAt(messageIndex) {
  if (!state.authToken || !state.sessionId) {
    return;
  }
  const note = window.prompt("Optional pin note:", "") || "";
  try {
    await api.json(`/api/sessions/${encodeURIComponent(state.sessionId)}/pins`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message_index: Number(messageIndex),
        note,
      }),
    });
    setStatus("Message pinned.");
  } catch (error) {
    setStatus(`Pin failed: ${error.message}`);
  }
}

async function showPins() {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!state.sessionId) {
    renderMessage("assistant", "Start a chat first.");
    return;
  }
  setStatus("Loading pins...");
  setLoading(true);
  try {
    const payload = await api.json(`/api/sessions/${encodeURIComponent(state.sessionId)}/pins`, {
      headers: authHeaders(),
    });
    const pins = Array.isArray(payload.pins) ? payload.pins : [];
    state.sessionPins = pins;
    if (!pins.length) {
      renderMessage("assistant", "No pinned messages in this session yet.", [], { timestamp: new Date().toISOString() });
    } else {
      const lines = [`Pinned messages (${pins.length}):`];
      for (const pin of pins.slice(0, 20)) {
        const role = String(pin.role || "").toUpperCase();
        const when = formatTimeStamp(pin.timestamp || "");
        const notePart = pin.note ? ` | note: ${pin.note}` : "";
        lines.push(`- #${pin.message_index} [${role}${when ? ` @ ${when}` : ""}] ${pin.excerpt}${notePart}`);
      }
      renderMessage("assistant", lines.join("\n"), [{ title: "Pinned Messages", url: "internal://pins" }], {
        timestamp: new Date().toISOString(),
      });
    }
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function setSessionTags(tags) {
  if (!state.authToken || !state.sessionId) {
    return;
  }
  const payload = await api.json(`/api/sessions/${encodeURIComponent(state.sessionId)}/tags`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ tags }),
  });
  state.sessionTags = Array.isArray(payload.tags) ? payload.tags : [];
  await refreshSessions();
}

async function setTagsFromPrompt() {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!state.sessionId) {
    renderMessage("assistant", "Start a chat first.");
    return;
  }
  const existing = state.sessionTags.join(", ");
  const raw = window.prompt("Set session tags (comma-separated):", existing);
  if (raw === null) {
    return;
  }
  const tags = String(raw || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  try {
    await setSessionTags(tags);
    const text = state.sessionTags.length ? `Session tags updated: ${state.sessionTags.join(", ")}` : "Session tags cleared.";
    renderMessage("assistant", text, [{ title: "Session Tags", url: "internal://session-tags" }], {
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  }
}

function formatAutonomyGoalLine(goal, index) {
  const status = String(goal.status || "open").toLowerCase();
  const priority = String(goal.priority || "normal").toLowerCase();
  const count = Math.max(1, Number(goal.count || 1));
  const id = String(goal.id || "").trim();
  const title = String(goal.title || "").trim() || "(untitled goal)";
  const trigger = String(goal.trigger || "").trim();
  const triggerPart = trigger ? ` | trigger: ${trigger}` : "";
  return `${index + 1}. [${status}/${priority}] ${title} (id: ${id}, seen: ${count})${triggerPart}`;
}

async function showAutonomyGoals() {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return [];
  }
  setStatus("Loading autonomy goals...");
  setLoading(true);
  try {
    const [goalsPayload, capsPayload, planPayload] = await Promise.all([
      api.json("/api/autonomy/goals", { headers: authHeaders() }),
      api.json("/api/autonomy/capabilities", { headers: authHeaders() }),
      api.json("/api/autonomy/self-upgrade-plan", { headers: authHeaders() }),
    ]);
    const goals = Array.isArray(goalsPayload.goals) ? goalsPayload.goals : [];
    const caps = (capsPayload && capsPayload.capabilities) || {};
    const longRunning = Boolean(caps.long_running_tasks && caps.long_running_tasks.enabled);
    const selfUpgrade = Boolean(caps.self_upgrading_code && caps.self_upgrading_code.enabled);
    const independent = Boolean(caps.independent_decisions && caps.independent_decisions.enabled);
    const plan = (planPayload && planPayload.plan) || {};
    const planItems = Array.isArray(plan.items) ? plan.items : [];
    const lines = [
      "Autonomy capability status:",
      `- Long-running tasks: ${longRunning ? "Yes" : "No"}`,
      `- Self-upgrading code: ${selfUpgrade ? "Yes" : "No"}`,
      `- Independent decisions: ${independent ? "Yes" : "Yes (bounded by safety checks)"}`,
      "",
      goals.length ? `Autonomy goals (${goals.length}):` : "No autonomy goals yet.",
    ];
    for (let i = 0; i < goals.length; i += 1) {
      lines.push(formatAutonomyGoalLine(goals[i], i));
    }
    lines.push("");
    lines.push(`Self-upgrade planning: ${selfUpgrade ? "active" : "plan-only (safe mode)"}`);
    if (planItems.length) {
      lines.push("Top upgrade plan items:");
      for (const item of planItems.slice(0, 3)) {
        lines.push(`- [${item.priority}] ${item.title} (complexity ${item.estimated_complexity})`);
      }
    }
    lines.push("", "Manage goals: add | open <id> | progress <id> | done <id> | block <id> | delete <id> | clear | run");
    renderMessage("assistant", lines.join("\n"), [{ title: "Autonomy Goals", url: "internal://autonomy-goals" }], {
      timestamp: new Date().toISOString(),
    });
    return goals;
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
    return [];
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function manageAutonomyGoals() {
  await showAutonomyGoals();
  if (!state.authToken) {
    return;
  }
  const raw = window.prompt(
    "Goals action (optional): add | open <id> | progress <id> | done <id> | block <id> | delete <id> | clear | run",
    ""
  );
  if (raw === null) {
    return;
  }
  const text = String(raw || "").trim();
  if (!text) {
    return;
  }
  const parts = text.split(/\s+/).filter(Boolean);
  const action = (parts.shift() || "").toLowerCase();
  const id = (parts.shift() || "").toLowerCase();
  const statusMap = {
    open: "open",
    progress: "in_progress",
    doing: "in_progress",
    done: "done",
    block: "blocked",
    blocked: "blocked",
  };

  setStatus("Updating autonomy goals...");
  setLoading(true);
  try {
    if (action === "add") {
      const title = window.prompt("Goal title:", "");
      if (!title || !title.trim()) {
        setStatus("Goal add canceled.");
        return;
      }
      const priority = (window.prompt("Priority (low|normal|high):", "normal") || "normal").trim().toLowerCase();
      const trigger = (window.prompt("Trigger or reason (optional):", "") || "").trim();
      await api.json("/api/autonomy/goals", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ title: title.trim(), trigger, priority }),
      });
    } else if (action === "delete") {
      if (!id) {
        throw new Error("Provide a goal id. Example: delete improve-low-confidence-handling");
      }
      await api.json(`/api/autonomy/goals/${encodeURIComponent(id)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
    } else if (action === "clear") {
      const confirmClear = window.confirm("Delete all autonomy goals?");
      if (!confirmClear) {
        setStatus("Clear canceled.");
        return;
      }
      await api.json("/api/autonomy/goals", {
        method: "DELETE",
        headers: authHeaders(),
      });
    } else if (action === "run") {
      const stepsRaw = window.prompt("Max steps for this autonomy run (1-20):", "6") || "6";
      const maxSteps = Math.max(1, Math.min(20, Number.parseInt(stepsRaw, 10) || 6));
      const payload = await api.json("/api/autonomy/goals/run", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ max_steps: maxSteps }),
      });
      const report = (payload && payload.report) || {};
      renderMessage(
        "assistant",
        `Autonomy run complete. Processed: ${Number(report.processed_count || 0)} | Remaining open: ${Number(report.remaining_open || 0)}.`,
        [{ title: "Autonomy Goal Runner", url: "internal://autonomy-run" }],
        { timestamp: new Date().toISOString() }
      );
    } else if (Object.prototype.hasOwnProperty.call(statusMap, action)) {
      if (!id) {
        throw new Error("Provide a goal id. Example: done improve-low-confidence-handling");
      }
      await api.json(`/api/autonomy/goals/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: statusMap[action] }),
      });
    } else {
      throw new Error(`Unknown goals action: ${action}`);
    }
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }

  await showAutonomyGoals();
}

async function showProfile() {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  setStatus("Loading profile...");
  setLoading(true);
  try {
    const payload = await api.json("/api/profile", { headers: authHeaders() });
    const profile = payload.profile || {};
    const keys = Object.keys(profile);
    if (!keys.length) {
      renderMessage("assistant", "No saved profile facts yet. Try: my name is <name>.");
    } else {
      const lines = ["Saved profile facts:"];
      for (const key of keys) {
        const item = profile[key] || {};
        lines.push(`- ${key}: ${item.value || ""} (${Math.round(Number(item.confidence || 0) * 100)}%)`);
      }
      renderMessage("assistant", lines.join("\n"), [{ title: "Learned User Profile", url: "memory://user-facts" }], {
        timestamp: new Date().toISOString(),
      });
    }
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function showSuggestions() {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  setStatus("Loading suggestions...");
  setLoading(true);
  try {
    const payload = await api.json("/api/chat/suggestions", { headers: authHeaders() });
    const list = Array.isArray(payload.suggestions) ? payload.suggestions : [];
    if (!list.length) {
      renderMessage("assistant", "No suggestions available right now.");
    } else {
      const text = ["Try one of these prompts:", ...list.map((item, idx) => `${idx + 1}. ${item}`)].join("\n");
      renderMessage("assistant", text, [], { timestamp: new Date().toISOString() });
    }
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function exportCurrentSession(format = "markdown") {
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  if (!state.sessionId) {
    renderMessage("assistant", "Start a chat first.");
    return;
  }
  setStatus("Exporting...");
  setLoading(true);
  try {
    const payload = await api.json(`/api/sessions/${encodeURIComponent(state.sessionId)}/export?fmt=${encodeURIComponent(format)}`, {
      headers: authHeaders(),
    });
    const mode = String(payload.format || "markdown").toLowerCase();
    if (mode === "json") {
      const text = JSON.stringify(payload.content || [], null, 2);
      downloadText(`${state.sessionId}.json`, text);
    } else {
      downloadText(`${state.sessionId}.md`, String(payload.content || ""));
    }
    renderMessage("assistant", `Exported ${state.sessionId} as ${mode}.`, [], { timestamp: new Date().toISOString() });
  } catch (error) {
    renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
  } finally {
    setLoading(false);
    setStatus("Ready");
  }
}

async function handleSlashCommand(rawText) {
  const text = String(rawText || "").trim();
  if (!text.startsWith("/")) {
    return false;
  }
  const parts = text.slice(1).split(/\s+/).filter(Boolean);
  const cmd = (parts.shift() || "").toLowerCase();
  if (!cmd) {
    return true;
  }

  if (cmd === "help") {
    renderMessage(
      "assistant",
      [
        "Slash commands:",
        "/help",
        "/new",
        "/continue",
        "/regenerate",
        "/profile",
        "/suggest",
        "/export [markdown|json]",
        "/search <text>",
        "/pins",
        "/tags [comma,separated]",
        "/goals",
        "/mode [simple|standard|advanced]",
        "/tone [formal|friendly|casual|chill|direct]",
        "/delete",
      ].join("\n"),
      [],
      { timestamp: new Date().toISOString() }
    );
    return true;
  }
  if (cmd === "new") {
    ui.newSessionBtn.click();
    return true;
  }
  if (cmd === "continue") {
    await requestContinue();
    return true;
  }
  if (cmd === "regen" || cmd === "regenerate") {
    await requestRegenerate();
    return true;
  }
  if (cmd === "profile") {
    await showProfile();
    return true;
  }
  if (cmd === "suggest" || cmd === "suggestions") {
    await showSuggestions();
    return true;
  }
  if (cmd === "export") {
    const mode = (parts[0] || "markdown").toLowerCase();
    await exportCurrentSession(mode === "json" ? "json" : "markdown");
    return true;
  }
  if (cmd === "search") {
    await searchInSession(parts.join(" "));
    return true;
  }
  if (cmd === "pins") {
    await showPins();
    return true;
  }
  if (cmd === "tags") {
    if (!parts.length) {
      await setTagsFromPrompt();
      return true;
    }
    const tags = parts.join(" ").split(",").map((item) => item.trim()).filter(Boolean);
    try {
      await setSessionTags(tags);
      renderMessage("assistant", `Session tags updated: ${state.sessionTags.join(", ") || "(none)"}`, [], {
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      renderMessage("assistant", `Error: ${error.message}`, [], { timestamp: new Date().toISOString() });
    }
    return true;
  }
  if (cmd === "goals") {
    await manageAutonomyGoals();
    return true;
  }
  if (cmd === "mode") {
    const mode = (parts[0] || "").toLowerCase().trim();
    if (!mode) {
      await sendChatMessage("what is my response mode");
      return true;
    }
    if (!["simple", "standard", "advanced"].includes(mode)) {
      renderMessage("assistant", "Mode must be one of: simple, standard, advanced.", [], {
        timestamp: new Date().toISOString(),
      });
      return true;
    }
    await sendChatMessage(`set response mode to ${mode}`);
    return true;
  }
  if (cmd === "tone") {
    const tone = (parts[0] || "").toLowerCase().trim();
    if (!tone) {
      renderMessage("assistant", `Current tone mode: ${state.toneMode}.`, [], { timestamp: new Date().toISOString() });
      return true;
    }
    await applyToneMode(tone);
    return true;
  }
  if (cmd === "delete") {
    await deleteSession();
    return true;
  }

  renderMessage("assistant", `Unknown command: /${cmd}. Use /help.`, [], { timestamp: new Date().toISOString() });
  return true;
}

ui.authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.authToken) {
    return;
  }
  const username = ui.authUsername.value.trim().toLowerCase();
  const password = ui.authPassword.value;
  if (!username || !password) {
    renderMessage("assistant", "Enter username and password.");
    return;
  }
  setStatus("Signing in...");
  setLoading(true);
  try {
    await handleSignIn(username, password);
    setStatus("Ready");
    loadDraft();
  } catch (error) {
    renderMessage("assistant", `Sign in failed: ${error.message}`, [], { timestamp: new Date().toISOString() });
    setStatus("Ready");
  } finally {
    setLoading(false);
  }
});

ui.signUpBtn.addEventListener("click", async () => {
  if (state.authToken) {
    return;
  }
  const username = ui.authUsername.value.trim().toLowerCase();
  const password = ui.authPassword.value;
  if (!username || !password) {
    renderMessage("assistant", "Enter username and password.");
    return;
  }
  setStatus("Creating account...");
  setLoading(true);
  try {
    await handleSignUp(username, password);
    setStatus("Ready");
    loadDraft();
  } catch (error) {
    renderMessage("assistant", `Sign up failed: ${error.message}`, [], { timestamp: new Date().toISOString() });
    setStatus("Ready");
  } finally {
    setLoading(false);
  }
});

ui.signOutBtn.addEventListener("click", async () => {
  setStatus("Signing out...");
  setLoading(true);
  await handleSignOut();
  setLoading(false);
});

ui.newSessionBtn.addEventListener("click", () => {
  closeMobileSidebar();
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  state.sessionId = null;
  state.lastAssistantTopic = null;
  state.sessionTags = [];
  state.sessionPins = [];
  ui.chatTitle.textContent = "New Session";
  clearMessages();
  renderSessions();
  loadDraft();
  renderMessage("assistant", "New session ready. Send a message to begin.", [], { timestamp: new Date().toISOString() });
});

if (ui.continueBtn) {
  ui.continueBtn.addEventListener("click", async () => {
    await requestContinue();
  });
}

if (ui.regenerateBtn) {
  ui.regenerateBtn.addEventListener("click", async () => {
    await requestRegenerate();
  });
}

if (ui.exportBtn) {
  ui.exportBtn.addEventListener("click", async () => {
    await exportCurrentSession("markdown");
  });
}

if (ui.deleteSessionBtn) {
  ui.deleteSessionBtn.addEventListener("click", async () => {
    await deleteSession();
  });
}

if (ui.profileBtn) {
  ui.profileBtn.addEventListener("click", async () => {
    await showProfile();
  });
}

if (ui.pinsBtn) {
  ui.pinsBtn.addEventListener("click", async () => {
    await showPins();
  });
}

if (ui.tagsBtn) {
  ui.tagsBtn.addEventListener("click", async () => {
    await setTagsFromPrompt();
  });
}

if (ui.goalsBtn) {
  ui.goalsBtn.addEventListener("click", async () => {
    await manageAutonomyGoals();
  });
}

if (ui.applyToneBtn) {
  ui.applyToneBtn.addEventListener("click", async () => {
    const tone = ui.toneSelect ? ui.toneSelect.value : "";
    await applyToneMode(tone);
  });
}

if (ui.profileCard) {
  ui.profileCard.addEventListener("click", () => {
    if (ui.profilePanel && !ui.profilePanel.open) {
      ui.profilePanel.open = true;
    }
    const isOpen = !ui.profileDetails || ui.profileDetails.classList.contains("hidden");
    setProfileDetailsOpen(isOpen);
  });
}

if (ui.profilePanel) {
  ui.profilePanel.addEventListener("toggle", () => {
    setProfileDetailsOpen(Boolean(ui.profilePanel.open));
  });
}

if (ui.saveProfileBtn) {
  ui.saveProfileBtn.addEventListener("click", () => {
    saveProfileData();
  });
}

if (ui.toggleConfidence) {
  ui.toggleConfidence.addEventListener("change", () => {
    state.uiPrefs.showConfidence = Boolean(ui.toggleConfidence.checked);
    saveUiPrefs();
    applyUiPrefs();
  });
}

if (ui.toggleCompact) {
  ui.toggleCompact.addEventListener("change", () => {
    state.uiPrefs.compactMessages = Boolean(ui.toggleCompact.checked);
    saveUiPrefs();
    applyUiPrefs();
  });
}

if (ui.toggleAutoscroll) {
  ui.toggleAutoscroll.addEventListener("change", () => {
    state.uiPrefs.autoScroll = Boolean(ui.toggleAutoscroll.checked);
    saveUiPrefs();
    applyUiPrefs();
  });
}

if (ui.searchBtn && ui.searchInput) {
  ui.searchBtn.addEventListener("click", async () => {
    await searchInSession(ui.searchInput.value);
  });

  ui.searchInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    await searchInSession(ui.searchInput.value);
  });
}

if (ui.mobileMenuBtn) {
  ui.mobileMenuBtn.addEventListener("click", () => {
    const next = !document.body.classList.contains("mobile-sidebar-open");
    setMobileSidebarOpen(next);
  });
}

if (ui.mobileSidebarBackdrop) {
  ui.mobileSidebarBackdrop.addEventListener("click", () => {
    closeMobileSidebar();
  });
}

window.addEventListener("resize", () => {
  if (!isMobileViewport()) {
    closeMobileSidebar();
  }
});
ui.messageInput.addEventListener("input", () => {
  saveDraft();
});

ui.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.authToken) {
    renderMessage("assistant", "Please sign in first.");
    return;
  }
  const rawMessage = ui.messageInput.value;
  const cleaned = rawMessage.trim();
  if (!cleaned) {
    return;
  }
  if (await handleSlashCommand(cleaned)) {
    ui.messageInput.value = "";
    clearDraft();
    return;
  }
  if (cleaned.toLowerCase() === "continue") {
    ui.messageInput.value = "";
    clearDraft();
    await requestContinue();
    return;
  }
  if (cleaned.toLowerCase() === "regenerate") {
    ui.messageInput.value = "";
    clearDraft();
    await requestRegenerate();
    return;
  }
  await sendChatMessage(rawMessage);
});

async function boot() {
  setStatus("Loading...");
  initLogoFallback();
  localStorage.removeItem("asseri_user_id");
  state.toneMode = (localStorage.getItem(TONE_MODE_KEY) || "friendly").toLowerCase();
  if (!["formal", "friendly", "casual", "chill", "direct"].includes(state.toneMode)) {
    state.toneMode = "friendly";
  }
  syncToneUI();
  syncProfileCard();
  loadUiPrefs();
  loadProfileData();
  applyUiPrefs();
  setProfileDetailsOpen(false);
  setSafetyBadge(false);
  closeMobileSidebar();

  if (!API_BASE && (window.location.hostname.endsWith("github.io") || window.location.pathname.startsWith("/docs"))) {
    renderMessage(
      "assistant",
      "Backend URL is not configured for this hosted page. Open this page with ?api=https://YOUR-BACKEND-URL, then refresh.",
      [],
      { timestamp: new Date().toISOString() }
    );
  }

  const storedToken = (localStorage.getItem(AUTH_TOKEN_KEY) || "").trim();
  const storedUser = (localStorage.getItem(AUTH_USER_KEY) || "").trim();
  state.authToken = storedToken || null;
  state.userId = storedUser || null;

  if (!state.authToken) {
    setAuthUI(false);
    renderMessage("assistant", "Sign in or create an account to start chatting.", [], { timestamp: new Date().toISOString() });
    setStatus("Ready");
    loadDraft();
    return;
  }

  try {
    const me = await api.json("/api/auth/me", { headers: authHeaders() });
    state.userId = me.user_id || state.userId;
    setStoredAuth(state.authToken, state.userId);
    setAuthUI(true);
    await refreshSessions();
    renderMessage("assistant", `Welcome back, ${state.userId}. Ask anything: math, knowledge, or conversation.`, [], {
      timestamp: new Date().toISOString(),
    });
    loadDraft();
  } catch (_error) {
    forceSignedOut("Session expired. Please sign in again.");
  } finally {
    setStatus("Ready");
  }
}

boot();




















