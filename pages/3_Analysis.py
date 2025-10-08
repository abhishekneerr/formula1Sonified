import io
from contextlib import redirect_stdout
import pandas as pd
import streamlit as st

from modules.telemetry import analyze_topN_rich

st.set_page_config(page_title="F1 Rich Analysis", page_icon="🧮", layout="wide")
st.title("Telemetry Analysis")

top_candidates = st.session_state.get("top_candidates", pd.DataFrame())  
selected_driver = st.session_state.get("selected_driver", "")

if top_candidates.empty or not selected_driver:
    st.info(
        "Go to **Drivers** page first, pick a driver and Top-N races.\n\n"
        "Alternatively, upload a CSV with columns ['year','name'] and enter a driver below."
    )
    up = st.file_uploader("Upload top candidates CSV", type=["csv"], key="upload_top_candidates")
    selected_driver = st.text_input("Driver full name", value=selected_driver or "", key="driver_name_input")
    if up is not None:
        try:
            top_candidates = pd.read_csv(up)
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")
            st.stop()
    if top_candidates.empty or not selected_driver.strip():
        st.stop()

DEFAULTS = dict(
    slow_thr_kph=120,
    medium_thr_kph=170,
    hairpin_thr_kph=80,
    chicane_gap_m=130,
    chicane_window_m=45,
    complex_span_m=300,
    corner_window_m=30,
    accel_thr_mps2=0.5,
    brake_thr_mps2=-0.7,
    throttle_min_pct=50,
    brake_min_pct=10,
)
if "analysis_params" not in st.session_state:
    st.session_state.analysis_params = DEFAULTS.copy()

def run_analysis(params: dict):
    """Run telemetry analysis and capture printed summary."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        per_race, overall = analyze_topN_rich(
            topN=top_candidates[["year", "name"]],
            driver_full_name=selected_driver,
            **params
        )
    return per_race, overall, buf.getvalue().strip()

left, right = st.columns([0.6, 0.4])
with left:
    st.caption("Selection")
    st.metric("Driver", selected_driver)
    st.write("Top-N races:")
    st.dataframe(top_candidates[["year", "name"]].reset_index(drop=True), use_container_width=True)
with right:
    st.caption("Settings")
    st.write("Results below use the parameters shown in **Advanced**. "
             "Change them and click **Recalculate** to update.")

st.divider()

with st.expander("Advanced (optional) — tune parameters", expanded=False):
    with st.form(key="adv_form"):
        p = st.session_state.analysis_params

        c1, c2, c3 = st.columns(3)
        p["slow_thr_kph"]    = c1.number_input("Slow apex < (kph)",    value=p["slow_thr_kph"],    step=5, key="slow_thr_kph")
        p["medium_thr_kph"]  = c2.number_input("Medium apex < (kph)",  value=p["medium_thr_kph"],  step=5, key="medium_thr_kph")
        p["hairpin_thr_kph"] = c3.number_input("Hairpin apex < (kph)", value=p["hairpin_thr_kph"], step=5, key="hairpin_thr_kph")

        c4, c5, c6 = st.columns(3)
        p["chicane_gap_m"]     = c4.number_input("Chicane gap ≤ (m)",     value=p["chicane_gap_m"],     step=10, key="chicane_gap_m")
        p["chicane_window_m"]  = c5.number_input("Chicane window ± (m)",  value=p["chicane_window_m"],  step=5,  key="chicane_window_m")
        p["complex_span_m"]    = c6.number_input("Corner complex span (m)", value=p["complex_span_m"],  step=25, key="complex_span_m")

        c7, c8, c9 = st.columns(3)
        p["corner_window_m"] = c7.number_input("Corner window ± (m)", value=p["corner_window_m"], step=5, key="corner_window_m")
        p["accel_thr_mps2"]  = c8.number_input("Accel threshold (m/s²)", value=p["accel_thr_mps2"], step=0.1, format="%.2f", key="accel_thr_mps2")
        p["brake_thr_mps2"]  = c9.number_input("Brake threshold (m/s²)", value=p["brake_thr_mps2"], step=0.1, format="%.2f", key="brake_thr_mps2")

        c10, c11 = st.columns(2)
        p["throttle_min_pct"] = c10.number_input("Min throttle for accel zone (%)", value=p["throttle_min_pct"], step=5, key="throttle_min_pct")
        p["brake_min_pct"]    = c11.number_input("Min brake for brake zone (%)",    value=p["brake_min_pct"],    step=5, key="brake_min_pct")

        cols = st.columns([0.3, 0.3, 0.4])
        recalc = cols[0].form_submit_button("Recalculate", use_container_width=True, type="primary")
        reset  = cols[1].form_submit_button("Reset to defaults", use_container_width=True)

        if reset:
            st.session_state.analysis_params = DEFAULTS.copy()
            st.experimental_rerun()
    st.session_state.analysis_params = p

with st.spinner("Computing analysis…"):
    per_race_df, overall_df, printed = run_analysis(st.session_state.analysis_params)
st.markdown("### Summary")
if printed:
    st.code(printed, language="text")

st.markdown("### Per-race metrics")
if per_race_df is None or per_race_df.empty:
    st.info("No telemetry available for these races.")
else:
    st.dataframe(per_race_df, use_container_width=True)

st.markdown("### Overall averages")

if overall_df is not None and not overall_df.empty:
    pretty_names = {
        "mean_kph_straight_drs": "Avg Speed – DRS Straights (km/h)",
        "mean_kph_straight_nondrs": "Avg Speed – Non-DRS Straights (km/h)",
        "p95_kph_straight_drs": "95th Percentile Speed – DRS Straights (km/h)",
        "p95_kph_straight_nondrs": "95th Percentile Speed – Non-DRS Straights (km/h)",
        "coverage_pct_straight_drs": "Track Coverage – DRS Straights (%)",
        "coverage_pct_straight_nondrs": "Track Coverage – Non-DRS Straights (%)",
        "mean_kph_accel_zones": "Avg Speed – Acceleration Zones (km/h)",
        "mean_kph_brake_zones": "Avg Speed – Braking Zones (km/h)",
        "coverage_pct_accel_zones": "Track Coverage – Acceleration Zones (%)",
        "coverage_pct_brake_zones": "Track Coverage – Braking Zones (%)",
        "mean_kph_slow_corners": "Avg Speed – Slow Corners (km/h)",
        "mean_kph_medium_corners": "Avg Speed – Medium Corners (km/h)",
        "mean_kph_high_corners": "Avg Speed – High Corners (km/h)",
        "coverage_pct_slow_corners": "Track Coverage – Slow Corners (%)",
        "coverage_pct_medium_corners": "Track Coverage – Medium Corners (%)",
        "coverage_pct_high_corners": "Track Coverage – High Corners (%)",
        "mean_kph_hairpins": "Avg Speed – Hairpins (km/h)",
        "coverage_pct_hairpins": "Track Coverage – Hairpins (%)",
        "mean_kph_chicane_slow": "Avg Speed – Slow Chicanes (km/h)",
        "mean_kph_chicane_fast": "Avg Speed – Fast Chicanes (km/h)",
        "coverage_pct_chicane_slow": "Track Coverage – Slow Chicanes (%)",
        "coverage_pct_chicane_fast": "Track Coverage – Fast Chicanes (%)",
        "mean_kph_complexes": "Avg Speed – Corner Complexes (km/h)",
        "coverage_pct_complexes": "Track Coverage – Corner Complexes (%)",
    }

    pretty_df = overall_df.copy()
    pretty_df["Metric"] = pretty_df["metric"].map(lambda x: pretty_names.get(x, x))
    pretty_df = pretty_df[["Metric", "value"]].rename(columns={"value": "Value"})

    st.dataframe(pretty_df, use_container_width=True)

    c1, c2 = st.columns(2)
    c1.download_button(
        "Download per-race CSV",
        per_race_df.to_csv(index=False).encode("utf-8"),
        file_name="per_race_rich.csv",
        mime="text/csv",
        key="dl_per_race_csv",
    )
    c2.download_button(
        "Download overall CSV (raw metrics)",
        overall_df.to_csv(index=False).encode("utf-8"),
        file_name="overall_rich.csv",
        mime="text/csv",
        key="dl_overall_csv",
    )
else:
    st.info("Overall averages are empty.")