import streamlit as st
import pandas as pd
from modules import data_loader, analysis, plotting
from modules.utils import normalize_name

st.title("F1 World Championship – Driver Highlights")

with st.sidebar:
    st.header("Filters")
    min_year = st.number_input("Minimum year", min_value=1950, max_value=2025, value=2018)
    wins_only = st.checkbox("Wins only", value=False)
    top_n = st.slider("Top N races", min_value=1, max_value=10, value=3)

    st.caption("Loading drivers/races from Kaggle dataset…")
    dfs = data_loader.load_core_tables()

    drivers = dfs['drivers'].copy()
    drivers['driver_name'] = drivers['forename'] + ' ' + drivers['surname']
    driver = st.selectbox("Driver", sorted(drivers['driver_name'].tolist()), index=0)

st.success("Dataset ready. Select options and scroll down.")

top_df = analysis.top_races_for_driver(dfs, driver_name=driver, n_top=top_n, min_year=min_year, wins_only=wins_only)

if top_df.empty:
    st.warning("No races found for the selected filters.")
else:
    st.subheader(f"Top {len(top_df)} races for {driver} since {min_year}" + (" (wins only)" if wins_only else ""))

    nice = top_df.copy()
    nice['gap_to_winner'] = nice['gap_to_winner_s'].map(lambda s: f"{s:.3f} s")
    nice = nice.drop(columns=['gap_to_winner_s'])
    st.dataframe(nice, use_container_width=True)

    st.subheader("Telemetry (Fastest Lap) for top result")
    first = top_df.iloc[0]
    # quick guess for 3-letter code from surname (works for common cases; can refine later)
    code = normalize_name(driver.split()[-1])[:3].upper()
    fig = plotting.plot_driver_telemetry(int(first['year']), str(first['name']), "R", code)
    st.pyplot(fig, use_container_width=True)

@st.cache_data(show_spinner=False)
def _cached_core_tables():
    return data_loader.load_core_tables()

@st.cache_data(show_spinner=False)
def _cached_top_races(dfs, driver, top_n, min_year, wins_only):
    return analysis.top_races_for_driver(dfs, driver, top_n, min_year, wins_only)

# replace direct calls with:
dfs = _cached_core_tables()
top_df = _cached_top_races(dfs, driver, top_n, min_year, wins_only)

if not top_df.empty:
    st.subheader("Telemetry (Fastest Lap) for top result")

    first = top_df.iloc[0]  # ✅ define 'first' only when the dataframe is valid

    code = normalize_name(driver.split()[-1])[:3].upper()
    fig = plotting.plot_driver_telemetry(int(first['year']), str(first['name']), "R", code)
    st.pyplot(fig, use_container_width=True)
else:
    st.warning("No races found for the selected filters — cannot plot telemetry.")
