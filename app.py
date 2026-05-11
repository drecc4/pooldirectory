"""Pool Pals · Dashboard (page 1, default landing).

Read-only view safe to share with collaborators.
The Capture page is password-gated separately.

Run:
    streamlit run Dashboard.py
"""
from __future__ import annotations

import streamlit as st

from shared import (
    add_effective_status,
    add_lifecycle,
    apply_global_styling,
    init_state,
    load_dataset,
    render_family_breakdown,
    render_neighborhood_cards,
    render_overview_kpis,
    render_property_table,
    render_status_map,
)

st.set_page_config(
    page_title="Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_global_styling()
init_state()

# Load data (HOA / common parcels excluded everywhere)
df = load_dataset()
df = df[df["cm"] == 0].reset_index(drop=True)
work = add_effective_status(df, st.session_state.markings)
work = add_lifecycle(work, st.session_state.lifecycle)

# === Page title ===
st.title("Pool Dashboard")
st.divider()

# === Overall summary section (anchored to full dataset) ===
render_overview_kpis(work)

st.markdown("##### Neighborhood Group Summary")
render_family_breakdown(work)

st.markdown("---")

# === Drill-down section ===
filter_col, _ = st.columns(2)
with filter_col:
    groups = sorted(df["nf"].unique().tolist())
    group = st.selectbox(
        "Filter by Neighborhood Group",
        groups,
        key="dash_group",
        help="Filters the map, neighborhood breakdown, and property table below.",
    )

scope = work[work["nf"] == group].reset_index(drop=True)

# Map (2/3) + transposed neighborhood metrics (1/3)
map_col, summary_col = st.columns([2, 1])

with map_col:
    map_style = st.radio(
        "Map style",
        ["Map", "Satellite"],
        key="dash_map_style",
        horizontal=True,
        label_visibility="collapsed",
    )
    render_status_map(scope, height=520, tiles=map_style)

with summary_col:
    render_neighborhood_cards(scope)

# === Property-level detail ===
st.markdown("---")
st.markdown(f"#### Properties · {group}")
render_property_table(scope)
