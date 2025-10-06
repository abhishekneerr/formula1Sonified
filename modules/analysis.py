import pandas as pd
from .utils import convert_time_to_seconds

def add_position_gaps(df_results: pd.DataFrame) -> pd.DataFrame:
    """
    For each race, compute gap to winner (s) and gap to next finisher (s) using results.milliseconds.
    """
    df = df_results.copy()
    df['milliseconds'] = pd.to_numeric(df['milliseconds'], errors='coerce')
    df['positionOrder'] = pd.to_numeric(df['positionOrder'], errors='coerce')

    out = []
    for race_id, grp in df.groupby('raceId', as_index=False):
        g = grp.sort_values('positionOrder').copy()
        base = g['milliseconds'].iloc[0] if pd.notna(g['milliseconds'].iloc[0]) else None
        g['gap_to_winner_s'] = ((g['milliseconds'] - base) / 1000.0) if base is not None else pd.NA
        g['gap_to_next_s'] = g['milliseconds'].diff().abs() / 1000.0
        out.append(g)

    return pd.concat(out, ignore_index=True)

def build_driver_table(dfs: dict, min_year: int = 2018, wins_only: bool = False) -> pd.DataFrame:
    """
    Merge drivers + results + races; compute positions gained, fastest lap metrics, and gaps.
    """
    drivers = dfs['drivers']
    results = dfs['results']
    races   = dfs['races']

    races_f = races[races['year'] >= min_year].copy()
    df = results.merge(races_f[['raceId','year','name','round']], on='raceId', how='inner')

    df['grid'] = pd.to_numeric(df['grid'], errors='coerce')
    df['positionOrder'] = pd.to_numeric(df['positionOrder'], errors='coerce')
    df['positions_gained'] = (df['grid'] - df['positionOrder']).fillna(0)

    df['fastestLapTime_s'] = df['fastestLapTime'].apply(convert_time_to_seconds)
    df['fastestLapSpeed']  = pd.to_numeric(df['fastestLapSpeed'], errors='coerce')

    df = add_position_gaps(df)
    if wins_only:
        df = df[df['positionOrder'] == 1]

    drivers['driver_name'] = drivers['forename'] + ' ' + drivers['surname']
    df = df.merge(drivers[['driverId','driver_name']], on='driverId', how='left')
    return df

def top_races_for_driver(dfs: dict, driver_name: str, n_top: int = 3, min_year: int = 2018, wins_only: bool = False) -> pd.DataFrame:
    """
    Rank a driver's results by: finish pos (asc), gap to winner (asc), positions gained (desc), fastest-lap speed (desc).
    """
    df = build_driver_table(dfs, min_year=min_year, wins_only=wins_only)
    df = df[df['driver_name'] == driver_name].copy()
    if df.empty:
        return df

    df['gap_to_winner_s'] = pd.to_numeric(df['gap_to_winner_s'], errors='coerce').fillna(0.0)
    df['fastestLapSpeed'] = pd.to_numeric(df['fastestLapSpeed'], errors='coerce').fillna(0.0)
    df['positions_gained'] = pd.to_numeric(df['positions_gained'], errors='coerce').fillna(0.0)

    df = df.sort_values(
        by=['positionOrder','gap_to_winner_s','positions_gained','fastestLapSpeed'],
        ascending=[True, True, False, False]
    )

    cols = ['year','round','name','driver_name','positionOrder','grid','positions_gained',
            'gap_to_winner_s','fastestLapTime_s','fastestLapSpeed','raceId','driverId']
    return df[cols].head(n_top).reset_index(drop=True)
