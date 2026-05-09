"""Pool Pals · Capture (page 2).

Password-protected. Set POOL_PALS_PASSWORD env var (or .streamlit/secrets.toml).
Allows marking pool Y/N, recording marketing-sent date, and updating customer status.
"""
from __future__ import annotations

import os
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from shared import (
    add_effective_status,
    add_lifecycle,
    apply_global_styling,
    fmt_full_money,
    init_state,
    load_dataset,
    render_capture_map,
    save_lifecycle,
    save_markings,
    save_notes,
    status_pill_html,
    TILE_SOURCES,
)

st.set_page_config(
    page_title="Pool Pals · Capture",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_global_styling()


# ─── Password gate ─────────────────────────────────────────────────────────
def _get_expected_password() -> str:
    """Resolve the Capture-page password.

    Order of precedence:
      1. POOL_PALS_PASSWORD environment variable
      2. POOL_PALS_PASSWORD entry in .streamlit/secrets.toml
      3. Hardcoded default "Central4$"
    """
    pwd = os.environ.get("POOL_PALS_PASSWORD", "")
    if not pwd:
        try:
            pwd = st.secrets.get("POOL_PALS_PASSWORD", "")  # type: ignore[attr-defined]
        except Exception:
            pwd = ""
    if not pwd:
        pwd = "Central4$"
    return pwd


def check_auth() -> bool:
    if st.session_state.get("capture_auth_ok"):
        return True

    expected = _get_expected_password()

    st.markdown('<div class="brand">Pool <em>Pals</em></div>', unsafe_allow_html=True)
    st.markdown("##### Capture · sign in")
    st.caption("This page is private. Enter password to continue.")

    pwd = st.text_input("Password", type="password", key="cap_pwd_input")
    if pwd:
        if pwd == expected:
            st.session_state.capture_auth_ok = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_auth():
    st.stop()


# ─── Capture view ──────────────────────────────────────────────────────────
init_state()

df = load_dataset()
df = df[df["cm"] == 0].reset_index(drop=True)
work = add_effective_status(df, st.session_state.markings)
work = add_lifecycle(work, st.session_state.lifecycle)

# Sidebar — queue filters
with st.sidebar:
    st.markdown('<div class="brand">Pool <em>Pals</em></div>', unsafe_allow_html=True)
    st.markdown("##### Capture queue")

    groups = ["All"] + sorted(work["nf"].unique().tolist())
    group = st.selectbox("Neighborhood Group", groups, key="cap_group")
    sub_df = work if group == "All" else work[work["nf"] == group]
    nbhds = ["All"] + sorted(sub_df["nn"].unique().tolist())
    neighborhood = st.selectbox("Neighborhood", nbhds, key="cap_nbhd")

    pool_filter = st.radio(
        "Pool status",
        ["Unmarked", "All", "Pools (Y)", "No pool (N)"],
        key="cap_pool_filter",
    )

    lifecycle_filter = st.radio(
        "Lifecycle stage",
        ["All", "Marketing not sent", "Marketing sent", "Interested", "Customers"],
        key="cap_lifecycle_filter",
    )

# Build queue
q = sub_df if group != "All" else work
if neighborhood != "All":
    q = q[q["nn"] == neighborhood]
if pool_filter == "Unmarked":
    q = q[q["es"] == ""]
elif pool_filter == "Pools (Y)":
    q = q[q["es"] == "Y"]
elif pool_filter == "No pool (N)":
    q = q[q["es"] == "N"]
if lifecycle_filter == "Marketing not sent":
    q = q[(q["es"] == "Y") & (q["marketing_date"] == "")]  # only meaningful for pool homes
elif lifecycle_filter == "Marketing sent":
    q = q[q["marketing_date"] != ""]
elif lifecycle_filter == "Interested":
    q = q[q["customer_status"] == "interested"]
elif lifecycle_filter == "Customers":
    q = q[q["customer_status"] == "customer"]
q = q.reset_index(drop=True)
total = len(q)

if total == 0:
    st.info("Queue empty for the current filters.")
    st.stop()

if "capture_idx" not in st.session_state:
    st.session_state.capture_idx = 0
idx = st.session_state.capture_idx
if idx >= total:
    idx = max(0, total - 1)
    st.session_state.capture_idx = idx

current = q.iloc[idx]
pid = current["pid"]
status = current["es"]


def mark_pool(value: str):
    if value == "":
        st.session_state.markings.pop(pid, None)
    else:
        st.session_state.markings[pid] = value
    save_markings(st.session_state.markings)
    # Auto-advance only when the property leaves the queue (non-Unmarked filter)
    if pool_filter != "Unmarked" and value:
        st.session_state.capture_idx = min(idx + 1, total - 1)


def update_lifecycle_field(*, marketing_date=None, customer_status=None):
    cur = st.session_state.lifecycle.get(pid, {"marketing_date": "", "customer_status": ""}).copy()
    if marketing_date is not None:
        cur["marketing_date"] = marketing_date
    if customer_status is not None:
        cur["customer_status"] = customer_status
    if cur["marketing_date"] or cur["customer_status"]:
        st.session_state.lifecycle[pid] = cur
    else:
        st.session_state.lifecycle.pop(pid, None)
    save_lifecycle(st.session_state.lifecycle)


# Header
h1, h2 = st.columns([3, 1])
with h1:
    meta = f"{current['nf']} · {current['nn']}"
    st.markdown(
        f"<div class='address-meta'>{meta}</div>"
        f"<div class='address-display'>{current['disp']}</div>"
        f"<div class='address-full'>{current['addr']}</div>",
        unsafe_allow_html=True,
    )
with h2:
    pills = status_pill_html(status)
    cs = current["customer_status"]
    if cs == "customer":
        pills += '<span class="pill pill-cust">Customer</span>'
    elif cs == "interested":
        pills += '<span class="pill pill-int">Interested</span>'
    elif cs == "declined":
        pills += '<span class="pill pill-decl">Declined</span>'
    if current["marketing_date"] and cs not in ("customer", "interested"):
        pills += '<span class="pill pill-mkt">Marketing sent</span>'
    st.markdown(
        f"<div style='text-align:right; padding-top:4px;'>{pills}</div>"
        f"<div class='position-counter'>{idx + 1} / {total:,}</div>",
        unsafe_allow_html=True,
    )

# Layer toggle (kept outside Folium so it survives reruns)
lcol1, _ = st.columns([3, 5])
with lcol1:
    layer = st.radio(
        "Map layer",
        options=list(TILE_SOURCES.keys()),
        key="cap_map_layer",
        horizontal=True,
        label_visibility="collapsed",
    )

# Map
map_html = render_capture_map(
    pid, float(current["lat"]), float(current["lng"]), current["disp"], layer
)
components.html(map_html, height=500, scrolling=False)

# Pool action bar
st.markdown("##### Pool")
b1, b2, b3, b4 = st.columns([2, 2, 2, 1])
with b1:
    if st.button("✓  Has pool", type="primary", use_container_width=True, key=f"y_{pid}"):
        mark_pool("Y")
        st.rerun()
with b2:
    if st.button("✗  No pool", use_container_width=True, key=f"n_{pid}"):
        mark_pool("N")
        st.rerun()
with b3:
    if st.button("⏭  Skip", use_container_width=True, key=f"s_{pid}"):
        mark_pool("S")
        st.rerun()
with b4:
    if st.button("Unmark", use_container_width=True, key=f"u_{pid}", disabled=status == ""):
        mark_pool("")
        st.rerun()

# Marketing & customer
st.markdown("##### Marketing & customer")
mc1, mc2 = st.columns(2)

with mc1:
    st.markdown("**Marketing**")
    cur_md = current["marketing_date"]
    md_date_val = None
    if cur_md:
        try:
            md_date_val = date.fromisoformat(cur_md)
        except ValueError:
            md_date_val = None

    md1, md2, md3 = st.columns([3, 1, 1])
    with md1:
        new_date = st.date_input(
            "Marketing sent on",
            value=md_date_val,
            key=f"md_{pid}",
            label_visibility="collapsed",
            format="YYYY-MM-DD",
        )
    with md2:
        if st.button("Today", use_container_width=True, key=f"today_{pid}"):
            update_lifecycle_field(marketing_date=date.today().isoformat())
            st.rerun()
    with md3:
        if st.button("Clear", use_container_width=True, key=f"clr_md_{pid}", disabled=not cur_md):
            update_lifecycle_field(marketing_date="")
            st.rerun()

    new_iso = new_date.isoformat() if new_date else ""
    if new_iso != cur_md:
        update_lifecycle_field(marketing_date=new_iso)
        st.rerun()

with mc2:
    st.markdown("**Customer status**")
    options = ["Prospect", "Interested", "Customer", "Declined"]
    label_to_val = {"Prospect": "", "Interested": "interested", "Customer": "customer", "Declined": "declined"}
    val_to_label = {v: k for k, v in label_to_val.items()}

    cur_cs = current["customer_status"]
    cur_label = val_to_label.get(cur_cs, "Prospect")
    new_label = st.radio(
        "Customer status",
        options,
        index=options.index(cur_label),
        key=f"cs_{pid}",
        horizontal=True,
        label_visibility="collapsed",
    )
    new_cs = label_to_val[new_label]
    if new_cs != cur_cs:
        update_lifecycle_field(customer_status=new_cs)
        st.rerun()

# Note
note_val = st.session_state.notes.get(pid, "")
new_note = st.text_input(
    "Note (optional)",
    value=note_val,
    key=f"note_{pid}",
    placeholder="e.g. obscured by trees, called and left voicemail…",
)
if new_note != note_val:
    if new_note:
        st.session_state.notes[pid] = new_note
    else:
        st.session_state.notes.pop(pid, None)
    save_notes(st.session_state.notes)

# Navigation
st.markdown("---")
n1, n2, n3 = st.columns([1, 2, 1])
with n1:
    if st.button("← Previous", use_container_width=True, disabled=idx == 0, key="nav_prev"):
        st.session_state.capture_idx = max(0, idx - 1)
        st.rerun()
with n2:
    st.markdown(
        f"<div style='text-align:center; padding:6px; color:#78716c; "
        f"font-family:IBM Plex Mono,monospace;'>"
        f"position {idx + 1} of {total:,}</div>",
        unsafe_allow_html=True,
    )
with n3:
    if st.button("Next →", use_container_width=True, disabled=idx >= total - 1, key="nav_next"):
        st.session_state.capture_idx = min(total - 1, idx + 1)
        st.rerun()

# Property detail
with st.expander("Property details"):
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("Appraised value", fmt_full_money(current["av"]))
    with d2:
        st.metric("Owner", current.get("on", "—") or "—")
    with d3:
        sub = current.get("sub", "") or "—"
        st.metric("Subdivision", sub)
    with d4:
        st.metric("Property ID", pid)
