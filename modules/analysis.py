import pandas as pd
import numpy as np
from .utils import convert_time_to_seconds, convert_seconds_to_time_str

# -----------------------------------------------------------
# GAP CALCULATION (use robust logic from old version)
# -----------------------------------------------------------
def add_position_gaps(df_results: pd.DataFrame) -> pd.DataFrame:
    """
    For each race, compute:
      - gap_to_winner_s: time behind the winner in seconds (0 for winner).
      - gap_to_next_s:   gap to car behind (next finisher). NaN for last car.
    Uses '+…' gap strings in 'time' if present, else falls back to milliseconds.
    """
    use_cols = ['raceId', 'driverId', 'positionOrder', 'time', 'milliseconds']
    g = df_results[use_cols].copy()

    g['positionOrder']    = pd.to_numeric(g['positionOrder'], errors='coerce')
    g['milliseconds_num'] = pd.to_numeric(g['milliseconds'], errors='coerce')

    def compute_for_race(gr):
        gr = gr.sort_values('positionOrder').copy()
        win_ms_series = gr.loc[gr['positionOrder'] == 1, 'milliseconds_num']
        win_ms = win_ms_series.iloc[0] if not win_ms_series.empty else np.nan

        def gap_to_win(row):
            t = row['time']
            if isinstance(t, str) and t.strip().startswith('+'):
                sec = convert_time_to_seconds(t)
                if sec is not None:
                    return sec
            if pd.notna(row['milliseconds_num']) and pd.notna(win_ms):
                return max(0.0, (row['milliseconds_num'] - win_ms) / 1000.0)
            return 0.0 if row['positionOrder'] == 1 else np.nan

        gr['gap_to_winner_s'] = gr.apply(gap_to_win, axis=1)
        gr['gap_to_next_s'] = gr['gap_to_winner_s'].shift(-1) - gr['gap_to_winner_s']
        if len(gr) > 0:
            gr.iloc[-1, gr.columns.get_loc('gap_to_next_s')] = np.nan

        return gr[['raceId', 'driverId', 'gap_to_winner_s', 'gap_to_next_s']]

    out = g.groupby('raceId', group_keys=False).apply(compute_for_race)
    return df_results.merge(out, on=['raceId', 'driverId'], how='left')


# -----------------------------------------------------------
# BUILD DRIVER TABLE (lightweight merge + computed features)
# -----------------------------------------------------------
def build_driver_table(dfs: dict, min_year: int = 2018, wins_only: bool = False) -> pd.DataFrame:
    drivers = dfs['drivers']
    results = dfs['results']
    races   = dfs['races']
    status  = dfs.get('status', pd.DataFrame())     # optional
    weather = dfs.get('weather', pd.DataFrame())    # optional

    races_f = races[races['year'] >= min_year].copy()
    df = results.merge(races_f[['raceId','year','name','round','date']], on='raceId', how='inner')

    # base numeric cleaning
    df['grid'] = pd.to_numeric(df['grid'], errors='coerce')
    df['positionOrder'] = pd.to_numeric(df['positionOrder'], errors='coerce')
    df['positions_gained'] = (df['grid'] - df['positionOrder']).fillna(0)

    df['fastestLapTime_s'] = df['fastestLapTime'].apply(convert_time_to_seconds).fillna(0.0)
    df['fastestLapSpeed']  = pd.to_numeric(df['fastestLapSpeed'], errors='coerce').fillna(0.0)
    df['fastestLap']       = pd.to_numeric(df['fastestLap'], errors='coerce')

    # add gaps (old logic)
    df = add_position_gaps(df)

    if wins_only:
        df = df[df['positionOrder'] == 1]

    # status weight
    if not status.empty and 'statusId' in df.columns and 'statusId' in status.columns:
        dnf_ids = {
            1, 2, 11, 12, 13, 14, 15, 16, 17, 18, 19, 45, 50, 128, 53, 55, 58, 88,
            111,112,113,114,115,116,117,118,119,120,122,123,124,125,127,133,134
        }
        status = status[['statusId','status']].copy()
        df = df.merge(status, on='statusId', how='left')
        df['status_weight'] = df['statusId'].apply(lambda sid: 0 if pd.isna(sid) or sid in dnf_ids else 1)
    else:
        df['status_weight'] = 1

    # weather bonus (optional)
    if not weather.empty and {'GP','Date'}.issubset(weather.columns):
        df = df.merge(weather, left_on=['name','date'], right_on=['GP','Date'], how='left')
    for col in ['Precipitation']:
        if col not in df.columns:
            df[col] = np.nan

    def wet_bonus_fn(p):
        if pd.isna(p): p = 0
        if 5 <= p < 10:   return 10
        if 10 <= p < 20:  return 30
        if 20 <= p < 50:  return 80
        if p >= 50:       return 100
        return 0
    df['wet_bonus'] = df['Precipitation'].apply(wet_bonus_fn)

    # driver name
    drivers['driver_name'] = drivers['forename'] + ' ' + drivers['surname']
    df = df.merge(drivers[['driverId','driver_name']], on='driverId', how='left')
    return df


# -----------------------------------------------------------
# TOP RACES FOR DRIVER (old scoring logic, clean return)
# -----------------------------------------------------------
def top_races_for_driver(dfs: dict, driver_name: str, n_top: int = 3, min_year: int = 2018, wins_only: bool = False) -> pd.DataFrame:
    df = build_driver_table(dfs, min_year=min_year, wins_only=wins_only)
    df = df[df['driver_name'] == driver_name].copy()
    if df.empty:
        return df

    # ensure numeric
    for col in ['gap_to_winner_s','gap_to_next_s','fastestLapSpeed','fastestLapTime_s','positions_gained']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # weights (same as old)
    W = {
        'positions_gained' : 4.0,
        'gap_to_next_s'    : 1.2,
        'gap_to_winner_s'  : -2.0,
        'fastestLapTime_s' : -1.0,
        'fastestLapSpeed'  : 1.0,
        'status_weight'    : 1.0,
        'wet_bonus'        : 1.0
    }

    # compute score
    df['score'] = (
        df['positions_gained']   * W['positions_gained'] +
        df['gap_to_next_s']      * W['gap_to_next_s'] +
        df['gap_to_winner_s']    * W['gap_to_winner_s'] +
        df['fastestLapTime_s']   * W['fastestLapTime_s'] +
        df['fastestLapSpeed']    * W['fastestLapSpeed'] +
        df['status_weight']      * W['status_weight'] +
        df['wet_bonus']          * W['wet_bonus']
    )

    # sort by score descending (best performances first)
    df = df.sort_values('score', ascending=False)

    # return clean top-N table (for Streamlit)
    cols = [
        'year','round','name','driver_name','positionOrder','grid','positions_gained',
        'gap_to_winner_s','gap_to_next_s','fastestLapTime_s','fastestLapSpeed',
        'wet_bonus','score'
    ]
    return df[cols].head(n_top).reset_index(drop=True)
