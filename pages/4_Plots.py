import io
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from modules.plotting import plot_speedmap, _get_fastest_lap_telemetry, plot_speedmap_from_telemetry
from modules.utils import normalize_name  
st.set_page_config(page_title="F1 Telemetry Plots", page_icon="📊", layout="wide")
st.title("Track Maps")

top_candidates = st.session_state.get("top_candidates", pd.DataFrame())  
selected_driver = st.session_state.get("selected_driver", "")

if top_candidates.empty or not selected_driver:
    st.info("Open **Drivers** page first, pick a driver and Top-N. Then come back here.")
    st.stop()

surname = str(selected_driver).split()[-1]
driver_code = normalize_name(surname)[:3].upper()

with st.sidebar:
    st.header("Plot controls")
    max_n = int(min(10, len(top_candidates))) if len(top_candidates) else 1
    n_plot = st.slider("How many top races?", 1, max_n, min(max_n, 3), key="n_plot_plots")

    layout = st.radio("Layout", ["One per race", "Overlay"], horizontal=True, key="layout_mode")
    cmap_name = st.selectbox("Colormap", ["viridis", "plasma", "inferno", "magma", "turbo", "cividis"], index=0)
    lw = st.slider("Line width", 1.0, 6.0, 3.0, 0.5)
    annotate = st.checkbox("Annotate corner numbers", value=True)
    normalize_scale = st.checkbox("Normalize color scale across all laps", value=True)

sel_top = top_candidates[["year", "name"]].head(n_plot).reset_index(drop=True)

telemetry_list = []
corners_list = []
speeds_all = []

with st.spinner("Loading telemetry…"):
    for _, r in sel_top.iterrows():
        year, gp = int(r["year"]), str(r["name"])
        if year < 2018:
            telemetry_list.append(None); corners_list.append(None)
            continue
        tel, corners = _get_fastest_lap_telemetry(year, gp, "R", driver_code)
        telemetry_list.append(tel)
        corners_list.append(corners)
        if tel is not None and not tel.empty and "Speed" in tel.columns:
            speeds_all.append(tel["Speed"].to_numpy(dtype=float))

if normalize_scale and speeds_all:
    all_speeds = np.concatenate(speeds_all)
    vmin_glob, vmax_glob = float(np.nanmin(all_speeds)), float(np.nanmax(all_speeds))
else:
    vmin_glob = vmax_glob = None

if layout == "One per race":
    cols = st.columns(2)
    figs = []
    for i, r in sel_top.iterrows():
        year, gp = int(r["year"]), str(r["name"])
        tel = telemetry_list[i]
        cor = corners_list[i]
        if tel is None or tel.empty:
            continue
        fig = plot_speedmap(year, gp, "R", driver_code,
                            cmap=cmap_name, lw=lw,
                            normalize=(vmin_glob, vmax_glob) if vmin_glob is not None else None,
                            annotate_corners=annotate)
        figs.append(fig)
        with cols[i % 2]:
            st.pyplot(fig, clear_figure=False)

    if figs:
        out = io.BytesIO()
        figs[-1].savefig(out, format="png", dpi=200, bbox_inches="tight")
        st.download_button(
            "Download last figure as PNG",
            data=out.getvalue(),
            file_name="speedmap.png",
            mime="image/png",
            key="dl_speedmap_single",
        )

else:
    fig, ax = plt.subplots(figsize=(8, 8))
    for i, r in sel_top.iterrows():
        year, gp = int(r["year"]), str(r["name"])
        tel = telemetry_list[i]
        if tel is None or tel.empty or not set(["X","Y","Speed"]).issubset(tel.columns):
            continue

        x = tel["X"].to_numpy(dtype=float)
        y = tel["Y"].to_numpy(dtype=float)
        s = tel["Speed"].to_numpy(dtype=float)
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segs = np.concatenate([points[:-1], points[1:]], axis=1)

        lc = LineCollection(segs, array=s[:-1], cmap=cmap_name, linewidths=lw, alpha=0.9)
        if vmin_glob is not None and vmax_glob is not None:
            lc.set_clim(vmin_glob, vmax_glob)
        ax.add_collection(lc)
        ax.text(x[0], y[0], f"{year} {gp}", fontsize=7)

    ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale()
    ax.set_title(f"{selected_driver} • Overlay of {len(sel_top)} top races")
    ax.set_xticks([]); ax.set_yticks([])

    mappable = plt.cm.ScalarMappable(cmap=cmap_name)
    if vmin_glob is not None and vmax_glob is not None:
        mappable.set_clim(vmin_glob, vmax_glob)
    else:
        if speeds_all:
            mappable.set_clim(float(np.nanmin(all_speeds)), float(np.nanmax(all_speeds)))
    cb = plt.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Speed (km/h)")

    st.pyplot(fig, clear_figure=False)

    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=200, bbox_inches="tight")
    st.download_button(
        "Download overlay figure as PNG",
        data=out.getvalue(),
        file_name="speedmap_overlay.png",
        mime="image/png",
        key="dl_speedmap_overlay",
    )
