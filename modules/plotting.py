import os
import matplotlib.pyplot as plt
import fastf1
import fastf1.plotting as fplot

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
