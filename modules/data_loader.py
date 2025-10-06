import fastf1
import os
import os
import pandas as pd
import kagglehub

DATASET = "rohanrao/formula-1-world-championship-1950-2020"
CIRCUITS_GEO_PATH = "data/circuits_geo.csv"
WEATHER_PATH      = "data/meteorat_2.csv"

def download_dataset() -> str:
    """Download (or reuse cached) dataset and return its local path."""
    path = kagglehub.dataset_download(DATASET)
    return path

def load_core_tables(path: str = None) -> dict:
    """
    Load core CSVs as DataFrames.
    Returns: dict of {drivers, constructors, races, results, qualifying, lap_times, pit_stops, seasons, status, sprint_results}
    """
    if path is None:
        path = download_dataset()

    def _read(name):
        p = os.path.join(path, name)
        return pd.read_csv(p)

    dfs = {
        "drivers": _read("drivers.csv"),
        "constructors": _read("constructors.csv"),
        "races": _read("races.csv"),
        "results": _read("results.csv"),
        "qualifying": _read("qualifying.csv"),
        "lap_times": _read("lap_times.csv"),
        "pit_stops": _read("pit_stops.csv"),
        "seasons": _read("seasons.csv"),
        "status": _read("status.csv"),
    }

    # Use constants for file paths
    circuits_geo_path = os.path.join(path, CIRCUITS_GEO_PATH)
    if os.path.exists(circuits_geo_path):
        dfs["circuits_geo"] = pd.read_csv(circuits_geo_path)
    else:
        dfs["circuits_geo"] = pd.DataFrame()

    weather_path = os.path.join(path, WEATHER_PATH)
    if os.path.exists(weather_path):
        dfs["weather"] = pd.read_csv(weather_path)
    else:
        dfs["weather"] = pd.DataFrame(columns=['GP','Date','Avg_Temperature','Humidity','Precipitation'])

    return dfs
