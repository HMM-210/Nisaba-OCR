const STAGES_DEFAULT = [
    { id: 1, name_ar: 'تنظيف الصورة',    name_en: 'Cleaning',     status: 'pending', elapsed: null },
    { id: 2, name_ar: 'تقطيع إلى كلمات', name_en: 'Cut to words', status: 'pending', elapsed: null },
    { id: 3, name_ar: 'Tesseract',        name_en: 'Tesseract',    status: 'pending', elapsed: null },
    { id: 4, name_ar: 'PP-OCRv6',         name_en: 'PP-OCRv6',     status: 'pending', elapsed: null },
    { id: 5, name_ar: 'Qari OCR',         name_en: 'Qari OCR',     status: 'pending', elapsed: null },
    { id: 6, name_ar: 'إضافة الترقيم',   name_en: 'Punctuation',  status: 'pending', elapsed: null },
];

const $ = (id) => document.getElementById(id);

let globalStartTime = null;
let timerInterval = null;
let currentStages = STAGES_DEFAULT.map(s => ({ ...s }));
let sseSource = null;
let currentLang = 'ar';
let settingsLoaded = false;

const DEFAULT_SETTINGS = {
    language: 'ar',
    stages_enabled: { '1': true, '2': true, '3': true,
                      '4': true, '5': true, '6': true },
    thresholds: { tesseract: 0.90, ppocrv6: 0.85, qari: 0.92 },
    qari: { max_new_tokens: 32 },
    cleaning: { upscale_factor: 5 },
    words: { min_size_ratio: 0.40, attach_gap_ratio: 0.30 }
};

let currentSettings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));

function renderStages(stages) {
    const container = $('stages-list');
    if (!container) return;

    container.innerHTML = stages.map(s => {
        const timeText = s.elapsed != null ? s.elapsed.toFixed(1) + 's' : '';
        const fill = s.status === 'done' ? 100 : s.status === 'running' ? 65 : 0;
        const numContent = s.status === 'done'
            ? ''
            : `<span class="stage-number-text">${s.id}</span>`;
        const name = currentLang === 'ar' ? s.name_ar : s.name_en;
        return `
            <div class="stage ${s.status}">
                <div class="stage-number">${numContent}</div>
                <div class="stage-info">
                    <div class="stage-name">${name}</div>
                    <div class="stage-en">${s.name_en}</div>
                </div>
                <div class="stage-time">${timeText}</div>
                <div class="stage-bar"><div class="stage-bar-fill" style="width:${fill}%"></div></div>
            </div>
        `;
    }).join('');

    const done = stages.filter(s => s.status === 'done').length;
    const count = $('stages-count');
    if (count) count.textContent = `${done} / ${stages.length}`;
}

function startTimer() {
    globalStartTime = Date.now();
    const el = $('global-timer');
    if (!el) return;
    el.classList.add('active');
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        const elapsed = (Date.now() - globalStartTime) / 1000;
        const mins = Math.floor(elapsed / 60);
        const secs = (elapsed % 60).toFixed(1);
        el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(4, '0')}`;
    }, 100);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function resetUI() {
    currentStages = STAGES_DEFAULT.map(s => ({ ...s }));
    renderStages(currentStages);
    if ($('text-output')) $('text-output').textContent = '';
    if ($('stat-words')) $('stat-words').textContent = '—';
    if ($('stat-time')) $('stat-time').textContent = '—';
    if ($('stat-state')) $('stat-state').textContent = '—';
    if ($('global-timer')) {
        $('global-timer').textContent = '00:00.0';
        $('global-timer').classList.remove('active');
    }
    stopTimer();
    setConnection('idle');
}

function setConnection(state) {
    const dot = $('connection-dot');
    const text = $('connection-text');
    if (!dot || !text) return;

    dot.className = 'dot';

    const labels = {
        online:  { ar: 'متصل',     en: 'Online' },
        busy:    { ar: 'يعمل',     en: 'Busy' },
        offline: { ar: 'غير متصل', en: 'Offline' },
        idle:    { ar: 'خامل',     en: 'Idle' },
    };

    if (state === 'online') dot.classList.add('online');
    else if (state === 'busy') dot.classList.add('busy');

    const lbl = labels[state] || labels.idle;
    text.textContent = currentLang === 'ar' ? lbl.ar : lbl.en;
    text.setAttribute('data-ar', lbl.ar);
    text.setAttribute('data-en', lbl.en);
}

function applyLanguage(lang) {
    currentLang = lang;

    document.body.setAttribute('data-lang', lang);
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');

    document.querySelectorAll('[data-ar][data-en]').forEach(el => {
        const value = el.getAttribute('data-' + lang);
        if (value !== null) el.textContent = value;
    });

    document.querySelectorAll('.lang-btn').forEach(b => {
        const isActive = b.getAttribute('data-lang') === lang;
        b.classList.toggle('active', isActive);
    });

    renderStages(currentStages);
    setConnection('idle');
}

async function saveSettings(patch) {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch)
        });
    } catch (err) {
    }
}

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        if (!res.ok) return;
        const settings = await res.json();
        if (settings) {
    currentSettings = {
        ...DEFAULT_SETTINGS,
        ...settings,
        thresholds: { ...DEFAULT_SETTINGS.thresholds, ...(settings.thresholds || {}) },
        stages_enabled: { ...DEFAULT_SETTINGS.stages_enabled, ...(settings.stages_enabled || {}) },
        qari: { ...DEFAULT_SETTINGS.qari, ...(settings.qari || {}) },
        cleaning: { ...DEFAULT_SETTINGS.cleaning, ...(settings.cleaning || {}) },
        words: { ...DEFAULT_SETTINGS.words, ...(settings.words || {}) }
    };
    if (settings.language === 'en') applyLanguage('en');
    else if (settings.language === 'ar') applyLanguage('ar');
}
    } catch (err) {
    } finally {
        settingsLoaded = true;
    }
}

function switchLanguage(lang) {
    if (!lang) return;
    if (lang !== 'ar' && lang !== 'en') return;
    if (lang === currentLang) return;

    applyLanguage(lang);
    saveSettings({ language: lang });
}

document.addEventListener('click', function (e) {
    const btn = e.target.closest('.lang-btn');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    switchLanguage(btn.getAttribute('data-lang'));
}, true);

const uploadZone = $('upload-zone');
const fileInput = $('file-input');

if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(evt => {
        uploadZone.addEventListener(evt, (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragging');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        uploadZone.addEventListener(evt, (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragging');
        });
    });

    uploadZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) handleUpload(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleUpload(e.target.files[0]);
    });
}

async function handleUpload(file) {
    if (!file.type.startsWith('image/')) {
        alert(currentLang === 'ar' ? 'اختر صورة صحيحة' : 'Please select a valid image');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    resetUI();
    setConnection('busy');

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.ok) {
            await startPipeline();
        } else {
            alert('Error: ' + (data.error || 'Unknown'));
            setConnection('idle');
        }
    } catch (err) {
        alert(currentLang === 'ar'
            ? 'تعذّر الاتصال بالخادم'
            : 'Could not connect to server');
        setConnection('offline');
    }
}

async function startPipeline() {
    try {
        await fetch('/api/start', { method: 'POST' });
    } catch (err) {
        alert(currentLang === 'ar'
            ? 'تعذّر بدء المعالجة'
            : 'Could not start pipeline');
        setConnection('offline');
    }
}

function connectSSE() {
    try {
        sseSource = new EventSource('/api/stream');

        sseSource.onopen = () => setConnection('online');

        sseSource.onmessage = (e) => {
            try {
                applyStatus(JSON.parse(e.data));
            } catch (err) {}
        };

        sseSource.onerror = () => setConnection('offline');
    } catch (err) {
        setConnection('idle');
    }
}

async function fetchAndDisplayResult(sourceKey) {
    try {
        const res = await fetch('/api/result');
        if (!res.ok) return;
        const data = await res.json();
        const sources = data.sources || {};

        let text = '';
        if (sourceKey && sources[sourceKey]) {
            text = sources[sourceKey].punctuated_text || '';
        } else {
            const keys = Object.keys(sources);
            if (keys.length > 0) {
                text = sources[keys[keys.length - 1]].punctuated_text || '';
            }
        }

        if ($('text-output')) {
            $('text-output').textContent = text;
        }
        if ($('stat-words')) {
            const wordCount = text.trim()
                ? text.trim().split(/\s+/).length
                : 0;
            $('stat-words').textContent = wordCount || '—';
        }
    } catch (err) {
    }
}

function applyStatus(status) {
    if (!status) return;

    if (status.stages && status.stages.length) {
        currentStages = status.stages;
        renderStages(currentStages);
    }

    if (status.state === 'processing') {
        if (!timerInterval) startTimer();
        setConnection('busy');
    }

    if (['done', 'error', 'idle', 'stopped'].includes(status.state)) {
        stopTimer();
        setConnection(status.state === 'done' ? 'online' : 'idle');
    }

    if (status.state === 'done' && status.image) {
        if ($('stat-time') && globalStartTime) {
            const elapsedSec = (Date.now() - globalStartTime) / 1000;
            $('stat-time').textContent = elapsedSec.toFixed(1);
        }

        const base = status.image.replace(/\.[^.]+$/, '');
        const key = base.startsWith('cleaned_') ? base : ('cleaned_' + base);
        fetchAndDisplayResult(key);
    }

    const map = {
        idle:       { ar: 'جاهز',   en: 'Ready' },
        processing: { ar: 'يعمل',   en: 'Working' },
        done:       { ar: 'تم',     en: 'Done' },
        error:      { ar: 'خطأ',    en: 'Error' },
        stopped:    { ar: 'متوقف',  en: 'Stopped' },
    };

    const state = map[status.state];
    if ($('stat-state')) {
        $('stat-state').textContent = state
            ? (currentLang === 'ar' ? state.ar : state.en)
            : '—';
    }
}

if ($('stop-btn')) {
    $('stop-btn').addEventListener('click', async () => {
        try { await fetch('/api/stop', { method: 'POST' }); } catch (e) {}
        stopTimer();
        setConnection('idle');
    });
}

if ($('clear-btn')) {
    $('clear-btn').addEventListener('click', async () => {
        try { await fetch('/api/clear', { method: 'POST' }); } catch (e) {}
        resetUI();
    });
}

if ($('copy-btn')) {
    $('copy-btn').addEventListener('click', () => {
        const text = $('text-output').textContent;
        if (!text) return;
        navigator.clipboard.writeText(text);
        const btn = $('copy-btn');
        const orig = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>';
        setTimeout(() => { btn.innerHTML = orig; }, 1500);
    });
}

function spawnParticles() {
    const container = $('particles');
    if (!container) return;

    const count = 40;

    for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        p.className = 'particle';

        const x = Math.random() * 100;
        const y = Math.random() * 100;
        const dx = (Math.random() - 0.5) * 200;
        const dy = -100 - Math.random() * 200;
        const dur = 8 + Math.random() * 12;
        const delay = -Math.random() * 20;

        p.style.left = x + '%';
        p.style.top = y + '%';
        p.style.setProperty('--dx', dx + 'px');
        p.style.setProperty('--dy', dy + 'px');
        p.style.animationDuration = dur + 's';
        p.style.animationDelay = delay + 's';

        const size = 1 + Math.random() * 2;
        p.style.width = size + 'px';
        p.style.height = size + 'px';

        container.appendChild(p);
    }
}

async function init() {
    document.body.setAttribute('data-lang', 'ar');

    renderStages(currentStages);
    spawnParticles();
    connectSSE();

    await loadSettings();
}

window.addEventListener('beforeunload', () => {
    if (sseSource) sseSource.close();
});

init();

function openSettings() {
    const modal = $('settings-modal');
    if (!modal) return;
    modal.hidden = false;
    populateSettingsForm();
}

function closeSettings() {
    const modal = $('settings-modal');
    if (modal) modal.hidden = true;
}

function populateSettingsForm() {
    const s = currentSettings;

    document.querySelectorAll('[data-stage]').forEach(cb => {
        const id = cb.getAttribute('data-stage');
        cb.checked = s.stages_enabled[id] !== false;
    });

    const setRange = (id, val) => {
        const el = $(id);
        const label = $(id + '-val');
        if (el) el.value = val;
        if (label) label.textContent = parseFloat(val).toFixed(2);
    };
    setRange('thr-tesseract', s.thresholds.tesseract);
    setRange('thr-ppocrv6', s.thresholds.ppocrv6);
    setRange('thr-qari', s.thresholds.qari);
    setRange('word-min', s.words.min_size_ratio);
    setRange('word-gap', s.words.attach_gap_ratio);

    if ($('qari-tokens')) $('qari-tokens').value = s.qari.max_new_tokens;
    if ($('clean-factor')) $('clean-factor').value = s.cleaning.upscale_factor;
}

function collectSettingsFromForm() {
    const stages_enabled = {};
    document.querySelectorAll('[data-stage]').forEach(cb => {
        stages_enabled[cb.getAttribute('data-stage')] = cb.checked;
    });

    return {
        language: currentLang,
        stages_enabled,
        thresholds: {
            tesseract: parseFloat($('thr-tesseract').value),
            ppocrv6: parseFloat($('thr-ppocrv6').value),
            qari: parseFloat($('thr-qari').value)
        },
        qari: {
            max_new_tokens: parseInt($('qari-tokens').value, 10) || 32
        },
        cleaning: {
            upscale_factor: parseInt($('clean-factor').value, 10) || 5
        },
        words: {
            min_size_ratio: parseFloat($('word-min').value),
            attach_gap_ratio: parseFloat($('word-gap').value)
        }
    };
}

async function saveSettingsFromUI() {
    currentSettings = collectSettingsFromForm();
    await saveSettings(currentSettings);
    closeSettings();
}

async function resetSettingsUI() {
    currentSettings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    populateSettingsForm();
    await saveSettings(currentSettings);
}

if ($('settings-btn')) {
    $('settings-btn').addEventListener('click', openSettings);
}
if ($('settings-close')) {
    $('settings-close').addEventListener('click', closeSettings);
}
if ($('settings-backdrop')) {
    $('settings-backdrop').addEventListener('click', closeSettings);
}
if ($('settings-save')) {
    $('settings-save').addEventListener('click', saveSettingsFromUI);
}
if ($('settings-reset')) {
    $('settings-reset').addEventListener('click', resetSettingsUI);
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSettings();
});

['thr-tesseract', 'thr-ppocrv6', 'thr-qari',
 'word-min', 'word-gap'].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener('input', () => {
        const label = $(id + '-val');
        if (label) label.textContent = parseFloat(el.value).toFixed(2);
    });
});