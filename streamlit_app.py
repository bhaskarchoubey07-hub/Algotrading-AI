"""Streamlit Main Application Entry Point — AlgoTrade AI
Provides root-level entry point compatible with both direct Streamlit execution
and multi-page navigation.
"""

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import streamlit as st

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.risk import risk_authority
from app.ui.components import apply_custom_theme, render_live_ticker_tape
from app.ui.pages.alerts import render_alerts_page
from app.ui.pages.backtest import render_backtest_page
from app.ui.pages.ensemble import render_ensemble_page
from app.ui.pages.integrations import render_integrations_page
from app.ui.pages.options import render_options_page
from app.ui.pages.overview import render_overview_page
from app.ui.pages.paper_trading import render_paper_trading_page
from app.ui.pages.portfolio import render_portfolio_page
from app.ui.pages.risk import render_risk_page
from app.ui.pages.settings import render_settings_page
from app.ui.pages.strategies import render_strategies_page
from app.ui.pages.terminal import render_terminal_page

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="AlgoTrade AI — Production Trading Workstation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply global dark styling
apply_custom_theme()

# Top Live Ticker Tape
render_live_ticker_tape()

# Sidebar Navigation & Control Panel
st.sidebar.markdown(
    """
    <div style="padding: 10px 0 16px 0;">
        <h2 style="margin: 0; color: #38bdf8; font-weight: 800; font-size: 1.55rem; letter-spacing: -0.5px;">⚡ ALGOTRADE AI</h2>
        <p style="margin: 3px 0 0 0; color: #94a3b8; font-size: 0.8rem; font-weight: 600;">NSE Quantitative Trading Workstation</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Mode Badge with pulsing indicator
st.sidebar.markdown(
    '<div class="badge-paper"><span class="pulse-dot-blue"></span>PAPER TRADING ENFORCED</div>',
    unsafe_allow_html=True,
)

st.sidebar.write("")

# Market Status & IST Clock in Sidebar
ist_now = datetime.now(IST)
m_open, _ = risk_authority.is_market_open(ist_now)
m_badge = '<span class="pulse-dot-green"></span> NSE: SESSION OPEN' if m_open else '● NSE: SESSION CLOSED'
st.sidebar.markdown(
    f"""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">
        <div style="color: {'#34d399' if m_open else '#94a3b8'}; font-weight: 600; margin-bottom: 4px;">{m_badge}</div>
        <div style="color: #cbd5e1;">IST: {ist_now.strftime('%H:%M:%S')} • {ist_now.strftime('%d %b %Y')}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Emergency Kill Switch in Sidebar
if risk_authority.kill_switch_active:
    st.sidebar.error("🚨 KILL-SWITCH TRIPPED")
    if st.sidebar.button("Reset Kill-Switch", key="sb_root_reset", use_container_width=True):
        risk_authority.reset_kill_switch()
        st.rerun()
else:
    if st.sidebar.button("🚨 Emergency Kill-Switch", key="sb_root_halt", type="secondary", use_container_width=True):
        risk_authority.trip_kill_switch("Emergency halt from sidebar")
        st.rerun()

st.sidebar.markdown("---")

# Experience Level Mode
exp_mode = st.sidebar.radio(
    "Interface Mode",
    ["Beginner Mode", "Advanced Mode"],
    index=0 if "Beginner" in st.session_state.get("ui_experience_level", "Beginner Mode") else 1,
    help="Beginner mode includes guided builders and explanations. Advanced mode exposes deep quantitative analytics.",
)
st.session_state["ui_experience_level"] = exp_mode

st.sidebar.markdown("---")

from app.ui.pages.adaptive import render_adaptive_page

PAGES = {
    "1. Overview": render_overview_page,
    "2. Market Terminal": render_terminal_page,
    "3. Strategy Laboratory": render_strategies_page,
    "4. Backtesting Laboratory": render_backtest_page,
    "5. Paper Trading": render_paper_trading_page,
    "6. Portfolio Analytics": render_portfolio_page,
    "7. Adaptive Strategy Center": render_adaptive_page,
    "8. Ensemble Monitor": render_ensemble_page,
    "9. Options Analytics": render_options_page,
    "10. Alert Center": render_alerts_page,
    "11. Risk Center": render_risk_page,
    "12. Integrations": render_integrations_page,
    "13. Settings and Audit": render_settings_page,
}

selected_page = st.sidebar.radio("Navigation", list(PAGES.keys()))

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 AlgoTrade AI • Financial Risk Engineering • SEBI / NSE Compliant Architecture")

# Render selected page
PAGES[selected_page]()

