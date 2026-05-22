// MCP Code Q&A — chat interface

const API_URL = window.location.origin;
let connectionStatus, statusText, question, repoPath;
let modeStatus, providerStatus, indexStatus;
let repoPicker, repoFilter, refreshRepos;
let chatHistory, chatEmpty;
let allRepoCandidates = [];

document.addEventListener('DOMContentLoaded', function () {
    connectionStatus = document.getElementById('connectionStatus');
    statusText       = document.getElementById('statusText');
    question         = document.getElementById('question');
    repoPath         = document.getElementById('repoPath');
    repoPicker       = document.getElementById('repoPicker');
    repoFilter       = document.getElementById('repoFilter');
    refreshRepos     = document.getElementById('refreshRepos');
    modeStatus       = document.getElementById('modeStatus');
    providerStatus   = document.getElementById('providerStatus');
    indexStatus      = document.getElementById('indexStatus');
    chatHistory      = document.getElementById('chatHistory');
    chatEmpty        = document.getElementById('chatEmpty');
    // Bootstrap connection status dot correctly
    if (connectionStatus) connectionStatus.classList.remove('connected');

    marked.setOptions({ breaks: true, gfm: true, mangle: false, sanitize: false, silent: true });

    initTheme();
    checkServer();
    loadRepoCandidates();
    refreshStatus();
    setupEventListeners();
});

function initTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const dark = saved ? saved === 'dark' : prefersDark;
    setTheme(dark);
}

function setTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    const btn = document.getElementById('themeToggle');
    if (btn) btn.innerHTML = dark ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon"></i>';
    localStorage.setItem('theme', dark ? 'dark' : 'light');
}

function setupEventListeners() {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            setTheme(!isDark);
        });
    }
    question.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitQuestion();
        }
    });

    document.querySelectorAll('.suggestion').forEach(btn => {
        btn.addEventListener('click', function () {
            question.value = this.textContent.trim();
            question.focus();
        });
    });

    if (repoPicker) {
        repoPicker.addEventListener('change', function () {
            if (repoPicker.value) { repoPath.value = repoPicker.value; triggerIndex(repoPicker.value); }
        });
    }
    if (repoFilter)  repoFilter.addEventListener('input', renderRepoCandidates);
    if (refreshRepos) refreshRepos.addEventListener('click', loadRepoCandidates);
    if (repoPath) {
        repoPath.addEventListener('change', () => triggerIndex(repoPath.value));
        repoPath.addEventListener('blur',   () => triggerIndex(repoPath.value));
    }
}

async function checkServer() {
    try {
        const res = await fetch(`${API_URL}/.well-known/mcp`);
        if (res.ok) {
            connectionStatus.classList.add('connected');
            statusText.textContent = 'Connected';
        } else {
            connectionStatus.classList.remove('connected');
            statusText.textContent = 'Disconnected';
        }
    } catch {
        if (connectionStatus) connectionStatus.classList.remove('connected');
        if (statusText) statusText.textContent = 'Disconnected';
    }
}

async function refreshStatus() {
    try {
        const url = repoPath?.value
            ? `${API_URL}/status?repo_path=${encodeURIComponent(repoPath.value)}`
            : `${API_URL}/status`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (modeStatus)    modeStatus.textContent    = data.mode || 'v2';
        if (providerStatus) {
            const name  = data.analysis?.name  || '—';
            const model = data.analysis?.model;
            providerStatus.textContent = model ? `${name} / ${model}` : name;
        }
        if (indexStatus) {
            const rm = data.analysis?.repo_map;
            indexStatus.textContent = rm
                ? `${rm.file_count} files / ${rm.chunk_count} chunks`
                : (data.analysis?.indexed ? 'indexed' : '—');
        }
    } catch { /* ignore */ }
}

async function triggerIndex(path) {
    if (!path) return;
    if (indexStatus) indexStatus.textContent = 'indexing…';
    try {
        const res = await fetch(`${API_URL}/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_path: path }),
        });
        if (res.ok) await refreshStatus();
    } catch { /* ignore */ }
}

async function loadRepoCandidates() {
    try {
        const res = await fetch(`${API_URL}/list_repo_candidates`);
        if (!res.ok) return;
        const data = await res.json();
        allRepoCandidates = data.repos || [];
        renderRepoCandidates();
    } catch { /* ignore */ }
}

function renderRepoCandidates() {
    if (!repoPicker) return;
    const filter = (repoFilter?.value || '').toLowerCase().trim();
    repoPicker.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = allRepoCandidates.length ? 'Choose a folder from Documents...' : 'No folders found';
    repoPicker.appendChild(placeholder);
    allRepoCandidates
        .filter(p => !filter || p.toLowerCase().includes(filter))
        .forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            const match = p.match(/\/Documents\/(.+)$/);
            opt.textContent = match ? match[1] : p;
            repoPicker.appendChild(opt);
        });
}

async function submitQuestion() {
    const text = question.value.trim();
    if (!text) return;

    if (chatEmpty) chatEmpty.style.display = 'none';

    // Append the user bubble
    const entry = document.createElement('div');
    entry.className = 'chat-entry';
    entry.innerHTML = `
        <div class="chat-q">${escapeHtml(text)}</div>
        <div class="chat-a chat-a--loading">
            <span class="chat-spinner"></span> Thinking…
        </div>`;
    chatHistory.appendChild(entry);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    question.value = '';

    const answerEl = entry.querySelector('.chat-a');

    try {
        const res = await fetch(`${API_URL}/question`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text, repo_path: repoPath.value }),
        });

        if (res.ok) {
            const data = await res.json();
            answerEl.classList.remove('chat-a--loading');
            answerEl.innerHTML = renderAnswer(data);
            refreshStatus();
            // Wire evidence chip toggles
            answerEl.querySelectorAll('.evidence-chip-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = btn.dataset.idx;
                    const snip = answerEl.querySelector(`#evsnip-${idx}`);
                    const open = !snip.hidden;
                    snip.hidden = open;
                    btn.setAttribute('aria-expanded', String(!open));
                    btn.classList.toggle('evidence-chip-btn--active', !open);
                });
            });
            setTimeout(() => {
                answerEl.querySelectorAll('pre code').forEach(b => {
                    if (!b.className) b.classList.add('language-python');
                });
                if (window.Prism) Prism.highlightAllUnder(answerEl);
            }, 50);
        } else {
            let msg = `Error ${res.status}`;
            try { const e = await res.json(); msg += ': ' + (e.error || e.detail || ''); } catch { }
            answerEl.classList.remove('chat-a--loading');
            answerEl.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(msg)}</div>`;
        }
    } catch (e) {
        answerEl.classList.remove('chat-a--loading');
        answerEl.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(e.message)}</div>`;
    }

    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function renderAnswer(data) {
    const meta     = data.metadata  || {};
    const citations = data.citations || [];
    const limitations = data.limitations || [];
    const evidence = data.evidence  || [];

    const pills = [
        `<span class="meta-pill">Mode: ${escapeHtml(meta.mode || 'v2')}</span>`,
        `<span class="meta-pill">Provider: ${escapeHtml(meta.provider || '—')}</span>`,
        `<span class="meta-pill">Confidence: ${escapeHtml(data.confidence || '—')}</span>`,
        `<span class="meta-pill">Citations: ${citations.length}</span>`,
    ].join('');

    const warning = limitations.length
        ? `<div class="meta-warning">${escapeHtml(limitations.join(' '))}</div>`
        : '';

    const evidenceHtml = evidence.length ? `
        <div class="evidence-chips-section">
            <span class="evidence-chips-label">Sources</span>
            <div class="evidence-chips">
                ${evidence.map((item, i) => {
                    const label = escapeHtml((item.rel_path || item.path).split('/').pop() + ':' + item.start_line + '-' + item.end_line);
                    const snippet = escapeHtml(item.snippet || '');
                    return `<button class="evidence-chip-btn" data-idx="${i}" aria-expanded="false">${label}</button>
                            <div class="evidence-chip-snippet" id="evsnip-${i}" hidden>
                                <div class="evsnip-meta">${escapeHtml(item.rel_path || item.path)} · ${escapeHtml(item.evidence_type || '')} · score ${Number(item.score || 0).toFixed(2)}</div>
                                <pre><code>${snippet}</code></pre>
                            </div>`;
                }).join('')}
            </div>
        </div>` : '';

    return `
        <div class="answer-meta">${pills}${warning}</div>
        <div class="answer-body">${marked.parse(data.content || '')}</div>
        ${evidenceHtml}`;
}

function escapeHtml(v) {
    return String(v)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}
