import os
import matplotlib.pyplot as plt
import fastf1
import fastf1.plotting as fplot
import numpy as np
from matplotlib.collections import LineCollection

# Setup FastF1 cache
CACHE_DIR = os.path.join("data","CacheFormulaOne")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

def plot_driver_telemetry(year: int, event_name: str, identifier: str, driver_3letter: str):
    """
    Plot Speed vs Distance for the driver's fastest lap in the given session.
    identifier: "R", "Q", "FP1", etc.  driver_3letter: e.g., "VER", "HAM"
    """
    session = fastf1.get_session(year, event_name, identifier)
    session.load()

    laps = session.laps.pick_driver(driver_3letter)
    if laps.empty:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, f"No laps for {driver_3letter} in {event_name} {identifier}",
                ha="center", va="center")
        ax.axis("off")
        return fig

    lap = laps.pick_fastest()
    tel = lap.get_car_data().add_distance()

    fplot.setup_mpl(misc_mpl_mods=False)
    fig, ax = plt.subplots()
    ax.scatter(tel['Distance'], tel['Speed'], s=2)
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_title(f"{driver_3letter} - {event_name} {year} ({identifier}) – fastest lap")
    return fig

def _get_fastest_lap_telemetry(year: int, event_name: str, identifier: str, driver_3letter: str):
    """
    Return telemetry DataFrame for the driver's fastest lap including GPS (X,Y), Speed, Distance
    and the circuit corners df (may be empty).
    """
    session = fastf1.get_session(year, event_name, identifier)
    session.load()

    laps = session.laps.pick_driver(driver_3letter)
    if laps is None or laps.empty:
        return None, None

    lap = laps.pick_fastest()
    try:
        tel = lap.get_telemetry()  # GPS X/Y (post-2018), Speed, Distance, etc.
    except Exception:
        tel = None

    # circuit info (corners)
    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
    except Exception:
        corners = None

    return tel, corners


def plot_speedmap_from_telemetry(tdf, title: str = "", cmap: str = "viridis", lw: float = 3.0,
                                 vmin: float | None = None, vmax: float | None = None,
                                 corners=None, annotate_corners: bool = True):
    """
    Draw a colored polyline by speed using telemetry columns ['X','Y','Speed'] (and optional 'Distance' for corner labels).
    Returns a matplotlib Figure.
    """
    fplot.setup_mpl(misc_mpl_mods=False)
    fig, ax = plt.subplots(figsize=(7, 7))

    if tdf is None or tdf.empty or not set(["X", "Y", "Speed"]).issubset(tdf.columns):
        ax.text(0.5, 0.5, "No telemetry with X/Y/Speed available", ha="center", va="center")
        ax.axis("off")
        return fig

    x = tdf["X"].to_numpy(dtype=float)
    y = tdf["Y"].to_numpy(dtype=float)
    s = tdf["Speed"].to_numpy(dtype=float)

    # Build line segments
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segs = np.concatenate([points[:-1], points[1:]], axis=1)

    lc = LineCollection(segs, array=s[:-1], cmap=cmap, linewidths=lw)
    if vmin is not None and vmax is not None:
        lc.set_clim(vmin=vmin, vmax=vmax)
    ax.add_collection(lc)

    ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale()
    ax.set_title(title)
    ax.set_xticks([]); ax.set_yticks([])

    # colorbar
    mappable = plt.cm.ScalarMappable(cmap=cmap)
    if vmin is not None and vmax is not None:
        mappable.set_clim(vmin, vmax)
    else:
        mappable.set_clim(float(np.nanmin(s)), float(np.nanmax(s)))
    cb = plt.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Speed (km/h)")

    # optional corner labels
    if annotate_corners and corners is not None and not getattr(corners, "empty", True):
        if "Distance" in tdf.columns and "Distance" in corners.columns:
            td = tdf["Distance"].to_numpy(dtype=float)
            for _, c in corners.reset_index(drop=True).iterrows():
                try:
                    d0 = float(c["Distance"])
                except Exception:
                    continue
                idx = int(np.argmin(np.abs(td - d0)))
                x0, y0 = float(tdf.iloc[idx]["X"]), float(tdf.iloc[idx]["Y"])
                label = str(int(c.get("Number", ""))) if c.get("Number") == c.get("Number") else c.get("Letter", "")
                if label:
                    ax.text(x0, y0, label, fontsize=8, weight="bold")

    return fig


def plot_speedmap(year: int, event_name: str, identifier: str, driver_3letter: str,
                  cmap: str = "viridis", lw: float = 3.0,
                  normalize: tuple[float, float] | None = None,
                  annotate_corners: bool = True):
    """
    Convenience wrapper: loads telemetry and draws a speed map.
    normalize = (vmin, vmax) to share color scale across multiple figures, else None.
    """
    tel, corners = _get_fastest_lap_telemetry(year, event_name, identifier, driver_3letter)
    if tel is None or tel.empty:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, f"No telemetry for {driver_3letter} – {event_name} {year} ({identifier})", ha="center", va="center")
        ax.axis("off")
        return fig

    vmin, vmax = (normalize if normalize is not None else (None, None))
    title = f"{driver_3letter} – {event_name} {year} ({identifier})"
    return plot_speedmap_from_telemetry(tel, title=title, cmap=cmap, lw=lw,
                                        vmin=vmin, vmax=vmax,
                                        corners=corners, annotate_corners=annotate_corners)