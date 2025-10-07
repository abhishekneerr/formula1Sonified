import streamlit as st
import pandas as pd
from modules import data_loader, analysis  # plotting, normalize_name not needed here

st.title("🏎️ F1 Driver Performance Explorer")

# -------------------------------
# Sidebar — only two filters
# -------------------------------
with st.sidebar:
    st.header("Filters")
    year_range = st.slider(
        "Select Year Range",
        min_value=2018,
        max_value=2025,
        value=(2018, 2025)
    )
    wins_only = st.checkbox("Show only winners", value=True)

# -------------------------------
# Load core data (cached)
# -------------------------------
@st.cache_data(show_spinner=False)
def _cached_core_tables():
    return data_loader.load_core_tables()

dfs = _cached_core_tables()
drivers = dfs['drivers'].copy()
races   = dfs['races'].copy()
results = dfs['results'].copy()

# Keep only races within the selected year range
races_in_range = races[(races['year'] >= year_range[0]) & (races['year'] <= year_range[1])]

# Merge results with race + driver data
merged = (
    results
    .merge(races_in_range[['raceId', 'year', 'name', 'date']], on='raceId', how='inner')
    .merge(drivers[['driverId', 'forename', 'surname']], on='driverId', how='left')
)
merged['Driver'] = (merged['forename'].fillna('') + ' ' + merged['surname'].fillna('')).str.strip()

# -------------------------------
# Main screen lists (names only)
# -------------------------------
if wins_only:
    st.subheader(f"Winner names • {year_range[0]}–{year_range[1]}")
    winners_df = (
        merged.loc[merged['positionOrder'] == 1, ['Driver']]
        .dropna()
        .drop_duplicates()
        .sort_values('Driver')
        .reset_index(drop=True)
    )
    winners_df.index = winners_df.index + 1  # Make index start from 1
    st.dataframe(winners_df, use_container_width=True)  # names only


    driver_list = winners_df['Driver'].tolist()
else:
    st.subheader(f"All driver names • {year_range[0]}–{year_range[1]}")
    all_drivers_df = (
        merged[['Driver']]
        .dropna()
        .drop_duplicates()
        .sort_values('Driver')
        .reset_index(drop=True)
    )
    all_drivers_df.index = all_drivers_df.index + 1  # Make index start from 1
    st.dataframe(all_drivers_df, use_container_width=True)  # names only
    driver_list = all_drivers_df['Driver'].tolist()

# Guard: no drivers found -> stop cleanly
if not driver_list:
    st.warning("No drivers found for the selected filters. Try a different year range or toggle.")
    st.stop()

st.markdown("---")

# -------------------------------
# Driver selection (updates with toggle)
# -------------------------------
driver = st.selectbox(
    "Select a driver to view their top performances",
    options=driver_list,
    index=0
)

# -------------------------------
# Top-N performances for selection
# -------------------------------
top_n = st.slider("Top N performances", min_value=1, max_value=10, value=3)

@st.cache_data(show_spinner=False)
def _cached_top_races(dfs, driver_name, n_top, min_year, wins_only):
    # analysis.top_races_for_driver handles filtering by min_year and wins_only
    return analysis.top_races_for_driver(dfs, driver_name, n_top, min_year, wins_only)

top_df = _cached_top_races(
    dfs=dfs,
    driver_name=driver,
    n_top=top_n,
    min_year=year_range[0],
    wins_only=wins_only
)

# Optional: keep top races within upper bound as well (uncomment if needed)
# if 'year' in top_df.columns:
#     top_df = top_df[(top_df['year'] >= year_range[0]) & (top_df['year'] <= year_range[1])]

if top_df.empty:
    st.warning("No races found for the selected filters.")
else:
    st.subheader(f"Top {len(top_df)} races for {driver}")
    display_df = top_df.copy()
    if 'gap_to_winner_s' in display_df.columns:
        display_df['gap_to_winner'] = display_df['gap_to_winner_s'].map(lambda s: f"{s:.3f} s")
        display_df = display_df.drop(columns=['gap_to_winner_s'])
    st.dataframe(display_df.reset_index(drop=True), use_container_width=True)
