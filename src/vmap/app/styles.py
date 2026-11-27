"""Bộ nhận diện pastel Sáng & Tối đồng bộ 100% với menu Light/Dark của Streamlit."""
import streamlit as st
import streamlit.components.v1 as components

def apply_styles():
    # 1. Script nhỏ tự động bắt chính xác chế độ Light/Dark hiện tại của Streamlit
    components.html(
        """
        <script>
        (function() {
            const parentDoc = window.parent.document;
            function syncTheme() {
                const app = parentDoc.querySelector('[data-testid="stAppViewContainer"]') || parentDoc.body;
                if (!app) return;
                // Lấy màu nền thực tế mà Streamlit đang áp dụng
                const bg = window.parent.getComputedStyle(app).backgroundColor;
                const rgb = bg.match(/\\d+/g);
                if (rgb && rgb.length >= 3) {
                    // Tính độ sáng (luminance): < 128 nghĩa là đang ở Dark Mode
                    const brightness = (parseInt(rgb[0])*299 + parseInt(rgb[1])*587 + parseInt(rgb[2])*114) / 1000;
                    const theme = brightness < 128 ? 'dark' : 'light';
                    if (parentDoc.documentElement.getAttribute('data-vmap-theme') !== theme) {
                        parentDoc.documentElement.setAttribute('data-vmap-theme', theme);
                    }
                }
            }
            syncTheme();
            setInterval(syncTheme, 250);
        })();
        </script>
        """,
        height=0,
        width=0,
    )

    # 2. CSS Pastel cho cả 2 chế độ
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap');

    /* Ẩn khung iframe 0px của script đồng bộ theme */
    iframe[height="0"] {
        display: none !important;
    }

    /* =========================================
       1. LIGHT MODE PASTEL (MẶC ĐỊNH)
    ========================================= */
    :root, html[data-vmap-theme="light"] {
        --bg-main: linear-gradient(135deg, #FFF5F8 0%, #F6F2FF 50%, #EDF8FF 100%);
        --bg-sidebar: linear-gradient(180deg, #F2ECFE 0%, #FCEEF3 55%, #E8F8F3 100%);
        --bg-card: rgba(255, 255, 255, 0.92);
        --bg-input: #FFFFFF;

        --ink: #222642;
        --muted: #787189;
        --heading: #55437A;
        --accent: #C85A7C;
        --accent-soft: #FCE4EC;
        --accent-hover: #F8D0DF;

        --border: #E6DFEF;
        --shadow: 0 6px 20px rgba(85, 67, 122, 0.07);
    }

    /* =========================================
       2. DARK MODE PASTEL (KÍCH HOẠT TỰ ĐỘNG)
    ========================================= */
    html[data-vmap-theme="dark"] {
        --bg-main: linear-gradient(135deg, #161B2E 0%, #1D1B30 50%, #15232E 100%);
        --bg-sidebar: linear-gradient(180deg, #231F38 0%, #2E2233 55%, #1A2D33 100%);
        --bg-card: rgba(36, 42, 62, 0.90);
        --bg-input: #2A314A;

        --ink: #ECECF6;
        --muted: #A2A9C0;
        --heading: #D6C6F4;
        --accent: #F09BB8;
        --accent-soft: #4A3248;
        --accent-hover: #5C3E59;

        --border: #3B425E;
        --shadow: 0 8px 24px rgba(0, 0, 0, 0.30);
    }

    /* =========================================
       3. CẤU TRÚC CHUNG & TYPOGRAPHY
    ========================================= */
    html, body, [class*="css"] {
        font-family: 'Nunito', sans-serif !important;
    }

    .stApp {
        background: var(--bg-main) !important;
        color: var(--ink) !important;
        transition: background 0.25s ease, color 0.25s ease;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    .block-container {
        max-width: 1480px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1 {
        color: var(--ink) !important;
        font-size: 2.15rem !important;
        font-weight: 900 !important;
        letter-spacing: -0.03em;
    }

    h2, h3 {
        color: var(--heading) !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em;
    }

    p, label, .stCaption {
        color: var(--muted) !important;
    }

    /* =========================================
       4. SIDEBAR & MENU ĐIỀU HƯỚNG
    ========================================= */
    [data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border) !important;
        transition: background 0.25s ease;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: var(--ink) !important;
    }

    [data-testid="stRadio"] > div {
        gap: 6px !important;
    }
    [data-testid="stRadio"] label {
        padding: 6px 12px !important;
        border-radius: 12px !important;
        transition: background 0.2s ease;
    }
    [data-testid="stRadio"] label:hover {
        background: var(--accent-soft) !important;
    }

    /* =========================================
       5. V-MAP WORDMARK
    ========================================= */
    .vmap-wordmark {
        display: flex !important;
        align-items: center !important;
        flex-wrap: nowrap !important;
        white-space: nowrap !important;
        font-size: 52px !important;
        font-weight: 900 !important;
        letter-spacing: -2px !important;
        line-height: 1.2 !important;
        padding: 4px 0 6px 0 !important;
        margin: 0 !important;
        filter: drop-shadow(0 3px 6px rgba(15, 130, 180, 0.18));
    }

    .vmap-wordmark span {
        display: inline-block !important;
        -webkit-background-clip: text !important;
        background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
    }

    .vmap-v      { background-image: linear-gradient(135deg, #2563EB, #0EA5E9) !important; }
    .vmap-hyphen { background-image: linear-gradient(135deg, #0EA5E9, #06B6D4) !important; }
    .vmap-m      { background-image: linear-gradient(135deg, #06B6D4, #14B8A6) !important; }
    .vmap-a      { background-image: linear-gradient(135deg, #14B8A6, #2DD4BF) !important; }
    .vmap-p      { background-image: linear-gradient(135deg, #2DD4BF, #5EEAD4) !important; }

    .vmap-caption {
        font-size: 12px !important;
        font-weight: 700 !important;
        color: var(--muted) !important;
        margin-bottom: 20px !important;
    }

    /* =========================================
       6. THẺ CHỈ SỐ (METRIC CARDS) - KHÔNG BAO GIỜ CẮT CHỮ
    ========================================= */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 18px !important;
        padding: 14px 12px !important;
        box-shadow: var(--shadow) !important;
        backdrop-filter: blur(8px);
    }

    [data-testid="stMetricLabel"] p {
        color: var(--muted) !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        white-space: normal !important;
        line-height: 1.2 !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--ink) !important;
        font-size: 1.25rem !important;
        font-weight: 900 !important;
        line-height: 1.3 !important;
    }

    [data-testid="stMetricValue"] > div {
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: unset !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.78rem !important;
        font-weight: 800 !important;
    }

/* =========================================
   7. ĐỒNG BỘ MÀU TẤT CẢ NÚT BẤM
========================================= */

/* NỀN VÀ VIỀN TẤT CẢ NÚT */
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button,
div[data-testid="stFormSubmitButton"] button,
.stButton button,
.stDownloadButton button {
    background: #3EAEF4 !important;
    background-color: #3EAEF4 !important;
    border: 1px solid #3EAEF4 !important;
    border-radius: 12px !important;
    box-shadow: none !important;
}

/* MÀU CHỮ VÀ TOÀN BỘ THÀNH PHẦN BÊN TRONG */
div[data-testid="stButton"] button *,
div[data-testid="stDownloadButton"] button *,
div[data-testid="stFormSubmitButton"] button *,
.stButton button *,
.stDownloadButton button * {
    color: #191970 !important;
    -webkit-text-fill-color: #191970 !important;
    font-weight: 800 !important;
}

/* HOVER */
div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover,
div[data-testid="stFormSubmitButton"] button:hover,
.stButton button:hover,
.stDownloadButton button:hover {
    background: #168BD0 !important;
    background-color: #168BD0 !important;
    border-color: #168BD0 !important;
}

/* GIỮ MÀU CHỮ KHI HOVER */
div[data-testid="stButton"] button:hover *,
div[data-testid="stDownloadButton"] button:hover *,
div[data-testid="stFormSubmitButton"] button:hover *,
.stButton button:hover *,
.stDownloadButton button:hover * {
    color: #191970 !important;
    -webkit-text-fill-color: #191970 !important;
}

/* TRẠNG THÁI FOCUS */
div[data-testid="stButton"] button:focus,
div[data-testid="stDownloadButton"] button:focus,
div[data-testid="stFormSubmitButton"] button:focus {
    background: #3EAEF4 !important;
    border-color: #3EAEF4 !important;
    box-shadow: none !important;
}
/* =========================================
   8. SELECT SLIDER - GRADIENT NHIỀU MÀU
========================================= */

/* Khoảng cách khu vực */
div[data-testid="stSelectSlider"] {
    padding: 12px 4px 18px 4px !important;
    margin-top: 10px !important;
    margin-bottom: 12px !important;
}

/* Thanh nền */
div[data-testid="stSelectSlider"] [data-baseweb="slider"] > div > div {
    background: linear-gradient(
        90deg,
        #3EAEF4 0%,
        #43C6AC 25%,
        #A8D96C 45%,
        #FFD166 65%,
        #FF9B71 82%,
        #D879C8 100%
    ) !important;
    border-radius: 20px !important;
}

/* Nút kéo */
div[data-testid="stSelectSlider"] [role="slider"] {
    background: #3EAEF4 !important;
    border: 3px solid #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(62, 174, 244, 0.3) !important;
}

/* Nhãn lựa chọn */
div[data-testid="stSelectSlider"] [data-baseweb="slider"] span {
    margin-top: 5px !important;
}
    </style>
    """, unsafe_allow_html=True)
