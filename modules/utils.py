import os
import fastf1 as ff1
import warnings
import logging
import pandas as pd
import unicodedata


# logging.getLogger("fastf1").setLevel(logging.ERROR)
# warnings.simplefilter(action='ignore', category=FutureWarning)


def normalize_name(name: str) -> str:
    if pd.isna(name):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', name)
        if unicodedata.category(c) != 'Mn'
    )

def convert_time_to_seconds(time_str):
    """
    Convert Ergast-style time strings to seconds.
    Examples: "1:23.456" -> 83.456, "\\N" -> None
    """
    if pd.isna(time_str):
        return None
    s = str(time_str).replace('+', '').strip()
    if s in {"\\N", "", "None"}:
        return None
    parts = s.split(':')
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            m, sec = parts
            return int(m)*60 + float(sec)
        elif len(parts) == 3:
            h, m, sec = parts
            return int(h)*3600 + int(m)*60 + float(sec)
    except Exception:
        return None
    return None

def convert_seconds_to_time_str(seconds):
    if seconds is None:
        return ""
    minutes = int(seconds // 60)
    leftover = seconds % 60
    return f"{minutes}:{leftover:05.3f}"
