/**
 * app.js — Rental Agreement Risk Analyzer Frontend
 * Talks to the FastAPI backend (local or Hugging Face Spaces).
 *
 * ⚙️  CHANGE THIS to your Hugging Face Spaces URL after deployment:
 *     e.g. "https://yourusername-rental-risk-api.hf.space"
 */
// 1) After deploying the backend on Render, paste its URL here (no trailing slash):
const RENDER_URL = "https://rental-risk-analyzer-1ao7.onrender.com";
// 2) Opened on your own computer -> uses the local backend; opened from Vercel -> uses Render.
const IS_LOCAL = ["localhost", "127.0.0.1", ""].includes(location.hostname);
const API_BASE = IS_LOCAL ? "http://localhost:7860" : RENDER_URL;

// Render's free plan puts the server to sleep when idle. Pinging it as soon as the page
// opens starts waking it, so it is usually ready by the time you click Analyse.
fetch(`${API_BASE}/api/health`).catch(() => {});

// One helper for both endpoints: 2-minute timeout + friendly error messages.
async function postJSON(path, payload) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal
    });
    if (!res.ok) throw new Error(`Server error ${res.status}: ${await res.text()}`);
    return await res.json();
  } catch (e) {
    if (e.name === "AbortError") throw new Error("The server took too long to answer (over 2 minutes). Please try again.");
    if (e.name === "TypeError") throw new Error("Cannot reach the backend. On Render's free plan it may still be waking up - wait a minute and try again.");
    throw e;
  } finally { clearTimeout(timer); }
}

// ── Tab switching ──────────────────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach(b => {
    b.classList.toggle("active", b.id === `tab-${tab}-btn`);
    b.setAttribute("aria-selected", b.id === `tab-${tab}-btn`);
  });
  document.querySelectorAll(".tab-content").forEach(c => {
    c.classList.toggle("active", c.id === `tab-${tab}`);
  });
}

// ── Staged rent toggle ─────────────────────────────────────────────────────
function toggleStaged() {
  const staged = document.getElementById("mode").value === "Staged rent";
  document.getElementById("rent2-group").style.display = staged ? "" : "none";
  document.getElementById("m1-group").style.display    = staged ? "" : "none";
  document.getElementById("rent-label").textContent = staged ? "First-period rent (₹)" : "Monthly Rent (₹)";
}

// ── Scenario presets ───────────────────────────────────────────────────────
const SCENARIOS = {
  fair: {
    area: "kothrud", bhk: 2, months: 11, mode: "Fixed rent",
    rent: 29000, rent2: 0, m1: 6,
    dep: 58000, deptype: "Refundable", maint: "licensor",
    lock: 6, lockwho: "both", esc: 5, fee: 100, grace: 7, refund: 30
  },
  borderline: {
    area: "wakad", bhk: 2, months: 11, mode: "Fixed rent",
    rent: 31000, rent2: 0, m1: 6,
    dep: 87000, deptype: "Refundable", maint: "licensee",
    lock: 8, lockwho: "both", esc: 8, fee: 200, grace: 5, refund: 45
  },
  risky: {
    area: "viman nagar", bhk: 2, months: 11, mode: "Fixed rent",
    rent: 55000, rent2: 0, m1: 6,
    dep: 330000, deptype: "Non-refundable", maint: "licensee",
    lock: 11, lockwho: "licensee", esc: 20, fee: 1000, grace: 0, refund: 0
  }
};

function loadScenario(name) {
  const s = SCENARIOS[name];
  if (!s) return;

  // Switch to form tab
  switchTab("form");

  // Fill fields
  setField("area",    s.area);
  setField("bhk",     s.bhk);
  setField("months",  s.months);
  setField("mode",    s.mode);
  toggleStaged();
  setField("rent",    s.rent);
  setField("rent2",   s.rent2);
  setField("m1",      s.m1);
  setField("dep",     s.dep);
  setField("deptype", s.deptype);
  setField("maint",   s.maint);
  setField("lock",    s.lock);
  setField("lockwho", s.lockwho);
  setField("esc",     s.esc);
  setField("fee",     s.fee);
  setField("grace",   s.grace);
  setField("refund",  s.refund);

  // Auto analyse
  analyseForm();
}

function setField(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

// ── Analyse (form mode) ────────────────────────────────────────────────────
async function analyseForm() {
  const payload = {
    area:    val("area"),
    bhk:     int("bhk"),
    months:  int("months"),
    mode:    val("mode"),
    rent:    int("rent"),
    rent2:   int("rent2"),
    m1:      int("m1"),
    dep:     int("dep"),
    deptype: val("deptype"),
    maint:   val("maint"),
    lock:    int("lock"),
    lockwho: val("lockwho"),
    esc:     float("esc"),
    fee:     int("fee"),
    grace:   int("grace"),
    refund:  int("refund"),
  };

  showLoading();
  try {
    const data = await postJSON("/api/analyze/form", payload);
    showResults(data, true);
  } catch (e) {
    showError(e.message);
  }
}

// ── Analyse (text mode) ────────────────────────────────────────────────────
async function analyseText() {
  const text = document.getElementById("agreement-text").value.trim();
  if (text.length < 50) {
    showError("Please paste a longer agreement text (at least 50 characters).");
    return;
  }
  const payload = {
    text,
    area: val("text-area"),
    bhk:  int("text-bhk"),
  };

  showLoading();
  try {
    const data = await postJSON("/api/analyze/text", payload);
    showResults(data, false);
  } catch (e) {
    showError(e.message);
  }
}

// ── Render results ─────────────────────────────────────────────────────────
function showResults(data, isForm) {
  hideAll();
  document.getElementById("results-state").classList.remove("hidden");

  // ── Gauge ──
  const score    = data.score;
  const level    = data.level; // "LOW" | "MODERATE" | "HIGH"
  const ARC_LEN  = 251.2;      // half-circle circumference (r=80, half)

  const gaugeEl  = document.getElementById("gauge-arc");
  const scoreEl  = document.getElementById("gauge-score");
  const badgeEl  = document.getElementById("risk-badge");

  // Color by level
  const colorMap = { LOW: "#10b981", MODERATE: "#f59e0b", HIGH: "#ef4444" };
  const color    = colorMap[level] || "#7c3aed";

  gaugeEl.style.stroke           = color;
  gaugeEl.style.strokeDashoffset = ARC_LEN - (score / 100) * ARC_LEN;

  scoreEl.textContent  = score;
  scoreEl.style.color  = color;
  badgeEl.textContent  = level + " RISK";
  badgeEl.className    = "risk-badge " + level;

  // ── Stat pills ──
  const counts = { High: 0, Medium: 0, Low: 0 };
  (data.clauses || []).forEach(c => counts[c.risk] = (counts[c.risk] || 0) + 1);
  const pillsEl = document.getElementById("stat-pills");
  pillsEl.innerHTML = [
    counts.High   ? `<div class="stat-pill high">🔴 ${counts.High} High</div>` : "",
    counts.Medium ? `<div class="stat-pill medium">🟡 ${counts.Medium} Medium</div>` : "",
    counts.Low    ? `<div class="stat-pill low">🟢 ${counts.Low} Low</div>` : "",
  ].join("");

  // ── Possession note ──
  const pnEl = document.getElementById("possession-note");
  if (data.possession_note) {
    pnEl.textContent = "📌 " + data.possession_note;
    pnEl.classList.remove("hidden");
  } else {
    pnEl.classList.add("hidden");
  }

  // ── NOT STATED ──
  const nsSection = document.getElementById("not-stated-section");
  const nsList    = document.getElementById("not-stated-list");
  const ns = data.not_stated || [];
  if (ns.length > 0) {
    nsList.innerHTML = ns.map(n =>
      `<div class="not-stated-item">
         <span class="not-stated-name">⚠ ${escHtml(n.name)}</span>
         <span class="not-stated-warn">${escHtml(n.warning)}</span>
       </div>`
    ).join("");
    nsSection.classList.remove("hidden");
  } else {
    nsSection.classList.add("hidden");
  }

  // ── Clause cards ──
  const list = document.getElementById("clauses-list");
  list.innerHTML = (data.clauses || []).map((c, idx) => {
    const delay = idx * 0.05;
    return `
      <div class="clause-card ${escHtml(c.risk)}"
           style="animation-delay:${delay}s"
           onclick="toggleClause(this)">
        <div class="clause-num">${c.num}</div>
        <div class="clause-body">
          <div class="clause-title">${escHtml(c.title)}</div>
          <div class="clause-why">${escHtml(c.why || "")}</div>
        </div>
        <div class="clause-src">${escHtml(c.decided_by || "")}</div>
        <div class="clause-expand">${escHtml(c.full_text || c.text || "")}</div>
      </div>`;
  }).join("");

  // ── Generated agreement (form mode only) ──
  const agSection = document.getElementById("agreement-section");
  const agText    = document.getElementById("agreement-text-out");
  if (isForm && data.generated_agreement) {
    agText.textContent = data.generated_agreement;
    agSection.classList.remove("hidden");
    agText.classList.add("hidden"); // collapsed by default
  } else {
    agSection.classList.add("hidden");
  }
}

// ── Clause expand / collapse ───────────────────────────────────────────────
function toggleClause(el) {
  el.classList.toggle("open");
}

// ── Toggle generated agreement ─────────────────────────────────────────────
function toggleAgreement() {
  const el = document.getElementById("agreement-text-out");
  el.classList.toggle("hidden");
}

// ── UI state helpers ───────────────────────────────────────────────────────
let _wakeTimer = null;
function hideAll() {
  clearTimeout(_wakeTimer);
  ["idle-state","loading-state","results-state","error-state"]
    .forEach(id => document.getElementById(id).classList.add("hidden"));
}
function showLoading() {
  hideAll();
  document.getElementById("loading-state").classList.remove("hidden");
  const sub = document.querySelector("#loading-state .loading-sub");
  if (sub) sub.textContent = "Running NLP engine";
  _wakeTimer = setTimeout(() => {
    if (sub) sub.textContent = "Server was asleep (free plan) - waking it up, this can take up to a minute...";
  }, 6000);
  // Disable buttons while loading
  document.querySelectorAll(".analyse-btn").forEach(b => b.disabled = true);
}
function showError(msg) {
  hideAll();
  document.getElementById("error-state").classList.remove("hidden");
  document.getElementById("error-msg").textContent = msg;
  document.querySelectorAll(".analyse-btn").forEach(b => b.disabled = false);
}

// ── Field value helpers ────────────────────────────────────────────────────
function val(id)   { return document.getElementById(id)?.value ?? ""; }
function int(id)   { return parseInt(val(id),  10) || 0; }
function float(id) { return parseFloat(val(id))     || 0; }

// ── HTML escape ────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Re-enable buttons after showing results ────────────────────────────────
// Wrap showResults to always re-enable buttons
const _baseShowResults = showResults;
window.showResults = function(data, isForm) {
  _baseShowResults(data, isForm);
  document.querySelectorAll(".analyse-btn").forEach(b => b.disabled = false);
};

// Expose analyse functions globally (called from onclick HTML attrs)
window.analyseForm  = analyseForm;
window.analyseText  = analyseText;
window.switchTab    = switchTab;
window.toggleStaged = toggleStaged;
window.loadScenario = loadScenario;
window.toggleClause = toggleClause;
window.toggleAgreement = toggleAgreement;
