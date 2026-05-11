"""Shared utilities for the Pool Pals Streamlit app.

State files written to $POOL_PALS_DATA_DIR (default /data):
    pool_pals_data.json     — primary source data (read-only)
    *geocodio*.csv          — fallback source (read-only)
    markings.csv            — user Y/N has-pool overrides (auto-created)
    notes.csv               — per-property notes (auto-created)
    lifecycle.csv           — marketing date + customer status (auto-created)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import folium
import pandas as pd
import streamlit as st


# ─── Configuration ─────────────────────────────────────────────────────────
# Default data dir is `./data` next to this file. Override via env var
# (e.g. POOL_PALS_DATA_DIR=/data for Docker/server deployments).
_THIS_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("POOL_PALS_DATA_DIR", _THIS_DIR / "data"))
MARKINGS_FILE = DATA_DIR / "markings.csv"
NOTES_FILE = DATA_DIR / "notes.csv"
LIFECYCLE_FILE = DATA_DIR / "lifecycle.csv"

# Brand
POOL = "#0891b2"
POOL_DARK = "#155e75"
NEUTRAL = "#1c1917"

# Status colors. Priority cascade:
# Customer > Interested > Marketing sent > Has pool > No pool > Skipped > Unmarked
DISPLAY_STATUS_COLORS = {
    "Customer":       "#059669",   # emerald-600
    "Interested":     "#eab308",   # yellow-500
    "Marketing sent": "#f97316",   # orange-500
    "Has pool":       POOL,
    "Skipped":        "#a8a29e",   # stone-400
    "No pool":        "#44403c",   # stone-700
    "Unmarked":       "#e7e5e4",   # stone-200
}

# Bottom-up draw order so high priority renders on top
DISPLAY_STATUS_PLOT_ORDER = [
    "Unmarked", "No pool", "Skipped", "Has pool",
    "Marketing sent", "Interested", "Customer",
]

# Map tile sources (Google, for capture-page satellite)
TILE_SOURCES = {
    "Hybrid":    "https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Satellite": "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Street":    "https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
}


# ─── Styling ───────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
 
html, body, [class*="st-"], .stApp { font-family: 'IBM Plex Sans', -apple-system, sans-serif; }
h1, h2, h3, h4 { font-family: 'Fraunces', Georgia, serif; letter-spacing: -0.01em; font-weight: 600; }
.stApp { background-color: #fafaf9; }
[data-testid="stSidebar"] { background-color: #f5f5f4; }
[data-testid="stMetricValue"] { font-family: 'Fraunces', Georgia, serif; font-size: 1.7rem !important; font-weight: 600; color: #1c1917; }
[data-testid="stMetricLabel"] { text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.7rem !important; color: #78716c; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; color: #78716c !important; }
 
.address-display { font-family: 'Fraunces', Georgia, serif; font-size: 2rem; font-weight: 600; color: #1c1917; line-height: 1.1; margin: 0; }
.address-meta { color: #78716c; font-size: 0.85rem; }
.address-full { color: #78716c; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }
.position-counter { font-family: 'IBM Plex Mono', monospace; color: #78716c; font-size: 0.85rem; text-align: right; }
.brand { font-family: 'Fraunces', Georgia, serif; font-size: 1.8rem; font-weight: 600; color: #1c1917; }
.brand em { color: #155e75; font-style: italic; }
.scope-label { color: #78716c; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
 
.pill { padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 500; display: inline-block; margin-right: 4px; }
.pill-y { background: #0891b2; color: white; }
.pill-n { background: #44403c; color: white; }
.pill-s { background: #fef3c7; color: #92400e; }
.pill-u { background: #f5f5f4; color: #57534e; border: 1px solid #e7e5e4; }
.pill-mkt { background: #f97316; color: white; }
.pill-int { background: #eab308; color: white; }
.pill-cust { background: #059669; color: white; }
.pill-decl { background: #f5f5f4; color: #57534e; border: 1px solid #d6d3d1; }
 
.nbhd-card-scroll {
    height: 520px;
    overflow-y: auto;
    padding-right: 6px;
}
.nbhd-card-scroll::-webkit-scrollbar {
    width: 8px;
}
.nbhd-card-scroll::-webkit-scrollbar-track {
    background: #f5f5f4;
    border-radius: 4px;
}
.nbhd-card-scroll::-webkit-scrollbar-thumb {
    background: #d6d3d1;
    border-radius: 4px;
}
.nbhd-card-scroll::-webkit-scrollbar-thumb:hover {
    background: #a8a29e;
}
.nbhd-card {
    background: white;
    border: 1px solid #e7e5e4;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.nbhd-card-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1c1917;
    margin-bottom: 8px;
    line-height: 1.2;
}
.nbhd-card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 12px;
    row-gap: 4px;
    font-size: 0.8rem;
}
.nbhd-card-label {
    color: #78716c;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.65rem;
    font-weight: 500;
}
.nbhd-card-value {
    text-align: right;
    font-family: 'IBM Plex Mono', monospace;
    color: #1c1917;
    font-weight: 500;
}
.nbhd-card-poolrate {
    color: #0891b2;
    font-weight: 600;
}
</style>
"""
 
 
def apply_global_styling():
    st.markdown(CSS, unsafe_allow_html=True)
 
 
# ─── Data loading ──────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_dataset() -> pd.DataFrame:
    if not DATA_DIR.exists():
        st.error(f"Data directory `{DATA_DIR}` does not exist.")
        st.stop()
 
    json_files = sorted(DATA_DIR.glob("pool_pals_data*.json"))
    if json_files:
        with open(json_files[0]) as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        df["pid"] = df["pid"].astype(str)
        for col in ("lat", "lng", "av"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ("nf", "nn", "sub", "on", "addr", "disp", "hp"):
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].fillna("").astype(str)
        if "cm" not in df.columns:
            df["cm"] = 0
        df["cm"] = pd.to_numeric(df["cm"], errors="coerce").fillna(0).astype(int)
        df = df.dropna(subset=["lat", "lng"]).reset_index(drop=True)
        return df
 
    csv_files = sorted(DATA_DIR.glob("*[Gg]eocodio*.csv"))
    if csv_files:
        return parse_geocodio_csv(csv_files[0])
 
    st.error(
        f"No data file found in `{DATA_DIR}/`. Drop in `pool_pals_data.json` "
        f"or a Geocodio CSV (`*geocodio*.csv`)."
    )
    st.stop()
 
 
def parse_geocodio_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str).fillna("")
    df = pd.DataFrame()
    df["pid"] = raw["PropertyID"].astype(str).str.strip()
    df["nf"] = raw["NeighborhoodFamily"].str.strip()
    nn_clean = raw["NeighborhoodName"].str.strip()
    df["nn"] = nn_clean.where(nn_clean != "", df["nf"])
    df["sub"] = raw.get("SubdivisionID", pd.Series([""] * len(raw))).str.strip()
    df["on"] = raw.get("Owner Name", pd.Series([""] * len(raw))).str.strip()
    df["av"] = pd.to_numeric(raw["AppraisedValue"], errors="coerce").fillna(0).astype(int)
    hp = raw["HasPool?"].str.strip().str.upper()
    df["hp"] = hp.where(hp.isin(["Y", "N"]), "")
    df["lat"] = pd.to_numeric(raw["Geocodio Latitude"], errors="coerce")
    df["lng"] = pd.to_numeric(raw["Geocodio Longitude"], errors="coerce")
    house_num = raw["Geocodio House Number"].str.replace(r"\.0$", "", regex=True).str.strip()
    street = raw["Geocodio Street"].str.strip()
    df["disp"] = (house_num + " " + street).str.strip()
    line1 = raw["Geocodio Address Line 1"].str.strip()
    line3 = raw["Geocodio Address Line 3"].str.strip()
    df["addr"] = (line1 + ", " + line3).str.strip(", ").str.strip()
    owner_upper = df["on"].str.upper()
    is_hoa = owner_upper.str.contains("HOA|HOMEOWNERS|ASSOCIATION|TOLL TX", na=False, regex=True)
    is_low = df["av"] < 5000
    df["cm"] = (is_hoa | is_low).astype(int)
    return df.dropna(subset=["lat", "lng"]).reset_index(drop=True)
 
 
# ─── State persistence ─────────────────────────────────────────────────────
def load_markings() -> dict:
    if MARKINGS_FILE.exists():
        try:
            df = pd.read_csv(MARKINGS_FILE, dtype={"pid": str, "has_pool": str}).fillna("")
            return dict(zip(df["pid"], df["has_pool"]))
        except Exception:
            return {}
    return {}
 
 
def save_markings(markings: dict):
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    df = pd.DataFrame([{"pid": k, "has_pool": v} for k, v in markings.items() if v])
    df.to_csv(MARKINGS_FILE, index=False)
 
 
def load_notes() -> dict:
    if NOTES_FILE.exists():
        try:
            df = pd.read_csv(NOTES_FILE, dtype={"pid": str, "note": str}).fillna("")
            return dict(zip(df["pid"], df["note"]))
        except Exception:
            return {}
    return {}
 
 
def save_notes(notes: dict):
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    df = pd.DataFrame([{"pid": k, "note": v} for k, v in notes.items() if v])
    df.to_csv(NOTES_FILE, index=False)
 
 
def load_lifecycle() -> dict:
    """Returns {pid: {"marketing_date": "YYYY-MM-DD", "customer_status": "..."}}"""
    if LIFECYCLE_FILE.exists():
        try:
            df = pd.read_csv(LIFECYCLE_FILE, dtype=str).fillna("")
            out = {}
            for _, row in df.iterrows():
                out[row["pid"]] = {
                    "marketing_date": row.get("marketing_date", ""),
                    "customer_status": row.get("customer_status", ""),
                }
            return out
        except Exception:
            return {}
    return {}
 
 
def save_lifecycle(lifecycle: dict):
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    rows = []
    for pid, vals in lifecycle.items():
        md = vals.get("marketing_date", "") or ""
        cs = vals.get("customer_status", "") or ""
        if md or cs:
            rows.append({"pid": pid, "marketing_date": md, "customer_status": cs})
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["pid", "marketing_date", "customer_status"])
    df.to_csv(LIFECYCLE_FILE, index=False)
 
 
def init_state():
    if "markings" not in st.session_state:
        st.session_state.markings = load_markings()
    if "notes" not in st.session_state:
        st.session_state.notes = load_notes()
    if "lifecycle" not in st.session_state:
        st.session_state.lifecycle = load_lifecycle()
 
 
# ─── Domain helpers ────────────────────────────────────────────────────────
def add_effective_status(df: pd.DataFrame, markings: dict) -> pd.DataFrame:
    """User markings override the source `hp` column. Output column: `es`."""
    out = df.copy()
    mark_series = out["pid"].map(markings)
    out["es"] = mark_series.where(
        mark_series.notna() & (mark_series != ""), out["hp"]
    ).fillna("")
    return out
 
 
def add_lifecycle(df: pd.DataFrame, lifecycle: dict) -> pd.DataFrame:
    """Add marketing_date, customer_status, and derived display_status columns."""
    out = df.copy()
    out["marketing_date"] = out["pid"].map(
        lambda p: lifecycle.get(p, {}).get("marketing_date", "") if isinstance(p, str) else ""
    ).fillna("")
    out["customer_status"] = out["pid"].map(
        lambda p: lifecycle.get(p, {}).get("customer_status", "") if isinstance(p, str) else ""
    ).fillna("")
    out["display_status"] = out.apply(_derive_display_status, axis=1)
    return out
 
 
def _derive_display_status(row) -> str:
    cs = row.get("customer_status", "")
    if cs == "customer":
        return "Customer"
    if cs == "interested":
        return "Interested"
    # 'declined' folds into Marketing sent (they were marketed but said no)
    if cs == "declined" or row.get("marketing_date"):
        return "Marketing sent"
    es = row.get("es", "")
    if es == "Y":
        return "Has pool"
    if es == "N":
        return "No pool"
    if es == "S":
        return "Skipped"
    return "Unmarked"
 
 
def fmt_money(v) -> str:
    if v is None or pd.isna(v) or v == 0:
        return "—"
    v = float(v)
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1000:
        return f"${round(v / 1000):,}k"
    return f"${int(v):,}"
 
 
def fmt_full_money(v) -> str:
    if v is None or pd.isna(v) or v == 0:
        return "—"
    return f"${int(v):,}"
 
 
def status_pill_html(status: str) -> str:
    if status == "Y":
        return '<span class="pill pill-y">Has pool</span>'
    if status == "N":
        return '<span class="pill pill-n">No pool</span>'
    if status == "S":
        return '<span class="pill pill-s">Skipped</span>'
    return '<span class="pill pill-u">Unmarked</span>'
 
 
# ─── Rendering ─────────────────────────────────────────────────────────────
def render_brand_header():
    st.markdown('<div class="brand">Pool <em>Pals</em></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#78716c; font-size:0.85rem; margin-top:-6px; margin-bottom:18px;">'
        'Pool detection & customer pipeline</div>',
        unsafe_allow_html=True,
    )
 
 
def render_overview_kpis(scope: pd.DataFrame):
    """Top-level KPIs: Total / Pools / Marked % / Pool %.
    Anchored to the dataset passed in — typically the full `work` (no filtering)."""
    total = len(scope)
    yes = int((scope["es"] == "Y").sum())
    no = int((scope["es"] == "N").sum())
    marked = yes + no
    marked_pct = marked / total if total else 0
    pool_pct = yes / total if total else 0
 
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total properties", f"{total:,}")
    with c2:
        st.metric("Pools confirmed", f"{yes:,}")
    with c3:
        st.metric("Marked %", f"{marked_pct * 100:.0f}%", f"{marked:,} of {total:,}")
    with c4:
        st.metric("Pool %", f"{pool_pct * 100:.1f}%", f"{yes:,} of {total:,}")
 
 
def render_kpis(scope: pd.DataFrame, scope_label: str = ""):
    """Legacy four-KPI row including Marketing/Customers. Kept for any callers needing it."""
    total = len(scope)
    yes = int((scope["es"] == "Y").sum())
    pool_rate = yes / total if total else 0
    marketing_sent = int((scope["marketing_date"] != "").sum())
    customers = int((scope["customer_status"] == "customer").sum())
    interested = int((scope["customer_status"] == "interested").sum())
    conversion = customers / marketing_sent if marketing_sent else 0
 
    if scope_label:
        st.markdown(f'<div class="scope-label">{scope_label}</div>', unsafe_allow_html=True)
 
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total properties", f"{total:,}")
    with c2:
        st.metric("Pools confirmed", f"{yes:,}", f"{pool_rate * 100:.1f}% of homes")
    with c3:
        delta = f"{(marketing_sent / yes * 100):.0f}% of pool homes" if yes else None
        st.metric("Marketing sent", f"{marketing_sent:,}", delta)
    with c4:
        if marketing_sent:
            delta = f"{conversion * 100:.0f}% conversion · {interested} interested"
        else:
            delta = f"{interested:,} interested" if interested else None
        st.metric("Customers", f"{customers:,}", delta)
 
 
def render_status_map(df: pd.DataFrame, height: int = 500, tiles: str = "Map"):
    """Plotly scatter_mapbox — color-coded by display_status, auto-zoomed.
 
    tiles: "Map" (carto-positron, clean cartography) or "Satellite" (Google hybrid imagery).
    """
    import plotly.express as px
 
    if len(df) == 0:
        st.info("No properties in scope.")
        return
 
    map_df = df.copy()
    map_df["av_fmt"] = map_df["av"].apply(fmt_money)
 
    # Auto-center on scope
    center_lat = float(map_df["lat"].mean())
    center_lng = float(map_df["lng"].mean())
 
    # Auto-zoom based on bbox span
    lat_span = float(map_df["lat"].max() - map_df["lat"].min())
    lng_span = float(map_df["lng"].max() - map_df["lng"].min())
    span = max(lat_span, lng_span)
    if span < 0.005:
        zoom = 16
    elif span < 0.01:
        zoom = 15
    elif span < 0.02:
        zoom = 14
    elif span < 0.04:
        zoom = 13
    elif span < 0.08:
        zoom = 12
    else:
        zoom = 11
 
    fig = px.scatter_mapbox(
        map_df, lat="lat", lon="lng",
        color="display_status",
        color_discrete_map=DISPLAY_STATUS_COLORS,
        category_orders={"display_status": DISPLAY_STATUS_PLOT_ORDER},
        hover_name="disp",
        hover_data={
            "nf": True, "nn": True, "on": True, "av_fmt": True,
            "lat": False, "lng": False, "display_status": True,
        },
        labels={
            "display_status": "Status",
            "nf": "Neighborhood Group",
            "nn": "Neighborhood",
            "on": "Owner",
            "av_fmt": "Appraised",
        },
        zoom=zoom, center={"lat": center_lat, "lon": center_lng},
        height=height,
        opacity=0.9,
    )
    fig.update_traces(marker=dict(size=10))
 
    if tiles == "Satellite":
        # Google hybrid (satellite + place labels) as a raster underlay
        fig.update_layout(
            mapbox=dict(
                style="white-bg",
                layers=[{
                    "below": "traces",
                    "sourcetype": "raster",
                    "source": ["https://mt0.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"],
                    "sourceattribution": "Google",
                }],
            )
        )
        # Bigger markers + white outline for visibility on busy aerial imagery
        fig.update_traces(marker=dict(size=11))
    else:
        fig.update_layout(mapbox_style="carto-positron")
 
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            yanchor="top", y=0.99, xanchor="left", x=0.01,
            bgcolor="rgba(255,255,255,0.95)", bordercolor="#e7e5e4",
            borderwidth=1, title=None,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
 
 
@st.cache_data(max_entries=60, show_spinner=False)
def render_capture_map(pid: str, lat: float, lng: float, disp: str, layer: str) -> str:
    """Folium map for the capture page (single-property satellite/hybrid/street)."""
    tile_url = TILE_SOURCES.get(layer, TILE_SOURCES["Hybrid"])
    m = folium.Map(location=[lat, lng], zoom_start=20, tiles=None, max_zoom=21, control_scale=True)
    folium.TileLayer(
        tiles=tile_url, attr="Google", name=layer, subdomains="0123", max_zoom=21,
    ).add_to(m)
    folium.Marker(
        [lat, lng], tooltip=disp,
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
    ).add_to(m)
    return m.get_root().render()
 
 
def _build_breakdown_row(name: str, sub: pd.DataFrame, name_col: str) -> dict:
    total = len(sub)
    yes = int((sub["es"] == "Y").sum())
    no = int((sub["es"] == "N").sum())
    marked = yes + no
    return {
        name_col: name,
        "Total": total,
        "Marked": marked,
        "Marked %": (marked / total * 100) if total else 0.0,
        "Pools": yes,
        "Pool %": (yes / total * 100) if total else 0.0,
    }
 
 
def _breakdown_column_config(name_col: str) -> dict:
    """Column widths for breakdown tables. Group/neighborhood name gets the most space.
    Percentages stored as floats (0-100) and formatted via printf-style; NumberColumn
    right-aligns header + values automatically."""
    return {
        name_col: st.column_config.TextColumn(name_col, width="medium"),
        "Total": st.column_config.NumberColumn("Total", width="small", format="%d"),
        "Marked": st.column_config.NumberColumn("Marked", width="small", format="%d"),
        "Marked %": st.column_config.NumberColumn("Marked %", width="small", format="%.0f%%"),
        "Pools": st.column_config.NumberColumn("Pools", width="small", format="%d"),
        "Pool %": st.column_config.NumberColumn("Pool %", width="small", format="%.1f%%"),
    }
 
 
def render_family_breakdown(scope: pd.DataFrame):
    rows = [_build_breakdown_row(fam, sub, "Neighborhood Group") for fam, sub in scope.groupby("nf")]
    df = pd.DataFrame(rows).sort_values("Pools", ascending=False).reset_index(drop=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=_breakdown_column_config("Neighborhood Group"),
    )
 
 
def render_neighborhood_breakdown(scope: pd.DataFrame):
    rows = [_build_breakdown_row(nbhd, sub, "Neighborhood") for nbhd, sub in scope.groupby("nn")]
    df = pd.DataFrame(rows).sort_values("Pools", ascending=False).reset_index(drop=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=_breakdown_column_config("Neighborhood"),
    )
 
 
def render_neighborhood_cards(scope: pd.DataFrame):
    """Renders a stacked column of compact cards, one per neighborhood.
    Each card shows the same data as the breakdown table but vertically arranged
    so all neighborhoods are visible without horizontal scroll.
    Sorted by Pool % descending (most pool-rich at top)."""
    nbhds = sorted(scope["nn"].unique().tolist())
    if not nbhds:
        st.info("No data")
        return
 
    # Compute stats per neighborhood
    cards = []
    for nbhd in nbhds:
        sub = scope[scope["nn"] == nbhd]
        total = len(sub)
        yes = int((sub["es"] == "Y").sum())
        no = int((sub["es"] == "N").sum())
        marked = yes + no
        cards.append({
            "name": nbhd,
            "total": total,
            "marked": marked,
            "marked_pct": (marked / total * 100) if total else 0,
            "pools": yes,
            "pool_pct": (yes / total * 100) if total else 0,
        })
 
    # Sort by Pool % desc, then by total desc as tiebreaker
    cards.sort(key=lambda c: (-c["pool_pct"], -c["total"]))
 
    html_parts = ['<div class="nbhd-card-scroll">']
    for c in cards:
        html_parts.append(f"""
<div class="nbhd-card">
    <div class="nbhd-card-title">{c["name"]}</div>
    <div class="nbhd-card-grid">
        <div class="nbhd-card-label">Total</div>
        <div class="nbhd-card-value">{c["total"]:,}</div>
        <div class="nbhd-card-label">Marked</div>
        <div class="nbhd-card-value">{c["marked"]:,} <span style="color:#a8a29e;">({c["marked_pct"]:.0f}%)</span></div>
        <div class="nbhd-card-label">Pools</div>
        <div class="nbhd-card-value">{c["pools"]:,}</div>
        <div class="nbhd-card-label">Pool %</div>
        <div class="nbhd-card-value nbhd-card-poolrate">{c["pool_pct"]:.1f}%</div>
    </div>
</div>""")
    html_parts.append('</div>')
 
    st.markdown("\n".join(html_parts), unsafe_allow_html=True)
 
 
def render_property_table(scope: pd.DataFrame):
    """Property-level data table with two filters (Group + Neighborhood), search, and downloads."""
    # Two filters side-by-side
    f1, f2 = st.columns(2)
    with f1:
        groups = ["All"] + sorted(scope["nf"].unique().tolist())
        group_filter = st.selectbox("Neighborhood Group", groups, key="prop_group")
    with f2:
        if group_filter == "All":
            nbhds = ["All"] + sorted(scope["nn"].unique().tolist())
        else:
            nbhds = ["All"] + sorted(scope[scope["nf"] == group_filter]["nn"].unique().tolist())
        nbhd_filter = st.selectbox("Neighborhood", nbhds, key="prop_nbhd")
 
    work = scope.copy()
    if group_filter != "All":
        work = work[work["nf"] == group_filter]
    if nbhd_filter != "All":
        work = work[work["nn"] == nbhd_filter]
 
    search = st.text_input(
        "Search property",
        key="prop_search",
        placeholder="Address, owner, or property ID…",
    )
 
    if search:
        s = search.lower().strip()
        mask = (
            work["disp"].str.lower().str.contains(s, na=False)
            | work["addr"].str.lower().str.contains(s, na=False)
            | work["on"].str.lower().str.contains(s, na=False)
            | work["nn"].str.lower().str.contains(s, na=False)
            | work["pid"].astype(str).str.contains(s, na=False)
        )
        work = work[mask]
 
    st.caption(f"{len(work):,} properties")
 
    show = pd.DataFrame({
        "Status": work["display_status"].values,
        "Address": work["disp"].values,
        "Neighborhood Group": work["nf"].values,
        "Neighborhood": work["nn"].values,
        "Pool": work["es"].map({"Y": "✓", "N": "✗", "S": "?"}).fillna("—").values,
        "Marketing": work["marketing_date"].apply(lambda d: d if d else "—").values,
        "Customer": work["customer_status"].map({
            "customer": "Customer", "interested": "Interested", "declined": "Declined",
        }).fillna("—").values,
        "Owner": work["on"].fillna("—").values,
        "Appraised": work["av"].apply(fmt_money).values,
    })
 
    # Sort: most actionable first
    priority_map = {
        "Customer": 0, "Interested": 1, "Marketing sent": 2,
        "Has pool": 3, "Skipped": 4, "No pool": 5, "Unmarked": 6,
    }
    show["_p"] = show["Status"].map(priority_map).fillna(7)
    show = show.sort_values(["_p", "Neighborhood Group", "Neighborhood", "Address"]).drop(columns=["_p"])
 
    st.dataframe(show, use_container_width=True, hide_index=True, height=500)
 
    # Exports
    e1, e2, e3 = st.columns(3)
    with e1:
        export = work[[
            "pid", "nf", "nn", "addr", "on", "av", "es",
            "marketing_date", "customer_status", "lat", "lng",
        ]].copy()
        export.columns = [
            "property_id", "neighborhood_group", "neighborhood", "address", "owner",
            "appraised_value", "has_pool", "marketing_date", "customer_status",
            "latitude", "longitude",
        ]
        st.download_button(
            f"⬇ Filtered CSV ({len(export):,})",
            export.to_csv(index=False).encode("utf-8"),
            file_name=f"pool_pals_{pd.Timestamp.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with e2:
        pools = work[work["es"] == "Y"]
        pools_export = pools[["pid", "nf", "nn", "addr", "on", "av", "lat", "lng"]].copy()
        pools_export.columns = [
            "property_id", "neighborhood_group", "neighborhood", "address", "owner",
            "appraised_value", "latitude", "longitude",
        ]
        st.download_button(
            f"⬇ Pools only ({len(pools):,})",
            pools_export.to_csv(index=False).encode("utf-8"),
            file_name=f"pools_{pd.Timestamp.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=len(pools) == 0,
        )
    with e3:
        actionable = work[
            (work["customer_status"].isin(["interested", "customer"]))
            | (work["marketing_date"] != "")
        ]
        actionable_export = actionable[[
            "pid", "nf", "nn", "addr", "on", "av",
            "marketing_date", "customer_status", "lat", "lng",
        ]].copy()
        actionable_export.columns = [
            "property_id", "neighborhood_group", "neighborhood", "address", "owner",
            "appraised_value", "marketing_date", "customer_status",
            "latitude", "longitude",
        ]
        st.download_button(
            f"⬇ Pipeline ({len(actionable):,})",
            actionable_export.to_csv(index=False).encode("utf-8"),
            file_name=f"pipeline_{pd.Timestamp.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=len(actionable) == 0,
        )
