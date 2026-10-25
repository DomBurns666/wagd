"""
Goal-based Elo Rating Engine for Football Matches.
Treats each goal scored as a win/loss exchange between two teams,
incorporating first-half and second-half results sequentially.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime


DEFAULT_BASE_RATING = 1000.0
DEFAULT_K_FACTOR = 15.0


def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    """Calculates the expected probability of team A scoring against team B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def apply_goal(scorer_rating: float, conceder_rating: float, k: float) -> Tuple[float, float, float]:
    """
    Applies a single goal event.
    Returns: (new_scorer_rating, new_conceder_rating, delta)
    """
    expected = calculate_expected_score(scorer_rating, conceder_rating)
    delta = k * (1.0 - expected)
    return scorer_rating + delta, conceder_rating - delta, delta


class GoalEloEngine:
    def __init__(self, base_rating: float = DEFAULT_BASE_RATING, k_factor: float = DEFAULT_K_FACTOR):
        self.base_rating = base_rating
        self.k_factor = k_factor

    def process_matches(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processes matches in chronological order and calculates ratings.
        Each match expects:
        - date, home_team, away_team, home_goals, away_goals,
          h1_home_goals, h1_away_goals, h2_home_goals, h2_away_goals
        """
        ratings: Dict[str, float] = {}
        matches_played: Dict[str, int] = {}
        goals_for: Dict[str, int] = {}
        goals_against: Dict[str, int] = {}
        official_points: Dict[str, int] = {}
        official_wins: Dict[str, int] = {}
        official_draws: Dict[str, int] = {}
        official_losses: Dict[str, int] = {}
        history_by_matchday: Dict[str, List[Dict[str, Any]]] = {}

        # Discover all teams
        for m in matches:
            for team in (m["home_team"], m["away_team"]):
                if team not in ratings:
                    ratings[team] = self.base_rating
                    matches_played[team] = 0
                    goals_for[team] = 0
                    goals_against[team] = 0
                    official_points[team] = 0
                    official_wins[team] = 0
                    official_draws[team] = 0
                    official_losses[team] = 0
                    history_by_matchday[team] = [{
                        "matchday": 0,
                        "rating": round(self.base_rating, 2),
                        "opponent": None,
                        "date": None,
                        "delta": 0.0,
                    }]

        processed_matches = []

        for m in matches:
            home = m["home_team"]
            away = m["away_team"]

            pre_home = ratings[home]
            pre_away = ratings[away]

            cur_home = pre_home
            cur_away = pre_away

            h1_hg = m.get("h1_home_goals", 0) or 0
            h1_ag = m.get("h1_away_goals", 0) or 0
            h2_hg = m.get("h2_home_goals", 0) or 0
            h2_ag = m.get("h2_away_goals", 0) or 0

            # First-half goals
            for _ in range(h1_hg):
                cur_home, cur_away, _ = apply_goal(cur_home, cur_away, self.k_factor)
            for _ in range(h1_ag):
                cur_away, cur_home, _ = apply_goal(cur_away, cur_home, self.k_factor)

            ht_home = cur_home
            ht_away = cur_away

            # Second-half goals
            for _ in range(h2_hg):
                cur_home, cur_away, _ = apply_goal(cur_home, cur_away, self.k_factor)
            for _ in range(h2_ag):
                cur_away, cur_home, _ = apply_goal(cur_away, cur_home, self.k_factor)

            post_home = cur_home
            post_away = cur_away

            ratings[home] = post_home
            ratings[away] = post_away

            matches_played[home] += 1
            matches_played[away] += 1

            goals_for[home] += m["home_goals"]
            goals_against[home] += m["away_goals"]
            goals_for[away] += m["away_goals"]
            goals_against[away] += m["home_goals"]

            # Track official Premier League match points (3 for win, 1 for draw)
            hg = m["home_goals"]
            ag = m["away_goals"]
            if hg > ag:
                official_points[home] += 3
                official_wins[home] += 1
                official_losses[away] += 1
            elif hg < ag:
                official_points[away] += 3
                official_wins[away] += 1
                official_losses[home] += 1
            else:
                official_points[home] += 1
                official_points[away] += 1
                official_draws[home] += 1
                official_draws[away] += 1

            home_delta = post_home - pre_home
            away_delta = post_away - pre_away

            history_by_matchday[home].append({
                "matchday": matches_played[home],
                "rating": round(post_home, 2),
                "opponent": away,
                "date": m["date"].strftime("%Y-%m-%d") if isinstance(m["date"], datetime) else str(m["date"]),
                "delta": round(home_delta, 2),
            })

            history_by_matchday[away].append({
                "matchday": matches_played[away],
                "rating": round(post_away, 2),
                "opponent": home,
                "date": m["date"].strftime("%Y-%m-%d") if isinstance(m["date"], datetime) else str(m["date"]),
                "delta": round(away_delta, 2),
            })

            processed_matches.append({
                "date": m["date"].strftime("%Y-%m-%d %H:%M") if isinstance(m["date"], datetime) else str(m["date"]),
                "home_team": home,
                "away_team": away,
                "home_goals": m["home_goals"],
                "away_goals": m["away_goals"],
                "ht_score": f"{h1_hg}-{h1_ag}",
                "ft_score": f"{m['home_goals']}-{m['away_goals']}",
                "pre_home_rating": round(pre_home, 1),
                "pre_away_rating": round(pre_away, 1),
                "post_home_rating": round(post_home, 1),
                "post_away_rating": round(post_away, 1),
                "home_delta": round(home_delta, 2),
                "away_delta": round(away_delta, 2),
            })

        # Calculate official Premier League standings
        official_sorted = sorted(
            ratings.keys(),
            key=lambda t: (official_points[t], goals_for[t] - goals_against[t], goals_for[t]),
            reverse=True
        )
        official_ranks = {t: off_rank for off_rank, t in enumerate(official_sorted, start=1)}

        # Calculate final WAGD leaderboard
        sorted_teams = sorted(ratings.keys(), key=lambda t: ratings[t], reverse=True)
        leaderboard = []
        for rank, team in enumerate(sorted_teams, start=1):
            off_rank = official_ranks[team]
            rank_diff = off_rank - rank  # Positive means WAGD rates higher than official table
            leaderboard.append({
                "rank": rank,
                "team": team,
                "rating": round(ratings[team], 2),
                "delta_total": round(ratings[team] - self.base_rating, 2),
                "matches_played": matches_played[team],
                "goals_for": goals_for[team],
                "goals_against": goals_against[team],
                "goal_difference": goals_for[team] - goals_against[team],
                "official_rank": off_rank,
                "official_points": official_points[team],
                "official_wins": official_wins[team],
                "official_draws": official_draws[team],
                "official_losses": official_losses[team],
                "rank_diff": rank_diff,
            })

        return {
            "leaderboard": leaderboard,
            "team_histories": history_by_matchday,
            "processed_matches": processed_matches,
            "total_matches": len(matches),
            "base_rating": self.base_rating,
            "k_factor": self.k_factor,
        }


def get_goal_elo_results(csv_path=None, base_rating=DEFAULT_BASE_RATING, k_factor=DEFAULT_K_FACTOR, season_id=None) -> Dict[str, Any]:
    """Helper to run the pipeline end-to-end from CSV to Elo results for a given season."""
    from scraping_job.csv_extractor import extract_results_from_csv, get_default_csv_path
    if csv_path is None:
        csv_path = get_default_csv_path(season_id)
    matches = extract_results_from_csv(csv_path)
    engine = GoalEloEngine(base_rating=base_rating, k_factor=k_factor)
    return engine.process_matches(matches)


if __name__ == "__main__":
    result = get_goal_elo_results()
    print("=== FINAL LEADERBOARD ===")
    for row in result["leaderboard"]:
        print(f"#{row['rank']:2d} {row['team']:<16} Rating: {row['rating']:7.2f} (diff {row['delta_total']:+6.2f}) | GF:{row['goals_for']:2d} GA:{row['goals_against']:2d}")
