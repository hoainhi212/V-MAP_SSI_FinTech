"""CSS chung cho giao diện V-MAP."""
import streamlit as st


def apply_styles():
    st.markdown("""
    <style>
    :root { --navy:#10243A; --teal:#087E8B; --muted:#637487; }
    .stApp { background:#F5F7FA; color:#172B3A; }
    [data-testid="stHeader"] { background:rgba(245,247,250,.9); }
    [data-testid="stMetric"] { background:#FFFFFF; border:1px solid #E4EAF0; padding:14px 16px; border-radius:12px; }
    div[data-testid="stTabs"] button { font-weight:600; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color:var(--teal); }
    h1,h2,h3 { color:var(--navy); }
    .block-container { padding-top:1.6rem; padding-bottom:2.5rem; }
    </style>
    """, unsafe_allow_html=True)
