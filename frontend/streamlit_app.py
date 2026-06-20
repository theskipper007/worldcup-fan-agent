"""Streamlit UI shell — morning digest + public predictor scoreboard.

See ../docs/eval.md and ../docs/agents.md. This is a layout skeleton: it talks to the FastAPI
backend (BACKEND_URL) but the backend endpoints are still stubbed.
"""

from __future__ import annotations

import os

import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="World Cup Fan Agent", page_icon="⚽", layout="wide")
st.title("World Cup Fan Agent ⚽")

digest_tab, scoreboard_tab = st.tabs(["Morning digest", "Predictor scoreboard"])

with digest_tab:
    st.subheader("Your morning digest")
    st.text_input("Followed teams (team ids, comma-separated)", key="teams")
    st.selectbox("Language", ["en", "ta", "zh", "ar"], key="language")
    st.info("Digest generation is not implemented yet — see docs/agents.md.")

with scoreboard_tab:
    st.subheader("Predictor scoreboard — agent vs baseline")
    st.caption("Winner hit-rate, lift over baseline, and recent predictions. See docs/eval.md.")
    st.info("Scoreboard is not implemented yet — sourced from the predictions table.")
