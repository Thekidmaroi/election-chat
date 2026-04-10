"""
Election Chat — Interface Streamlit Premium
EDAN 2025 Côte d'Ivoire
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag.hybrid_agent import process_question

st.set_page_config(
    page_title="🗳️ EDAN 2025 — Election Chat",
    page_icon="🇨🇮",
    layout="wide",
    initial_sidebar_state="expanded"
)

CI_ORANGE = "#F77F00"
CI_GREEN  = "#009A44"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; }}
    .stApp {{
        background: linear-gradient(135deg, #0d1b2a 0%, #1a2744 40%, #0d2818 100%);
        min-height: 100vh;
    }}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}

    .main-header {{
        background: linear-gradient(135deg, {CI_ORANGE} 0%, #e06000 30%, {CI_GREEN} 100%);
        padding: 30px 40px; border-radius: 20px; margin-bottom: 25px;
        position: relative; overflow: hidden;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }}
    .main-header::before {{
        content: ''; position: absolute; top: -50%; right: -10%;
        width: 400px; height: 400px;
        background: rgba(255,255,255,0.05); border-radius: 50%;
    }}
    .header-title {{
        font-family: 'Playfair Display', serif;
        font-size: 2.8em; font-weight: 900; color: white; margin: 0;
        text-shadow: 2px 4px 20px rgba(0,0,0,0.3); letter-spacing: -1px;
    }}
    .header-subtitle {{
        color: rgba(255,255,255,0.9); font-size: 1em; margin-top: 8px;
        font-weight: 300; letter-spacing: 2px; text-transform: uppercase;
    }}

    .stats-bar {{ display: flex; gap: 15px; margin-bottom: 25px; }}
    .stat-card {{
        flex: 1; background: rgba(255,255,255,0.07); backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
        padding: 15px 20px; text-align: center;
        transition: transform 0.2s, border-color 0.2s;
    }}
    .stat-card:hover {{ transform: translateY(-3px); border-color: {CI_ORANGE}; }}
    .stat-number {{
        font-family: 'Playfair Display', serif; font-size: 2em;
        font-weight: 700; color: {CI_ORANGE}; display: block;
    }}
    .stat-label {{
        color: rgba(255,255,255,0.6); font-size: 0.75em;
        text-transform: uppercase; letter-spacing: 1px;
    }}

    .stChatMessage {{ background: transparent !important; }}
    [data-testid="stChatMessageContent"] {{
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 16px !important; color: white !important;
        padding: 15px 20px !important; backdrop-filter: blur(10px);
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {{
        background: linear-gradient(135deg, rgba(247,127,0,0.2), rgba(247,127,0,0.1)) !important;
        border-color: rgba(247,127,0,0.3) !important;
    }}
    [data-testid="stChatInput"] {{
        background: rgba(255,255,255,0.08) !important;
        border: 2px solid rgba(247,127,0,0.4) !important;
        border-radius: 50px !important; color: white !important;
    }}

    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0d1b2a 0%, #162535 100%) !important;
        border-right: 1px solid rgba(247,127,0,0.2) !important;
    }}
    [data-testid="stSidebar"] * {{ color: rgba(255,255,255,0.85) !important; }}
    [data-testid="stSidebar"] .stButton button {{
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(247,127,0,0.3) !important;
        color: rgba(255,255,255,0.85) !important;
        border-radius: 8px !important; font-size: 0.82em !important;
        transition: all 0.2s !important; text-align: left !important;
    }}
    [data-testid="stSidebar"] .stButton button:hover {{
        background: rgba(247,127,0,0.15) !important;
        border-color: {CI_ORANGE} !important;
        transform: translateX(4px) !important;
    }}

    .welcome-card {{
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px; padding: 30px; text-align: center;
        color: rgba(255,255,255,0.7); margin: 20px 0;
    }}
    .welcome-card h3 {{
        color: {CI_ORANGE}; font-family: 'Playfair Display', serif;
        font-size: 1.4em; margin-bottom: 10px;
    }}

    .source-box {{
        background: rgba(255,255,255,0.04);
        border-left: 3px solid {CI_ORANGE};
        border-radius: 8px; padding: 8px 14px;
        margin-top: 10px; font-size: 0.78em;
        color: rgba(255,255,255,0.5);
    }}
    hr {{ border-color: rgba(247,127,0,0.2) !important; }}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <span style="font-size:3em; margin-right:15px; vertical-align:middle;">🇨🇮</span>
    <span class="header-title">EDAN 2025 — Election Chat</span>
    <div class="header-subtitle">Élection des Députés à l'Assemblée Nationale · 27 Décembre 2025 · Côte d'Ivoire</div>
</div>
""", unsafe_allow_html=True)

# ── Stats bar ─────────────────────────────────────────────
st.markdown("""
<div class="stats-bar">
    <div class="stat-card"><span class="stat-number">186</span><span class="stat-label">Circonscriptions</span></div>
    <div class="stat-card"><span class="stat-number">964</span><span class="stat-label">Candidats</span></div>
    <div class="stat-card"><span class="stat-number">41,71%</span><span class="stat-label">Participation moyenne</span></div>
    <div class="stat-card"><span class="stat-number">32</span><span class="stat-label">Partis en lice</span></div>
    <div class="stat-card"><span class="stat-number">1,68M</span><span class="stat-label">Électeurs inscrits</span></div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:10px 0 20px 0;">
        <div style="font-size:3em;">🇨🇮</div>
        <div style="font-family:'Playfair Display',serif; font-size:1.3em; color:#F77F00; font-weight:700;">EDAN 2025</div>
        <div style="font-size:0.75em; color:rgba(255,255,255,0.5); text-transform:uppercase; letter-spacing:2px;">Election Chat</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("**💡 Questions suggérées**")
    examples = [
        ("🏆", "Combien de sièges a gagné le RHDP ?"),
        ("📊", "Top 10 candidats par nombre de voix"),
        ("🗺️", "Qui a gagné dans la circonscription 001 ?"),
        ("📈", "Taux de participation par région"),
        ("📊", "Montre un histogramme des élus par parti"),
        ("🔍", "Qui sont les élus PDCI-RDA ?"),
        ("⚡", "Circonscription avec le plus de voix"),
        ("🌍", "Parle moi des résultats à Abidjan"),
    ]
    for icon, ex in examples:
        if st.button(f"{icon} {ex}", use_container_width=True, key=ex):
            st.session_state.pending_question = ex
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Effacer", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with col2:
        st.markdown("""
        <div style="text-align:center; padding:5px; font-size:0.7em; color:rgba(255,255,255,0.4);">
            Powered by<br><b style="color:#F77F00;">GPT-4o-mini</b>
        </div>
        """, unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Chart colors ──────────────────────────────────────────
PARTI_COLORS = {
    "RHDP": CI_ORANGE, "PDCI-RDA": "#3498db",
    "INDEPENDANT": "#95a5a6", "FPI": "#e74c3c",
    "ADCI": "#9b59b6", "MGC": "#1abc9c",
    "CODE": "#f39c12", "GP-PAIX": "#2ecc71",
}
COLOR_SEQ = [CI_ORANGE, CI_GREEN, "#3498db", "#e74c3c", "#9b59b6",
             "#1abc9c", "#f39c12", "#2ecc71", "#e67e22", "#16a085"]


def generate_chart(df, chart_type, question):
    try:
        if df is None or df.empty or chart_type == "none":
            return None
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        str_cols = df.select_dtypes(include=["object"]).columns.tolist()
        if not num_cols:
            return None
        x_col  = str_cols[0] if str_cols else df.columns[0]
        y_col  = num_cols[0]
        colors = [PARTI_COLORS.get(str(p), COLOR_SEQ[i % len(COLOR_SEQ)])
                  for i, p in enumerate(df[x_col])]

        layout = dict(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="rgba(255,255,255,0.85)", size=12),
            title=dict(
                text=question[:60] + "..." if len(question) > 60 else question,
                font=dict(family="Playfair Display", size=15, color="white"), x=0.02
            ),
            height=420, margin=dict(t=60, b=80, l=60, r=20),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-35, tickfont=dict(size=10)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            hoverlabel=dict(bgcolor="#1a2744", font_size=13, font_family="DM Sans"),
        )

        if chart_type == "pie" and len(df) <= 20:
            fig = go.Figure(go.Pie(
                labels=df[x_col], values=df[y_col], hole=0.45,
                marker=dict(colors=COLOR_SEQ, line=dict(color="#1a2744", width=2)),
                textinfo="label+percent", textfont=dict(size=11, color="white"),
                hovertemplate="<b>%{label}</b><br>%{value:,} — %{percent}<extra></extra>"
            ))
            fig.update_layout(**layout)
            fig.update_layout(showlegend=True,
                legend=dict(bgcolor="rgba(0,0,0,0)",
                            font=dict(color="rgba(255,255,255,0.7)", size=11)))
        elif chart_type == "histogram":
            fig = go.Figure(go.Bar(
                x=df[x_col], y=df[y_col],
                marker=dict(
                    color=df[y_col],
                    colorscale=[[0, CI_GREEN], [0.5, CI_ORANGE], [1, "#FFD700"]],
                    showscale=True,
                    colorbar=dict(tickfont=dict(color="rgba(255,255,255,0.6)"),
                                  outlinecolor="rgba(0,0,0,0)")
                ),
                hovertemplate=f"<b>%{{x}}</b><br>{y_col}: %{{y:,}}<extra></extra>"
            ))
            fig.update_layout(**layout)
        else:
            fig = go.Figure(go.Bar(
                x=df[x_col], y=df[y_col],
                marker=dict(color=colors,
                            line=dict(color="rgba(255,255,255,0.1)", width=1)),
                text=df[y_col].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else ""),
                textposition="outside",
                textfont=dict(color="rgba(255,255,255,0.8)", size=10),
                hovertemplate=f"<b>%{{x}}</b><br>{y_col}: %{{y:,}}<extra></extra>"
            ))
            fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def render_sources(sources: list):
    """Render RAG source citations."""
    if not sources:
        return
    lines = []
    for s in sources:
        circ = s.get("circonscription", "")
        page = s.get("page", "?")
        score = s.get("score", 0)
        if circ:
            lines.append(f"📄 Page {page} — {circ} (score: {score:.2f})")
        else:
            lines.append(f"📄 Page {page} (score: {score:.2f})")
    sources_text = " &nbsp;|&nbsp; ".join(lines)
    st.markdown(
        f'<div class="source-box">🔍 Sources : {sources_text}</div>',
        unsafe_allow_html=True
    )


# ── Welcome screen ────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-card">
        <h3>Bienvenue sur Election Chat 🇨🇮</h3>
        <p>Posez vos questions sur les résultats des élections législatives ivoiriennes du 27 Décembre 2025.<br>
        L'assistant analyse le dataset officiel de la CEI et répond avec des données précises.</p>
        <p style="margin-top:15px; color:rgba(255,255,255,0.4); font-size:0.85em;">
        Essayez : <i>"Combien de sièges a gagné le RHDP ?"</i> ou <i>"Top 10 candidats par voix"</i>
        </p>
    </div>
    """, unsafe_allow_html=True)

# ── Chat history ──────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart") is not None:
            st.plotly_chart(msg["chart"], use_container_width=True,
                            key=f"chart_hist_{i}")
        if msg.get("sources"):
            render_sources(msg["sources"])


# ── Handle question ───────────────────────────────────────
def handle_question(question: str):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("assistant"):
        with st.spinner("🔍 Analyse en cours..."):
            result = process_question(question)

        answer     = result.get("answer", "")
        sources    = result.get("sources", [])
        chart      = None

        st.markdown(answer)

        # Show chart if available
        df = result.get("df")
        if df is not None and not df.empty:
            chart = generate_chart(df, result.get("chart_type", "none"), question)
            if chart:
                st.plotly_chart(chart, use_container_width=True,
                                key=f"chart_new_{len(st.session_state.messages)}")

        # Show RAG sources if available
        if sources:
            render_sources(sources)

    st.session_state.messages.append({
        "role":    "assistant",
        "content": answer,
        "chart":   chart,
        "sources": sources,
    })


# ── Triggers ──────────────────────────────────────────────
if st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None
    handle_question(q)
    st.rerun()

if question := st.chat_input("🇨🇮 Posez votre question sur les élections de Côte d'Ivoire..."):
    handle_question(question)
    st.rerun()