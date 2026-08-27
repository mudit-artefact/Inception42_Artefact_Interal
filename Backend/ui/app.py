"""
ui/app.py — HCS-01 Policy & Leave Concierge — Streamlit Interface

Features:
  - English / Arabic language toggle with RTL CSS support
  - Employee dropdown (EMP001–EMP005) with profile sidebar
  - Streaming chat via httpx + FastAPI /api/v1/hcs01/query
  - Source citation panel per assistant message
  - Premium dark-mode design
"""
import sys
import os
import json
import time
import httpx
import streamlit as st

# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

EMPLOYEES = {
    "EMP001": "Sarah Ahmed — Senior Consultant",
    "EMP002": "Mohammed Al Rashidi — HR Business Partner",
    "EMP003": "Priya Nair — Associate Analyst",
    "EMP004": "Omar Khalil — Finance Manager",
    "EMP005": "Liu Yang — Project Manager",
}

LANG_CONFIG = {
    "en": {
        "label": "🇬🇧 English",
        "dir": "ltr",
        "placeholder": "Ask a policy or leave question...",
        "greeting": "Hello! I'm your **HC Services Policy & Leave Concierge**. Ask me anything about leave entitlements, probation, remote work, or expense claims.",
        "thinking": "Searching policies and generating your answer...",
        "sources_label": "📎 Policy Sources",
        "error_msg": "⚠️ Unable to reach the API. Make sure FastAPI is running on port 8000.",
        "no_vectors": "⚠️ Policy documents have not been ingested yet. Run `python scripts/ingest.py` or call `/api/v1/hcs01/ingest`.",
        "leave_label": "Annual Leave",
        "sick_label": "Sick Leave",
        "carry_label": "Carry-Over",
        "prob_label": "Probation",
        "tenure_label": "Tenure",
    },
    "ar": {
        "label": "🇸🇦 العربية",
        "dir": "rtl",
        "placeholder": "اسألني عن سياسات الإجازات أو المزايا...",
        "greeting": "مرحباً! أنا **مساعد خدمات الموارد البشرية (HCS-01)**. يمكنني الإجابة على أسئلتك حول الإجازات السنوية، الإجازة المرضية، فترة الاختبار، العمل عن بُعد، وبدلات المصاريف.",
        "thinking": "جارٍ البحث في السياسات وإعداد إجابتك...",
        "sources_label": "📎 مصادر السياسات",
        "error_msg": "⚠️ تعذّر الاتصال بالخادم. تأكد من تشغيل FastAPI على المنفذ 8000.",
        "no_vectors": "⚠️ لم يتم فهرسة وثائق السياسات بعد. شغّل `python scripts/ingest.py`.",
        "leave_label": "الإجازة السنوية",
        "sick_label": "الإجازة المرضية",
        "carry_label": "الأيام المرحّلة",
        "prob_label": "فترة الاختبار",
        "tenure_label": "سنوات الخدمة",
    },
}

# ─────────────────────────────────────────────────────────────────
# Page Config & Global CSS
# ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="HCS-01 | Policy & Leave Concierge",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

GLOBAL_CSS = """
<style>
/* ── Google Font ─────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap');

/* ── Root Variables ──────────────────────────── */
:root {
    --bg-primary:    #0d1117;
    --bg-secondary:  #161b22;
    --bg-card:       #1c2128;
    --bg-hover:      #21262d;
    --border:        #30363d;
    --accent:        #7c3aed;
    --accent-light:  #a855f7;
    --accent-glow:   rgba(124,58,237,0.25);
    --gold:          #f59e0b;
    --gold-light:    #fcd34d;
    --text-primary:  #e6edf3;
    --text-secondary:#8b949e;
    --text-muted:    #6e7681;
    --success:       #238636;
    --success-light: #3fb950;
    --warning:       #9e6a03;
    --warning-light: #d29922;
    --user-bubble:   #1e3a5f;
    --bot-bubble:    #1c2128;
    --radius:        12px;
    --radius-sm:     8px;
    --shadow:        0 4px 24px rgba(0,0,0,0.4);
}

/* ── Base App ────────────────────────────────── */
html, body, .stApp {
    background: var(--bg-primary) !important;
    font-family: 'Inter', 'Noto Sans Arabic', sans-serif !important;
    color: var(--text-primary) !important;
}

/* ── Hide Streamlit chrome ───────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Top Header Bar ──────────────────────────── */
.hcs-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%);
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: var(--radius);
    padding: 20px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: var(--shadow), 0 0 40px var(--accent-glow);
}
.hcs-header-icon {
    font-size: 2.5rem;
    filter: drop-shadow(0 0 12px var(--accent));
}
.hcs-header-title {
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(90deg, #c4b5fd, #e9d5ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: -0.3px;
}
.hcs-header-sub {
    font-size: 0.82rem;
    color: #a5b4fc;
    margin: 2px 0 0;
}

/* ── Partner Logo ────────────────────────────── */
.partner-logo {
    display: flex;
    align-items: center;
    background: #ffffff;
    padding: 8px 16px;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    user-select: none;
}
.inc-text {
    color: #1a1a1a;
    font-weight: 600;
    font-size: 1.2rem;
    letter-spacing: -0.5px;
}
.inc-sup {
    font-size: 0.55em;
    font-weight: 700;
    margin-left: 1px;
}
.x-text {
    color: #005fa9;
    font-weight: 700;
    font-size: 1.05rem;
    margin: 0 10px;
}
.art-text {
    color: #001C3D;
    font-weight: 400;
    font-size: 1.2rem;
    letter-spacing: 1.5px;
}

/* ── Sidebar ─────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div { padding: 12px 16px !important; }

/* ── Employee Card ───────────────────────────── */
.emp-card {
    background: linear-gradient(135deg, #1e3a5f 0%, #1c2128 100%);
    border: 1px solid rgba(59,130,246,0.35);
    border-radius: var(--radius);
    padding: 18px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(59,130,246,0.15);
}
.emp-name {
    font-size: 1.05rem;
    font-weight: 600;
    color: #93c5fd;
    margin-bottom: 2px;
}
.emp-role {
    font-size: 0.78rem;
    color: var(--text-secondary);
    margin-bottom: 14px;
}
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.stat-item {
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    text-align: center;
}
.stat-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--gold-light);
    line-height: 1;
}
.stat-label {
    font-size: 0.68rem;
    color: var(--text-muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.prob-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-top: 8px;
}
.prob-passed { background: rgba(35,134,54,0.25); color: var(--success-light); border: 1px solid var(--success); }
.prob-active { background: rgba(158,106,3,0.25); color: var(--warning-light); border: 1px solid var(--warning); }
.prob-extended { background: rgba(220,38,38,0.25); color: #f87171; border: 1px solid #dc2626; }

/* ── Chat Messages ───────────────────────────── */
.stChatMessage {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    margin-bottom: 10px !important;
}
[data-testid="stChatMessageContent"] {
    font-size: 0.92rem !important;
    line-height: 1.65 !important;
}

/* ── Chat Input ──────────────────────────────── */
.stChatInputContainer {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}
.stChatInputContainer:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}

/* ── RTL support ─────────────────────────────── */
.rtl-text {
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Noto Sans Arabic', 'Inter', sans-serif !important;
}
.ltr-text {
    direction: ltr !important;
    text-align: left !important;
}

/* ── Sources Expander ────────────────────────── */
.source-chip {
    display: inline-block;
    background: rgba(124,58,237,0.15);
    border: 1px solid rgba(124,58,237,0.4);
    color: #c4b5fd;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.73rem;
    font-weight: 500;
    margin: 3px;
}
.source-score {
    color: var(--gold);
    font-size: 0.68rem;
    margin-left: 6px;
}

/* ── Language Toggle ─────────────────────────── */
.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}

/* ── Spinner ─────────────────────────────────── */
.thinking-indicator {
    background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(168,85,247,0.1));
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: var(--radius);
    padding: 12px 18px;
    color: #c4b5fd;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    gap: 10px;
    animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* ── Divider ─────────────────────────────────── */
.hcs-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 16px 0;
}

/* ── Scrollbar ───────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Session State Initialisation
# ─────────────────────────────────────────────────────────────────

def init_state():
    if "language" not in st.session_state:
        st.session_state.language = "en"
    if "employee_id" not in st.session_state:
        st.session_state.employee_id = "EMP001"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "employee_profile" not in st.session_state:
        st.session_state.employee_profile = None
    if "last_sources" not in st.session_state:
        st.session_state.last_sources = []


init_state()


# ─────────────────────────────────────────────────────────────────
# API Helpers
# ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def fetch_health():
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{API_BASE}/api/v1/hcs01/health")
            return r.json()
    except Exception:
        return None


@st.cache_data(ttl=60)
def fetch_employee(employee_id: str):
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{API_BASE}/api/omni/employee/{employee_id}")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


def query_rag(query: str, employee_id: str, target_language: str) -> dict | None:
    """Call the RAG endpoint (non-streaming) and return the full response."""
    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{API_BASE}/api/v1/hcs01/query",
                json={
                    "query": query,
                    "employee_id": employee_id,
                    "target_language": target_language,
                },
            )
            if r.status_code == 200:
                return r.json()
            st.error(f"API Error {r.status_code}: {r.text}")
    except httpx.ConnectError:
        return None
    return None


# ─────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────

def render_sidebar():
    lang = st.session_state.language
    cfg = LANG_CONFIG[lang]

    with st.sidebar:
        # ── Language Toggle ─────────────────────────────────────
        st.markdown("### ⚙️ Settings" if lang == "en" else "### ⚙️ الإعدادات")

        lang_choice = st.selectbox(
            "Language / اللغة",
            options=["en", "ar"],
            format_func=lambda x: LANG_CONFIG[x]["label"],
            index=0 if lang == "en" else 1,
            key="lang_select",
        )
        if lang_choice != st.session_state.language:
            st.session_state.language = lang_choice
            st.session_state.messages = []  # Clear chat on language switch
            st.rerun()

        st.markdown('<div class="hcs-divider"></div>', unsafe_allow_html=True)

        # ── Employee Selector ───────────────────────────────────
        st.markdown("### 👤 Employee" if lang == "en" else "### 👤 الموظف")

        emp_choice = st.selectbox(
            "Select Employee" if lang == "en" else "اختر الموظف",
            options=list(EMPLOYEES.keys()),
            format_func=lambda k: EMPLOYEES[k],
            index=list(EMPLOYEES.keys()).index(st.session_state.employee_id),
            key="emp_select",
        )
        if emp_choice != st.session_state.employee_id:
            st.session_state.employee_id = emp_choice
            st.session_state.messages = []
            st.session_state.employee_profile = None
            fetch_employee.clear()
            st.rerun()

        # ── Employee Profile Card ───────────────────────────────
        profile = fetch_employee(st.session_state.employee_id)
        if profile:
            st.session_state.employee_profile = profile
            name = profile.get("name_ar") if lang == "ar" else profile.get("name")
            role = profile.get("role", "")
            dept = profile.get("department", "")
            al = profile.get("annual_leave_balance", 0)
            sl = profile.get("sick_leave_balance", 0)
            co = profile.get("carry_over_days", 0)
            prob = profile.get("probation_status", "")
            tenure = profile.get("years_of_service", 0)

            prob_class = (
                "prob-passed" if prob == "Passed"
                else "prob-active" if prob == "Active"
                else "prob-extended"
            )

            prob_display = prob
            if lang == "ar":
                prob_map = {"Passed": "اجتاز", "Active": "نشط", "Extended": "مُمدَّد"}
                prob_display = prob_map.get(prob, prob)

            tenure_str = (
                f"{tenure} {'year' if tenure == 1 else 'years'}" if lang == "en"
                else f"{tenure} {'سنة' if tenure == 1 else 'سنوات'}"
            )

            card_html = f"""
            <div class="emp-card">
                <div class="emp-name">{'👤 ' + name}</div>
                <div class="emp-role">{role} · {dept}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-value">{al}</div>
                        <div class="stat-label">{cfg['leave_label']}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{sl}</div>
                        <div class="stat-label">{cfg['sick_label']}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{co}</div>
                        <div class="stat-label">{cfg['carry_label']}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{tenure_str}</div>
                        <div class="stat-label">{cfg['tenure_label']}</div>
                    </div>
                </div>
                <div>
                    <span class="prob-badge {prob_class}">{cfg['prob_label']}: {prob_display}</span>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

        # ── API Health ──────────────────────────────────────────
        st.markdown('<div class="hcs-divider"></div>', unsafe_allow_html=True)
        health = fetch_health()
        if health:
            count = health.get("vectors_indexed", 0)
            status_icon = "🟢" if health.get("qdrant_connected") else "🔴"
            st.markdown(
                f"**API Status** {status_icon}  \n"
                f"Vectors: `{count}` · LLM: `{health.get('llm_model', 'N/A')}`"
                if lang == "en" else
                f"**حالة الخادم** {status_icon}  \n"
                f"المتجهات: `{count}` · النموذج: `{health.get('llm_model', 'N/A')}`"
            )
            if count == 0:
                st.warning(cfg["no_vectors"])
        else:
            st.error(cfg["error_msg"])


# ─────────────────────────────────────────────────────────────────
# Main Chat Interface
# ─────────────────────────────────────────────────────────────────

def render_main():
    lang = st.session_state.language
    cfg = LANG_CONFIG[lang]
    is_rtl = (lang == "ar")
    dir_class = "rtl-text" if is_rtl else "ltr-text"

    # ── Header ─────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="hcs-header">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div class="hcs-header-icon">🏢</div>
                <div>
                    <div class="hcs-header-title">{'HCS-01 · Policy & Leave Concierge' if lang == 'en' else 'HCS-01 · مساعد السياسات والإجازات'}</div>
                    <div class="hcs-header-sub">{'HC Services · Powered by GPT-4o & Qdrant' if lang == 'en' else 'خدمات المواد البشرية · مدعوم بـ GPT-4o و Qdrant'}</div>
                </div>
            </div>
            <div class="partner-logo">
                <span class="inc-text">inception<sup class="inc-sup">42</sup></span>
                <span class="x-text">x</span>
                <span class="art-text">ΛRTΞFΛCT</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Greeting message (if first load) ───────────────────────
    if not st.session_state.messages:
        with st.chat_message("assistant", avatar="🏢"):
            st.markdown(
                f'<div class="{dir_class}">\n\n{cfg["greeting"]}\n\n</div>',
                unsafe_allow_html=True,
            )

    # ── Chat History ────────────────────────────────────────────
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        sources = msg.get("sources", [])
        avatar = "👤" if role == "user" else "🏢"

        with st.chat_message(role, avatar=avatar):
            st.markdown(
                f'<div class="{dir_class}">\n\n{content}\n\n</div>',
                unsafe_allow_html=True,
            )
            # Sources expander
            if sources and role == "assistant":
                render_sources(sources, cfg, dir_class)

    # ── Chat Input ──────────────────────────────────────────────
    user_input = st.chat_input(cfg["placeholder"])

    if user_input:
        # Append user message
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("user", avatar="👤"):
            st.markdown(
                f'<div class="{dir_class}">\n\n{user_input}\n\n</div>',
                unsafe_allow_html=True,
            )

        # Call RAG API
        with st.chat_message("assistant", avatar="🏢"):
            thinking_ph = st.empty()
            thinking_ph.markdown(
                f'<div class="thinking-indicator">⚡ {cfg["thinking"]}</div>',
                unsafe_allow_html=True,
            )

            result = query_rag(
                query=user_input,
                employee_id=st.session_state.employee_id,
                target_language=lang,
            )

            thinking_ph.empty()

            if result is None:
                err_msg = cfg["error_msg"]
                st.error(err_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                    "sources": [],
                })
            else:
                answer = result.get("answer", "")
                sources = result.get("sources", [])
                latency = result.get("latency_ms", 0)
                tokens = result.get("tokens_used", 0)

                st.markdown(
                    f'<div class="{dir_class}">\n\n{answer}\n\n</div>',
                    unsafe_allow_html=True,
                )

                # Sources
                if sources:
                    render_sources(sources, cfg, dir_class)

                # Meta info (subtle)
                st.markdown(
                    f"<div style='font-size:0.7rem;color:#6e7681;margin-top:8px;'>"
                    f"⏱ {latency/1000:.1f}s · 🔤 {tokens} tokens</div>",
                    unsafe_allow_html=True,
                )

                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })


def render_sources(sources: list, cfg: dict, dir_class: str):
    """Render the collapsible sources panel."""
    if not sources:
        return
    with st.expander(cfg["sources_label"], expanded=False):
        chips_html = ""
        for s in sources:
            ref = f"{s.get('source', '')} · {s.get('section', '')}".strip(" ·")
            score = s.get("score", 0)
            chips_html += (
                f'<span class="source-chip">{ref}'
                f'<span class="source-score">↑{score:.2f}</span></span>'
            )
        st.markdown(
            f'<div class="{dir_class}" style="padding:8px 0;">{chips_html}</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────

render_sidebar()
render_main()
