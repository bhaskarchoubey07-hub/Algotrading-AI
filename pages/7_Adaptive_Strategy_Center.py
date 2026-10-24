from pathlib import Path
import sys
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ui.components import apply_custom_theme, render_live_ticker_tape
from app.ui.pages.adaptive import render_adaptive_page

st.set_page_config(page_title="Adaptive Strategy Center — AlgoTrade AI", page_icon="🧠", layout="wide")
apply_custom_theme()
render_live_ticker_tape()
render_adaptive_page()
