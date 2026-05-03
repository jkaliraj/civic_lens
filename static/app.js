/* CivicLens AI — Frontend Logic */
"use strict";

const API = "/api";

/**
 * Track events with Google Analytics (GA4).
 * @param {string} eventName - GA4 event name.
 * @param {Object} [params] - Optional event parameters.
 */
function trackEvent(eventName, params = {}) {
    if (typeof gtag === "function") {
        gtag("event", eventName, params);
    }
}

// ── Navigation ─────────────────────────────────────────────

document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn").forEach((b) => {
            b.classList.remove("active");
            b.removeAttribute("aria-current");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-current", "page");

        document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
        const sectionId = `section-${btn.dataset.section}`;
        document.getElementById(sectionId).classList.add("active");

        trackEvent("navigate_section", { section: btn.dataset.section });
    });
});

// ── Chat ───────────────────────────────────────────────────

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");

chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.disabled = true;
    document.getElementById("send-btn").disabled = true;

    trackEvent("chat_message_sent", { message_length: message.length });

    const thinkingEl = showThinking();

    try {
        const res = await fetch(`${API}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        removeThinking(thinkingEl);
        appendMessage(data.reply, "bot");
    } catch (err) {
        removeThinking(thinkingEl);
        appendMessage("Sorry, something went wrong. Please try again.", "bot");
    } finally {
        chatInput.disabled = false;
        document.getElementById("send-btn").disabled = false;
        chatInput.focus();
    }
});

function appendMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `message ${sender === "user" ? "user-message" : "bot-message"}`;
    const content = document.createElement("div");
    content.className = "message-content";
    if (sender === "bot") {
        content.innerHTML = `<strong>CivicLens AI</strong><br>${formatText(text)}`;
    } else {
        content.textContent = text;
    }
    div.appendChild(content);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Sanitise raw text to prevent XSS when inserting via innerHTML.
 * @param {string} text - Untrusted text.
 * @returns {string} HTML-escaped string.
 */
function sanitizeHTML(text) {
    const el = document.createElement("div");
    el.textContent = text;
    return el.innerHTML;
}

/**
 * Convert markdown-style bold and newlines to safe HTML.
 * Sanitises first, then applies formatting patterns.
 * @param {string} text - Raw text from API.
 * @returns {string} Safe HTML string.
 */
function formatText(text) {
    const safe = sanitizeHTML(text);
    return safe
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
}

function showThinking() {
    const div = document.createElement("div");
    div.className = "message bot-message thinking-message";
    div.innerHTML = `<div class="message-content"><span class="thinking-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span></div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function removeThinking(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
}

// ── Election Process ──────────────────────────────────────

async function loadProcess() {
    try {
        const res = await fetch(`${API}/process`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const container = document.getElementById("process-steps");
        container.innerHTML = data.steps
            .map(
                (s) => `
            <article class="step-card" role="listitem">
                <div class="step-header">
                    <span class="step-icon" aria-hidden="true">${s.icon}</span>
                    <span class="step-number" aria-label="Step ${s.step}">${s.step}</span>
                    <span class="step-title">${s.title}</span>
                </div>
                <p class="step-desc">${s.description}</p>
                <ul class="step-details">
                    ${s.details.map((d) => `<li>${d}</li>`).join("")}
                </ul>
            </article>
        `
            )
            .join("");
    } catch {
        document.getElementById("process-steps").innerHTML =
            '<p class="loading">Failed to load election process data.</p>';
    }
}

// ── Timeline ──────────────────────────────────────────────

const timelineForm = document.getElementById("timeline-form");
timelineForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const country = document.getElementById("timeline-country").value.trim();
    if (!country) return;

    trackEvent("timeline_generated", { country: country });

    const container = document.getElementById("timeline-results");
    container.innerHTML = '<div class="loading" role="status">Generating timeline...</div>';

    try {
        const res = await fetch(`${API}/timeline`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ country }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        container.innerHTML = data.timeline
            .map(
                (item) => `
            <div class="timeline-item" role="listitem">
                <div class="timeline-phase">${item.phase}</div>
                <div class="timeline-time">${item.timeframe}</div>
                <p class="timeline-desc">${item.description}</p>
            </div>
        `
            )
            .join("");
    } catch {
        container.innerHTML = '<p class="loading">Failed to generate timeline. Please try again.</p>';
    }
});

// ── Voter Readiness ───────────────────────────────────────

const readinessForm = document.getElementById("readiness-form");
readinessForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const results = document.getElementById("readiness-results");
    results.innerHTML = '<div class="loading" role="status">Evaluating readiness...</div>';

    const payload = {
        registered: document.getElementById("q-registered").checked,
        know_polling_location: document.getElementById("q-polling").checked,
        have_id: document.getElementById("q-id").checked,
        know_election_date: document.getElementById("q-date").checked,
        understand_ballot: document.getElementById("q-ballot").checked,
    };

    trackEvent("readiness_check", {
        items_checked: Object.values(payload).filter(Boolean).length,
    });

    try {
        const res = await fetch(`${API}/readiness`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderReadiness(data);
    } catch {
        results.innerHTML = '<p class="loading">Failed to check readiness. Please try again.</p>';
    }
});

function renderReadiness(data) {
    const scoreClass =
        data.status === "ready" ? "score-ready" : data.status === "needs_action" ? "score-action" : "score-not-ready";

    let html = `
        <div class="readiness-card">
            <div class="score-display">
                <div class="score-number ${scoreClass}">${data.score}%</div>
                <div class="score-label">${data.summary}</div>
            </div>
    `;

    if (data.action_items && data.action_items.length > 0) {
        html += `<h3>Action Items</h3><ul class="action-list">${data.action_items.map((a) => `<li>${a}</li>`).join("")}</ul>`;
    }
    if (data.tips && data.tips.length > 0) {
        html += `<h3>Tips</h3><ul class="tips-list">${data.tips.map((t) => `<li>${t}</li>`).join("")}</ul>`;
    }

    html += "</div>";
    document.getElementById("readiness-results").innerHTML = html;
}

// ── Glossary ──────────────────────────────────────────────

let glossaryData = [];

async function loadGlossary() {
    try {
        const res = await fetch(`${API}/glossary`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        glossaryData = data.terms || [];
        renderGlossary(glossaryData);
    } catch {
        document.getElementById("glossary-list").innerHTML =
            '<p class="loading">Failed to load glossary.</p>';
    }
}

function renderGlossary(terms) {
    document.getElementById("glossary-list").innerHTML = terms
        .map(
            (t) => `
        <div class="glossary-card" role="listitem">
            <div class="glossary-term">${t.term}</div>
            <div class="glossary-def">${t.definition}</div>
        </div>
    `
        )
        .join("");
}

document.getElementById("glossary-search").addEventListener("input", debounce((e) => {
    const q = e.target.value.toLowerCase();
    const filtered = glossaryData.filter(
        (t) => t.term.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q)
    );
    renderGlossary(filtered);
    trackEvent("glossary_search", { query: q });
}, 250));

// ── Accessibility: live announcer ─────────────────────────

/**
 * Announce a message to screen readers via the live region.
 * @param {string} message - Text to announce.
 */
function announce(message) {
    const el = document.getElementById("announcer");
    if (el) {
        el.textContent = "";
        // Force re-announcement by clearing first
        requestAnimationFrame(() => { el.textContent = message; });
    }
}

// ── Keyboard shortcuts ────────────────────────────────────

const navButtons = document.querySelectorAll(".nav-btn");
document.addEventListener("keydown", (e) => {
    // Don't capture if user is typing in an input field
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
        // Allow "/" to blur and focus chat when in other inputs
        if (e.key === "Escape") {
            e.target.blur();
        }
        return;
    }

    // Number keys 1-5 switch tabs
    if (e.key >= "1" && e.key <= "5") {
        const idx = parseInt(e.key) - 1;
        if (navButtons[idx]) {
            navButtons[idx].click();
            announce(`Switched to ${navButtons[idx].textContent} tab`);
        }
    }

    // "/" focuses chat input
    if (e.key === "/") {
        e.preventDefault();
        // Switch to chat tab if not active
        navButtons[0].click();
        chatInput.focus();
        announce("Chat input focused");
    }
});

// ── Debounce utility ──────────────────────────────────────

/**
 * Debounce a function call to avoid excessive invocations.
 * @param {Function} fn - The function to debounce.
 * @param {number} delay - Delay in milliseconds.
 * @returns {Function} Debounced function.
 */
function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ── Error tracking ────────────────────────────────────────

window.addEventListener("error", (e) => {
    trackEvent("javascript_error", {
        message: e.message,
        source: e.filename,
        line: e.lineno,
    });
});

window.addEventListener("unhandledrejection", (e) => {
    trackEvent("unhandled_promise_rejection", {
        reason: String(e.reason),
    });
});

// ── Initialise ────────────────────────────────────────────

loadProcess();
loadGlossary();
trackEvent("app_loaded");
announce("CivicLens AI loaded. Use number keys 1 through 5 to switch tabs.");
