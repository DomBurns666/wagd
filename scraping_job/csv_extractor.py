import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd


def get_data_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "data"


def get_available_seasons() -> List[Dict[str, str]]:
    """Returns a list of all available seasons found in the data directory, newest first."""
    data_dir = get_data_dir()
    seasons = []
    for p in sorted(data_dir.glob("premier_league_*.csv"), reverse=True):
        m = re.search(r"premier_league_(\d{4})_(\d{4})\.csv", p.name)
        if m:
            y1, y2 = m.groups()
            seasons.append({
                "id": f"{y1}-{y2}",
                "label": f"{y1}/{y2[2:]}",
                "display_name": f"{y1}-{y2} Season",
                "file_name": p.name,
                "path": str(p),
            })
    return seasons


def get_default_csv_path(season_id: Optional[str] = None) -> Path:
    data_dir = get_data_dir()
    if season_id:
        # Match by id like 2024-2025 or 2024_2025 or filename
        clean_id = season_id.replace("/", "-").replace("_", "-")
        for s in get_available_seasons():
            if s["id"] == clean_id or s["label"] == season_id or s["file_name"] == season_id:
                return Path(s["path"])
        # Fallback direct path check
        candidate = data_dir / f"premier_league_{clean_id.replace('-', '_')}.csv"
        if candidate.exists():
            return candidate

    seasons = get_available_seasons()
    if seasons:
        return Path(seasons[0]["path"])
    return data_dir / "premier_league_2025_2026.csv"


def extract_results_from_csv(csv_path=None):
    """
    Extracts match results from the football-data.co.uk CSV.
    Returns a list of match dictionaries with keys:
    - date (datetime)
    - home_team (str)
    - away_team (str)
    - home_goals (int)
    - away_goals (int)
    """
    if csv_path is None:
        csv_path = get_default_csv_path()
    else:
        csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Required columns in football-data.co.uk format
    required_cols = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"CSV is missing expected columns: {missing_cols}")

    results = []
    for _, row in df.iterrows():
        # Skip unplayed matches or rows with missing teams/scores
        if pd.isna(row["HomeTeam"]) or pd.isna(row["AwayTeam"]):
            continue
        if pd.isna(row["FTHG"]) or pd.isna(row["FTAG"]):
            continue

        date_str = str(row["Date"]).strip()
        time_str = str(row["Time"]).strip() if "Time" in row and pd.notna(row["Time"]) else None

        match_dt = None
        if time_str and time_str != "nan":
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%Y-%m-%d %H:%M"):
                try:
                    match_dt = datetime.strptime(f"{date_str} {time_str}", fmt)
                    break
                except ValueError:
                    pass

        if match_dt is None:
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
                try:
                    match_dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    pass

        if match_dt is None:
            match_dt = datetime.now()

        h1_home_goals = int(row["HTHG"]) if "HTHG" in row and pd.notna(row["HTHG"]) else None
        h1_away_goals = int(row["HTAG"]) if "HTAG" in row and pd.notna(row["HTAG"]) else None
        
        home_goals = int(row["FTHG"])
        away_goals = int(row["FTAG"])

        # Calculate second half goals
        h2_home_goals = (home_goals - h1_home_goals) if h1_home_goals is not None else None
        h2_away_goals = (away_goals - h1_away_goals) if h1_away_goals is not None else None

        results.append({
            "date": match_dt,
            "home_team": str(row["HomeTeam"]).strip(),
            "away_team": str(row["AwayTeam"]).strip(),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "h1_home_goals": h1_home_goals,
            "h1_away_goals": h1_away_goals,
            "h2_home_goals": h2_home_goals,
            "h2_away_goals": h2_away_goals,
        })

    # Sort chronologically
    results.sort(key=lambda m: m["date"])
    return results


def get_results_dataframe(csv_path=None) -> pd.DataFrame:
    """Extract results and return as a sorted pandas DataFrame."""
    results = extract_results_from_csv(csv_path)
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


if __name__ == "__main__":
    matches = extract_results_from_csv()
    print(f"Extracted {len(matches)} matches from CSV.")
    if matches:
        print("First match:", matches[0])
        print("Last match:", matches[-1])
