"""FBS ecosystem strength from score-aware game edges and Bradley-Terry estimation."""
from __future__ import annotations

import argparse
import csv
import logging
import math
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import requests

LOG = logging.getLogger("cfb_analysis")
ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams"
ESPN_FBS_TEAMS_URL = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/"
    "seasons/{season}/types/2/groups/80/teams"
)
USER_AGENT = "cfb-season-dataset/0.1 (educational research; contact: local project)"
MIN_EXPECTED_FBS_TEAMS = 100
DEFAULT_REGULARIZATION = 0.25


def _team_entries(payload: Any) -> list[dict[str, str]]:
    """Read direct team directory entries, not nested conference records."""
    sports = payload.get("sports", []) if isinstance(payload, dict) else []
    leagues = sports[0].get("leagues", []) if sports else []
    entries = leagues[0].get("teams", []) if leagues else []
    found: dict[str, dict[str, str]] = {}
    for wrapper in entries:
        team = wrapper.get("team", wrapper) if isinstance(wrapper, dict) else {}
        team_id = team.get("id")
        name = team.get("displayName") or team.get("name")
        if team_id and name:
            found[str(team_id)] = {"team_id": str(team_id), "team_name": str(name)}
    return sorted(found.values(), key=lambda row: row["team_name"].casefold())


def _write_team_cache(cache_path: Path, teams: list[dict[str, str]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["team_id", "team_name"])
        writer.writeheader()
        writer.writerows(teams)


def fetch_fbs_teams(season: int, cache_path: Path, *, refresh: bool = False) -> list[dict[str, str]]:
    """Get season FBS membership and intersect it with ESPN's direct team directory."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    directory_response = requests.get(ESPN_TEAMS_URL, params={"limit": 1000}, headers=headers, timeout=30)
    directory_response.raise_for_status()
    names = {team["team_id"]: team["team_name"] for team in _team_entries(directory_response.json())}

    if cache_path.exists() and not refresh:
        with cache_path.open(newline="", encoding="utf-8-sig") as handle:
            cached_rows = list(csv.DictReader(handle))
        cached = [
            {"team_id": str(row["team_id"]), "team_name": names[str(row["team_id"])]}
            for row in cached_rows if str(row.get("team_id", "")) in names
        ]
        if len(cached) >= MIN_EXPECTED_FBS_TEAMS:
            if len(cached) != len(cached_rows):
                _write_team_cache(cache_path, cached)
            return cached

    group_url = ESPN_FBS_TEAMS_URL.format(season=season)
    response = requests.get(group_url, params={"limit": 500}, headers=headers, timeout=30)
    response.raise_for_status()
    refs = response.json().get("items", [])
    fbs_ids = {
        match.group(1)
        for item in refs if isinstance(item, dict)
        and (match := re.search(r"/teams/(\d+)", item.get("$ref", "")))
    }
    teams = [{"team_id": team_id, "team_name": names[team_id]}
             for team_id in fbs_ids if team_id in names]
    teams.sort(key=lambda row: row["team_name"].casefold())
    if len(teams) < MIN_EXPECTED_FBS_TEAMS:
        raise RuntimeError(f"Only {len(teams)} named FBS teams resolved for {season}; refusing a partial ranking.")
    if len(fbs_ids) != len(teams):
        LOG.warning("Ignored %d non-team entries in ESPN's FBS group", len(fbs_ids) - len(teams))
    _write_team_cache(cache_path, teams)
    return teams


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _read_final_games(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows:
        if str(row.get("status", "")).casefold() != "final":
            continue
        home_score, away_score = _number(row.get("home_score")), _number(row.get("away_score"))
        home_id, away_id = str(row.get("home_team_id", "")).strip(), str(row.get("away_team_id", "")).strip()
        if home_score is None or away_score is None or not home_id or not away_id:
            continue
        result.append({
            "event_id": str(row.get("event_id", "")), "date": str(row.get("date", "")),
            "season": str(row.get("season", "")), "home_id": home_id,
            "home_name": str(row.get("home_team", home_id)), "home_score": home_score,
            "away_id": away_id, "away_name": str(row.get("away_team", away_id)),
            "away_score": away_score, "neutral_site": str(row.get("neutral_site", "")),
            "source": str(row.get("source", "")),
        })
    return result


def _supplement_from_schedule_files(games_path: Path, teams: list[dict[str, str]], season: int) -> list[dict[str, Any]]:
    """Use normalized schedule rows, or recover finished rows from cached HTML."""
    schedule_path = games_path.with_name(f"team_schedules_{season}.csv")
    if schedule_path.exists() and schedule_path.stat().st_size:
        return _read_final_games(schedule_path)
    raw_dir = games_path.parent.parent / "raw" / f"schedules_{season}"
    if not raw_dir.exists():
        return []
    from cfb_scraper.cli import parse_schedule_html
    names = {str(team["team_id"]): str(team["team_name"]) for team in teams}
    games = []
    for path in raw_dir.glob("*.html"):
        match = re.match(r"(\d+)-", path.name)
        if not match or match.group(1) not in names:
            continue
        rows = parse_schedule_html(path.read_text(encoding="utf-8"), names[match.group(1)], match.group(1), season)
        for row in rows:
            home_score, away_score = _number(row.get("home_score")), _number(row.get("away_score"))
            if home_score is None or away_score is None:
                continue
            games.append({
                "event_id": str(row["event_id"]), "date": str(row.get("date", "")), "season": str(season),
                "home_id": str(row["home_team_id"]), "home_name": str(row["home_team"]), "home_score": home_score,
                "away_id": str(row["away_team_id"]), "away_name": str(row["away_team"]), "away_score": away_score,
                "neutral_site": str(row.get("neutral_site", "")), "source": "ESPN schedule HTML",
            })
    return games


def _merge_game_sources(primary: list[dict[str, Any]], supplement: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer scoreboard records and fill absent event IDs from schedules."""
    merged = {game["event_id"]: game for game in primary if game.get("event_id")}
    for game in supplement:
        event_id = game.get("event_id")
        if event_id and event_id not in merged:
            merged[event_id] = game
    return sorted(merged.values(), key=lambda game: (game.get("date", ""), game.get("event_id", "")))


def _edge_quality(winner_score: float, loser_score: float) -> float:
    margin = min(abs(winner_score - loser_score), 35.0)
    relative_score = (winner_score + 1.0) / (loser_score + 1.0)
    return 0.65 * math.log1p(margin) + 0.35 * math.log1p(relative_score)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -700.0))
    return z / (1.0 + z)


def _softplus(value: float) -> float:
    return max(value, 0.0) + math.log1p(math.exp(-abs(value)))


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [matrix[i][:] + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-14:
            raise ArithmeticError("Singular Bradley-Terry information matrix")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        for j in range(col, n + 1):
            augmented[col][j] /= scale
        for row in range(n):
            if row != col:
                factor = augmented[row][col]
                if factor:
                    for j in range(col, n + 1):
                        augmented[row][j] -= factor * augmented[col][j]
    return [augmented[i][n] for i in range(n)]


def fit_bradley_terry(team_ids: list[str], observations: list[tuple[str, str, float]], *,
                      regularization: float = DEFAULT_REGULARIZATION,
                      tolerance: float = 1e-8, max_iterations: int = 100) -> tuple[dict[str, float], int]:
    """Fit weighted Bradley-Terry log strengths from (winner, loser, weight)."""
    if regularization <= 0:
        raise ValueError("regularization must be positive")
    ids = list(team_ids)
    index = {team_id: i for i, team_id in enumerate(ids)}
    n = len(ids)
    if not n:
        return {}, 0
    obs = [(index[w], index[l], max(0.0, weight)) for w, l, weight in observations if w in index and l in index]
    strengths = [0.0] * n

    def objective(values: list[float]) -> float:
        loss = 0.5 * regularization * sum(value * value for value in values)
        for winner, loser, weight in obs:
            loss += weight * _softplus(-(values[winner] - values[loser]))
        return loss

    if not obs:
        return {team_id: 0.0 for team_id in ids}, 0
    for iteration in range(1, max_iterations + 1):
        gradient = [regularization * value for value in strengths]
        hessian = [[0.0] * n for _ in range(n)]
        for i in range(n):
            hessian[i][i] = regularization
        for winner, loser, weight in obs:
            probability = _sigmoid(strengths[winner] - strengths[loser])
            error = weight * (probability - 1.0)
            gradient[winner] += error
            gradient[loser] -= error
            curvature = weight * probability * (1.0 - probability)
            hessian[winner][winner] += curvature
            hessian[loser][loser] += curvature
            hessian[winner][loser] -= curvature
            hessian[loser][winner] -= curvature
        direction = _solve_linear(hessian, gradient)
        old_loss = objective(strengths)
        step = 1.0
        candidate = strengths
        while step >= 1e-7:
            trial = [strengths[i] - step * direction[i] for i in range(n)]
            if objective(trial) <= old_loss:
                candidate = trial
                break
            step *= 0.5
        change = max(abs(candidate[i] - strengths[i]) for i in range(n))
        strengths = candidate
        if change < tolerance:
            break
    mean_strength = sum(strengths) / n
    strengths = [value - mean_strength for value in strengths]
    return dict(zip(ids, strengths)), iteration


def _norm(values: dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in values.values()))


def _normalize_l2(values: dict[str, float]) -> dict[str, float]:
    norm = _norm(values)
    return {key: value / norm for key, value in values.items()} if norm else {key: 0.0 for key in values}


def _weighted_pagerank(ids: list[str], adjacency: dict[str, dict[str, float]], damping: float = 0.85) -> dict[str, float]:
    n = len(ids)
    if not n:
        return {}
    rank = {team_id: 1.0 / n for team_id in ids}
    for _ in range(10_000):
        dangling = sum(rank[source] for source in ids if not adjacency[source])
        updated = {team_id: (1.0 - damping) / n + damping * dangling / n for team_id in ids}
        for source in ids:
            total = sum(adjacency[source].values())
            if total:
                for target, weight in adjacency[source].items():
                    updated[target] += damping * rank[source] * weight / total
        error = sum(abs(updated[team_id] - rank[team_id]) for team_id in ids)
        rank = updated
        if error < 1e-12:
            break
    return rank


def _hits(ids: list[str], adjacency: dict[str, dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    authority = {team_id: 1.0 for team_id in ids}
    hub = dict(authority)
    for _ in range(10_000):
        new_authority = {team_id: 0.0 for team_id in ids}
        for source in ids:
            for target, weight in adjacency[source].items():
                new_authority[target] += weight * hub[source]
        new_authority = _normalize_l2(new_authority)
        new_hub = {team_id: sum(weight * new_authority[target] for target, weight in adjacency[team_id].items())
                   for team_id in ids}
        new_hub = _normalize_l2(new_hub)
        error = sum(abs(new_authority[k] - authority[k]) + abs(new_hub[k] - hub[k]) for k in ids)
        authority, hub = new_authority, new_hub
        if error < 1e-12:
            break
    return authority, hub


def _katz(ids: list[str], adjacency: dict[str, dict[str, float]], alpha: float = 0.85) -> dict[str, float]:
    max_out = max((sum(adjacency[source].values()) for source in ids), default=0.0)
    if not max_out:
        return {team_id: 1.0 for team_id in ids}
    score = {team_id: 1.0 for team_id in ids}
    for _ in range(10_000):
        updated = {team_id: 1.0 for team_id in ids}
        for source in ids:
            for target, weight in adjacency[source].items():
                updated[target] += alpha * score[source] * weight / max_out
        error = sum(abs(updated[k] - score[k]) for k in ids)
        score = updated
        if error < 1e-11:
            break
    return score


def _eigenvector(ids: list[str], adjacency: dict[str, dict[str, float]]) -> dict[str, float]:
    max_out = max((sum(adjacency[source].values()) for source in ids), default=0.0)
    if not max_out:
        return {team_id: 1.0 / math.sqrt(len(ids)) for team_id in ids} if ids else {}
    score = {team_id: 1.0 / math.sqrt(len(ids)) for team_id in ids}
    for _ in range(10_000):
        updated = dict(score)
        for source in ids:
            for target, weight in adjacency[source].items():
                updated[target] += score[source] * weight / max_out
        updated = _normalize_l2(updated)
        error = sum(abs(updated[k] - score[k]) for k in ids)
        score = updated
        if error < 1e-12:
            break
    return score


def _components(ids: list[str], adjacency: dict[str, dict[str, float]]) -> tuple[dict[str, int], dict[str, int]]:
    undirected = {team_id: set() for team_id in ids}
    for source in ids:
        for target in adjacency[source]:
            undirected[source].add(target)
            undirected[target].add(source)
    labels: dict[str, int] = {}
    sizes: dict[int, int] = {}
    label = 0
    for root in ids:
        if root in labels:
            continue
        label += 1
        queue = [root]
        labels[root] = label
        for node in queue:
            for neighbor in undirected[node]:
                if neighbor not in labels:
                    labels[neighbor] = label
                    queue.append(neighbor)
        sizes[label] = len(queue)
    return labels, {team_id: sizes[labels[team_id]] for team_id in ids}


def _distance_to_top(ids: list[str], adjacency: dict[str, dict[str, float]], top_ids: Iterable[str]) -> dict[str, int]:
    undirected = {team_id: set() for team_id in ids}
    for source in ids:
        for target in adjacency[source]:
            undirected[source].add(target)
            undirected[target].add(source)
    distance = {team_id: -1 for team_id in ids}
    queue: deque[str] = deque()
    for team_id in top_ids:
        if team_id in distance:
            distance[team_id] = 0
            queue.append(team_id)
    while queue:
        node = queue.popleft()
        for neighbor in undirected[node]:
            if distance[neighbor] == -1:
                distance[neighbor] = distance[node] + 1
                queue.append(neighbor)
    return distance


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def rank_fbs_teams(teams: list[dict[str, str]], games: list[dict[str, Any]], *,
                   regularization: float = DEFAULT_REGULARIZATION
                   ) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    """Rank by latent FBS strength; also return separate metrics and game edges."""
    team_names = {str(team["team_id"]): str(team["team_name"]) for team in teams}
    ids = sorted(team_names)
    fbs_ids = set(ids)
    stats = {team_id: {"team_id": team_id, "team_name": team_names[team_id], "wins": 0,
                       "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0,
                       "games_played": 0} for team_id in ids}
    edges: list[dict[str, Any]] = []
    observations_raw: list[tuple[str, str, float, dict[str, Any]]] = []
    opponents = {team_id: [] for team_id in ids}
    opponent_weights = {team_id: [] for team_id in ids}
    wins_against = {team_id: [] for team_id in ids}
    losses_to = {team_id: [] for team_id in ids}

    for game in games:
        home, away = game["home_id"], game["away_id"]
        hs, ass = game["home_score"], game["away_score"]
        for team_id, scored, allowed in ((home, hs, ass), (away, ass, hs)):
            if team_id in stats:
                stats[team_id]["games_played"] += 1
                stats[team_id]["points_for"] += scored
                stats[team_id]["points_against"] += allowed
                opponent_id = away if team_id == home else home
                if opponent_id in fbs_ids:
                    opponents[team_id].append(opponent_id)
        tied = hs == ass
        winner = "" if tied else (home if hs > ass else away)
        loser = "" if tied else (away if hs > ass else home)
        winner_score, loser_score = max(hs, ass), min(hs, ass)
        margin = abs(hs - ass)
        quality = 0.0 if tied else _edge_quality(winner_score, loser_score)
        both_fbs = home in fbs_ids and away in fbs_ids
        graph_edge = both_fbs and not tied
        edge = {
            "season": game.get("season", ""), "event_id": game.get("event_id", ""), "date": game.get("date", ""),
            "home_team_id": home, "home_team": game["home_name"], "home_score": hs,
            "away_team_id": away, "away_team": game["away_name"], "away_score": ass,
            "winner_team_id": winner, "winner_team": game["home_name"] if winner == home else game["away_name"] if winner else "",
            "loser_team_id": loser, "loser_team": game["away_name"] if loser == away else game["home_name"] if loser else "",
            "winner_score": winner_score if not tied else "", "loser_score": loser_score if not tied else "",
            "margin": margin, "winner_home_away": "Home" if winner == home else "Away" if winner else "",
            "neutral_site": game.get("neutral_site", ""), "edge_direction": f"{loser}->{winner}" if not tied else "tie",
            "edge_quality": quality, "edge_weight": 0.0, "fbs_graph_edge": graph_edge,
            "source": game.get("source", ""),
        }
        edges.append(edge)
        if not tied:
            if winner in stats:
                stats[winner]["wins"] += 1
            if loser in stats:
                stats[loser]["losses"] += 1
        else:
            for team_id in (home, away):
                if team_id in stats:
                    stats[team_id]["ties"] += 1
        if graph_edge:
            observations_raw.append((winner, loser, quality, edge))
            opponent_weights[home].append((away, quality))
            opponent_weights[away].append((home, quality))
            wins_against[winner].append((loser, quality))
            losses_to[loser].append((winner, quality))

    mean_quality = _mean([row[2] for row in observations_raw]) or 1.0
    adjacency: dict[str, dict[str, float]] = {team_id: defaultdict(float) for team_id in ids}
    observations = []
    for winner, loser, quality, edge in observations_raw:
        weight = quality / mean_quality
        adjacency[loser][winner] += weight
        observations.append((winner, loser, weight))
        edge["edge_weight"] = weight

    latent, iterations = fit_bradley_terry(ids, observations, regularization=regularization)
    pagerank = _weighted_pagerank(ids, adjacency)
    authority, hub = _hits(ids, adjacency)
    katz = _katz(ids, adjacency)
    eigenvector = _eigenvector(ids, adjacency)
    components, component_sizes = _components(ids, adjacency)
    latent_order = sorted(ids, key=lambda team_id: (-latent[team_id], team_names[team_id].casefold()))
    distance = _distance_to_top(ids, adjacency, latent_order[:5])
    in_strength = {team_id: sum(adjacency[src].get(team_id, 0.0) for src in ids) for team_id in ids}
    out_strength = {team_id: sum(adjacency[team_id].values()) for team_id in ids}

    for row in stats.values():
        decisions = row["wins"] + row["losses"] + row["ties"]
        row["record"] = f"{row['wins']}-{row['losses']}" + (f"-{row['ties']}" if row["ties"] else "")
        row["win_pct"] = (row["wins"] + 0.5 * row["ties"]) / decisions if decisions else 0.0

    for team_id, row in stats.items():
        played = row["games_played"]
        row["points_for"] = int(row["points_for"])
        row["points_against"] = int(row["points_against"])
        row["point_diff"] = row["points_for"] - row["points_against"]
        row["points_per_game"] = row["points_for"] / played if played else 0.0
        row["point_diff_per_game"] = row["point_diff"] / played if played else 0.0
        row["score_strength"] = math.tanh(row["point_diff_per_game"] / 21.0)
        opps = opponents[team_id]
        row["fbs_opponents_played"] = len(opps)
        row["opponent_win_pct"] = _mean([stats[opp]["win_pct"] for opp in opps])
        weighted = opponent_weights[team_id]
        denominator = sum(weight for _, weight in weighted)
        row["strength_of_schedule"] = _mean([latent[opp] for opp in opps])
        row["weighted_sos"] = sum(latent[opp] * weight for opp, weight in weighted) / denominator if denominator else 0.0
        for key, source in (("quality_of_wins", wins_against[team_id]), ("quality_of_losses", losses_to[team_id])):
            total = sum(weight for _, weight in source)
            row[key] = sum(latent[opp] * weight for opp, weight in source) / total if total else 0.0
        row["latent_strength"] = latent[team_id]
        row["weighted_pagerank"] = pagerank[team_id]
        row["hits_authority"] = authority[team_id]
        row["hits_hub"] = hub[team_id]
        row["katz_centrality"] = katz[team_id]
        row["eigenvector_centrality"] = eigenvector[team_id]
        row["in_strength"] = in_strength[team_id]
        row["out_strength"] = out_strength[team_id]
        row["network_component"] = components[team_id]
        row["network_component_size"] = component_sizes[team_id]
        row["distance_to_top5"] = distance[team_id]

    ranked = sorted(stats.values(), key=lambda row: (-row["latent_strength"], row["team_name"].casefold()))
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return ranked, iterations, edges


def load_analysis_games(games_path: Path, teams: list[dict[str, str]], season: int) -> list[dict[str, Any]]:
    scoreboard = _read_final_games(games_path)
    schedules = _supplement_from_schedule_files(games_path, teams, season)
    merged = _merge_game_sources(scoreboard, schedules)
    LOG.info("Loaded %d scoreboard plus %d schedule games; %d unique games", len(scoreboard), len(schedules), len(merged))
    return merged


def analyze_season(games_path: Path, teams: list[dict[str, str]], *, season: int = 2026,
                   regularization: float = DEFAULT_REGULARIZATION):
    return rank_fbs_teams(teams, load_analysis_games(games_path, teams, season), regularization=regularization)


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Estimate FBS ecosystem strength from weighted game results.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--games", type=Path, help="games CSV (defaults to data/processed/games_YEAR.csv)")
    parser.add_argument("--teams", type=Path, help="cached FBS roster (defaults to data/raw/fbs_teams_YEAR.csv)")
    parser.add_argument("--output", type=Path, help="team ranking CSV output path")
    parser.add_argument("--edges-output", type=Path, help="game edge CSV output path")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--regularization", type=float, default=DEFAULT_REGULARIZATION)
    parser.add_argument("--refresh-fbs-teams", action="store_true")
    args = parser.parse_args(argv)
    games_path = args.games or project_root / "data" / "processed" / f"games_{args.season}.csv"
    teams_path = args.teams or project_root / "data" / "raw" / f"fbs_teams_{args.season}.csv"
    output_path = args.output or project_root / "data" / "processed" / f"fbs_markov_rankings_{args.season}.csv"
    edges_path = args.edges_output or project_root / "data" / "processed" / f"fbs_game_edges_{args.season}.csv"
    if not games_path.exists():
        parser.error(f"games CSV not found: {games_path}")
    teams = fetch_fbs_teams(args.season, teams_path, refresh=args.refresh_fbs_teams)
    games = load_analysis_games(games_path, teams, args.season)
    ranking, iterations, edges = rank_fbs_teams(teams, games, regularization=args.regularization)
    rank_columns = [
        "rank", "team_id", "team_name", "latent_strength", "record", "wins", "losses", "ties", "win_pct",
        "games_played", "points_for", "points_against", "point_diff", "points_per_game", "point_diff_per_game",
        "score_strength", "fbs_opponents_played", "opponent_win_pct", "strength_of_schedule", "weighted_sos",
        "quality_of_wins", "quality_of_losses", "weighted_pagerank", "hits_authority", "hits_hub",
        "katz_centrality", "eigenvector_centrality", "in_strength", "out_strength", "network_component",
        "network_component_size", "distance_to_top5",
    ]
    edge_columns = [
        "season", "event_id", "date", "home_team_id", "home_team", "home_score", "away_team_id", "away_team",
        "away_score", "winner_team_id", "winner_team", "loser_team_id", "loser_team", "winner_score",
        "loser_score", "margin", "winner_home_away", "neutral_site", "edge_direction", "edge_quality",
        "edge_weight", "fbs_graph_edge", "source",
    ]
    _write_csv(output_path, ranking, rank_columns)
    _write_csv(edges_path, edges, edge_columns)
    print(f"Ranked {len(ranking)} FBS teams by latent strength ({iterations} Bradley-Terry iterations).")
    print(f"Saved team evidence: {output_path}")
    print(f"Saved game edges: {edges_path}")
    print("Rank  Team                       Record  Latent  SOS")
    for row in ranking[:max(0, args.top)]:
        print(f"{row['rank']:>4}  {row['team_name'][:26]:<26} {row['record']:<7} "
              f"{row['latent_strength']:>7.3f} {row['strength_of_schedule']:>7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
