# modules/telemetry.py
import numpy as np
import pandas as pd
from typing import Tuple

# Reuse your helpers / naming from utils (normalize_name already lives there)
from .utils import normalize_name
import fastf1 as ff1

# Enable FastF1 cache to avoid repeated HTTP
try:
    ff1.Cache.enable_cache(".fastf1cache")
except Exception:
    pass


def _safe_col(df: pd.DataFrame, col: str) -> bool:
    return (col in df.columns) and (df[col].notna().any())


def _speed_kph_to_mps(v: np.ndarray) -> np.ndarray:
    return v / 3.6


def _derive_accel(car_data: pd.DataFrame) -> pd.Series | None:
    """
    Return acceleration in m/s^2 from Speed (km/h) and Time (Timedelta).
    """
    if not (_safe_col(car_data, 'Speed') and _safe_col(car_data, 'Time')):
        return None
    v = _speed_kph_to_mps(car_data['Speed'].to_numpy(dtype=float))
    t = car_data['Time'].dt.total_seconds().to_numpy(dtype=float)
    if t.size < 2:
        return pd.Series(np.zeros(len(car_data)), index=car_data.index, name='acc_mps2')
    dv = np.diff(v, prepend=v[0])
    dt0 = max(t[1] - t[0], 1e-3)
    dt = np.diff(t, prepend=dt0)
    dt[dt == 0] = dt0
    acc = np.divide(dv, dt, out=np.zeros_like(dv), where=dt != 0)
    return pd.Series(acc, index=car_data.index, name='acc_mps2')


def _load_lap_and_circuit(driver_full_name: str, year: int, gp_name: str, fastest_lap_number: int | None = None):
    """
    Load selected lap car_data(+distance) + circuit corners + drs_zones.
    """
    try:
        session = ff1.get_session(int(year), gp_name, "R")
        session.load()
    except Exception as e:
        print(f"[WARN] session load failed for {year} {gp_name}: {e}")
        return None, None, None

    surname = str(driver_full_name).split()[-1]
    driver_code = normalize_name(surname)[:3].upper()

    try:
        laps = session.laps.pick_driver(driver_code)
        if fastest_lap_number is not None and not pd.isna(fastest_lap_number):
            sel = laps[laps['LapNumber'] == int(fastest_lap_number)]
            selected_lap = sel.iloc[0] if not sel.empty else laps.pick_fastest()
        else:
            selected_lap = laps.pick_fastest()
    except Exception as e:
        print(f"[WARN] no laps for {driver_full_name} at {year} {gp_name}: {e}")
        return None, None, None

    try:
        car_data = selected_lap.get_car_data().add_distance()  # Speed, DRS, Throttle, Brake, Distance, Time
    except Exception as e:
        print(f"[WARN] no car_data for {driver_full_name} at {year} {gp_name}: {e}")
        return None, None, None

    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
        drs_zones = getattr(ci, 'drs_zones', None)
        if drs_zones is None:
            drs_zones = pd.DataFrame(columns=['DistanceActivation', 'DistanceEnd'])
    except Exception as e:
        print(f"[WARN] circuit info not available: {e}")
        corners = pd.DataFrame(columns=['Number', 'Letter', 'Distance'])
        drs_zones = pd.DataFrame(columns=['DistanceActivation', 'DistanceEnd'])

    return car_data, corners, drs_zones


def _segment_mask_by_distance(distance_series: pd.Series, start: float, end: float) -> pd.Series:
    return (distance_series >= start) & (distance_series <= end)


def analyze_topN_rich(
    topN: pd.DataFrame,
    driver_full_name: str,
    # corner classification knobs
    slow_thr_kph: float = 120,
    medium_thr_kph: float = 170,
    hairpin_thr_kph: float = 80,
    # chicane / complex grouping knobs
    chicane_gap_m: float = 130,
    chicane_window_m: float = 45,
    complex_span_m: float = 300,
    # straight / accel / brake detection
    corner_window_m: float = 30,
    accel_thr_mps2: float = 0.5,
    brake_thr_mps2: float = -0.7,
    throttle_min_pct: float = 50,
    brake_min_pct: float = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Analyse each race in topN and summarise speeds/coverage for:
      straights (DRS/non-DRS), braking, acceleration, slow/med/high corners,
      chicanes (slow/fast), hairpins, corner complexes.

    Expects topN to contain at least: ['year','name'].
    """
    out_rows = []
    if topN is None or topN.empty:
        return pd.DataFrame(), pd.DataFrame(columns=['metric', 'value'])

    for _, row in topN.iterrows():
        year = int(row['year'])
        gp = row['name']

        if year < 2018:
            print(f"[INFO] Skipping {year} {gp} (telemetry pre-2018 not available).")
            continue

        car_data, corners, drs_zones = _load_lap_and_circuit(driver_full_name, year, gp, fastest_lap_number=None)
        if car_data is None or car_data.empty:
            continue

        dist = car_data['Distance']
        speed = car_data['Speed']
        has_drs_col = _safe_col(car_data, 'DRS')
        has_thr_col = _safe_col(car_data, 'Throttle')
        has_brk_col = _safe_col(car_data, 'Brake')

        acc = _derive_accel(car_data)
        if acc is None:
            acc = pd.Series(np.zeros(len(car_data)), index=car_data.index, name='acc_mps2')

        # tag corners
        is_corner = pd.Series(False, index=car_data.index)
        corner_windows = []
        apex_by_corner = []  # (idx, apex_speed, center_dist)
        if not corners.empty and 'Distance' in corners.columns:
            for idx, c in corners.reset_index(drop=True).iterrows():
                try:
                    d0 = float(c['Distance'])
                except Exception:
                    continue
                mask = (dist >= d0 - corner_window_m) & (dist <= d0 + corner_window_m)
                if mask.any():
                    is_corner |= mask
                    s_vals = speed[mask].to_numpy(dtype=float)
                    if s_vals.size > 0:
                        apex = float(np.nanmin(s_vals))
                        apex_by_corner.append((idx, apex, d0))
                    corner_windows.append((idx, d0, mask))

        is_straight = ~is_corner

        # DRS masks
        if has_drs_col:
            drs_numeric = pd.to_numeric(car_data['DRS'], errors='coerce').fillna(0.0)
            is_drs = (drs_numeric > 0) & is_straight
            is_nondrs = (~(drs_numeric > 0)) & is_straight
        else:
            is_drs = pd.Series(False, index=car_data.index)
            if drs_zones is not None and not drs_zones.empty:
                for _, dz in drs_zones.iterrows():
                    try:
                        a = float(dz.get('DistanceActivation', np.nan))
                        b = float(dz.get('DistanceEnd', np.nan))
                        if np.isnan(a) or np.isnan(b):
                            continue
                        is_drs |= _segment_mask_by_distance(dist, min(a, b), max(a, b))
                    except Exception:
                        continue
            is_drs &= is_straight
            is_nondrs = is_straight & (~is_drs)

        # accel / brake
        is_accel = (acc > accel_thr_mps2)
        if has_thr_col:
            thr = pd.to_numeric(car_data['Throttle'], errors='coerce').fillna(0.0)
            is_accel &= (thr >= throttle_min_pct)
        is_accel &= is_straight

        is_brake = (acc < brake_thr_mps2)
        if has_brk_col:
            brk = pd.to_numeric(car_data['Brake'], errors='coerce').fillna(0.0)
            is_brake |= (brk >= brake_min_pct)

        # corner classes
        slow_masks, med_masks, high_masks, hairpin_masks = [], [], [], []
        for idx, apex, d0 in apex_by_corner:
            k = next((m for (i, d, m) in corner_windows if i == idx), None)
            if k is None or not k.any():
                continue
            if apex < hairpin_thr_kph:
                hairpin_masks.append(k)
            if apex < slow_thr_kph:
                slow_masks.append(k)
            elif apex < medium_thr_kph:
                med_masks.append(k)
            else:
                high_masks.append(k)

        is_slow = pd.Series(False, index=car_data.index);   [is_slow.__ior__(m) for m in slow_masks]
        is_med = pd.Series(False,  index=car_data.index);   [is_med.__ior__(m) for m in med_masks]
        is_high = pd.Series(False, index=car_data.index);   [is_high.__ior__(m) for m in high_masks]
        is_hairpin = pd.Series(False, index=car_data.index);[is_hairpin.__ior__(m) for m in hairpin_masks]

        # chicanes
        is_chicane = pd.Series(False, index=car_data.index)
        is_chicane_slow = pd.Series(False, index=car_data.index)
        is_chicane_fast = pd.Series(False, index=car_data.index)
        if len(apex_by_corner) >= 2:
            apex_by_corner_sorted = sorted(apex_by_corner, key=lambda x: x[2])
            for (i1, apex1, d1), (i2, apex2, d2) in zip(apex_by_corner_sorted[:-1], apex_by_corner_sorted[1:]):
                if abs(d2 - d1) <= chicane_gap_m:
                    center = 0.5 * (d1 + d2)
                    combo_mask = (dist >= center - chicane_window_m) & (dist <= center + chicane_window_m)
                    if combo_mask.any():
                        is_chicane |= combo_mask
                        pair_apex = min(apex1, apex2)
                        if pair_apex < medium_thr_kph:
                            is_chicane_slow |= combo_mask
                        else:
                            is_chicane_fast |= combo_mask

        # complexes (≥3 corners in span)
        is_complex = pd.Series(False, index=car_data.index)
        if len(apex_by_corner) >= 3:
            dists = np.array([d for (_, _, d) in apex_by_corner])
            dists.sort()
            i, L = 0, len(dists)
            while i < L:
                j = i
                while j + 1 < L and (dists[j + 1] - dists[i] <= complex_span_m):
                    j += 1
                if (j - i + 1) >= 3:
                    start = dists[i] - corner_window_m
                    end = dists[j] + corner_window_m
                    is_complex |= _segment_mask_by_distance(dist, start, end)
                i += 1

        # stat helpers
        def mean_speed(mask: pd.Series) -> float:
            arr = speed[mask].to_numpy(dtype=float)
            return float(np.nanmean(arr)) if arr.size else np.nan

        def coverage(mask: pd.Series) -> float:
            if dist.empty:
                return 0.0
            covered = dist[mask]
            if covered.empty:
                return 0.0
            length = covered.max() - covered.min() if len(covered) else 0.0
            total = dist.max() - dist.min()
            return float(100.0 * length / total) if total > 0 else 0.0

        def p95_speed(mask: pd.Series) -> float:
            arr = speed[mask].to_numpy(dtype=float)
            return float(np.nanpercentile(arr, 95)) if arr.size else np.nan

        row_out = {
            'year': year, 'gp': gp, 'driver': driver_full_name, 'lap_used': 'fastest',
            'mean_kph_straight_drs': mean_speed(is_drs),
            'mean_kph_straight_nondrs': mean_speed(is_nondrs),
            'p95_kph_straight_drs': p95_speed(is_drs),
            'p95_kph_straight_nondrs': p95_speed(is_nondrs),
            'coverage_pct_straight_drs': coverage(is_drs),
            'coverage_pct_straight_nondrs': coverage(is_nondrs),
            'mean_kph_accel_zones': mean_speed(is_accel),
            'mean_kph_brake_zones': mean_speed(is_brake),
            'coverage_pct_accel_zones': coverage(is_accel),
            'coverage_pct_brake_zones': coverage(is_brake),
            'mean_kph_slow_corners': mean_speed(is_slow),
            'mean_kph_medium_corners': mean_speed(is_med),
            'mean_kph_high_corners': mean_speed(is_high),
            'coverage_pct_slow_corners': coverage(is_slow),
            'coverage_pct_medium_corners': coverage(is_med),
            'coverage_pct_high_corners': coverage(is_high),
            'mean_kph_hairpins': mean_speed(is_hairpin),
            'coverage_pct_hairpins': coverage(is_hairpin),
            'mean_kph_chicane_slow': mean_speed(is_chicane_slow),
            'mean_kph_chicane_fast': mean_speed(is_chicane_fast),
            'coverage_pct_chicane_slow': coverage(is_chicane_slow),
            'coverage_pct_chicane_fast': coverage(is_chicane_fast),
            'mean_kph_complexes': mean_speed(is_complex),
            'coverage_pct_complexes': coverage(is_complex),
        }
        out_rows.append(row_out)

    per_race = pd.DataFrame(out_rows).sort_values(['year', 'gp']).reset_index(drop=True)
    if per_race.empty:
        return per_race, pd.DataFrame(columns=['metric', 'value'])

    overall = (
        per_race.drop(columns=['year', 'gp', 'driver', 'lap_used'])
        .mean(numeric_only=True)
        .to_frame('value')
        .rename_axis('metric')
        .reset_index()
    )
    return per_race, overall