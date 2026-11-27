from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from cfb_analysis.markov import fetch_fbs_teams

LOG = logging.getLogger("cfb_scraper")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
USER_AGENT = "cfb-season-dataset/0.1 (educational research; contact: local project)"


@dataclass
class Game:
    season: int
    event_id: str
    date: str
    season_type: str
    week: str
    home_team: str
    home_team_id: str
    away_team: str
    away_team_id: str
    home_score: str
    away_score: str
    status: str
    venue: str
    neutral_site: str
    source: str = "ESPN scoreboard API"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
    return session


def request(session: requests.Session, url: str, params: dict[str, Any] | None = None, retries: int = 3) -> requests.Response:
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt + 1 == retries:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def event_game(event: dict[str, Any], season: int) -> Game | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    def team_name(item: dict[str, Any]) -> str:
        team = item.get("team") or {}
        return team.get("displayName") or team.get("name") or ""

    status = ((event.get("status") or {}).get("type") or {}).get("description", "")
    season_info = event.get("season") or {}
    venue = (comp.get("venue") or {}).get("fullName", "")
    return Game(
        season=season,
        event_id=str(event.get("id", "")),
        date=str(event.get("date", "")),
        season_type=str(season_info.get("type", "")),
        week=str(season_info.get("week", "")),
        home_team=team_name(home),
        home_team_id=str((home.get("team") or {}).get("id", "")),
        away_team=team_name(away),
        away_team_id=str((away.get("team") or {}).get("id", "")),
        home_score=str(home.get("score", "")),
        away_score=str(away.get("score", "")),
        status=status,
        venue=venue,
        neutral_site=str(comp.get("neutralSite", "")),
    )


def season_dates(season: int) -> Iterable[date]:
    # CFB regular/postseason falls between late August and mid January.
    cursor = date(season, 8, 1)
    end = date(season + 1, 1, 20)
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def fetch_games(session: requests.Session, season: int, raw_path: Path, delay: float) -> list[Game]:
    games: dict[str, Game] = {}
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("w", encoding="utf-8") as raw:
        for day in season_dates(season):
            response = request(session, SCOREBOARD_URL, {"dates": day.strftime("%Y%m%d"), "limit": 1000, "groups": 80})
            payload = response.json()
            raw.write(json.dumps({"requested_date": day.isoformat(), "payload": payload}, ensure_ascii=False) + "\n")
            for event in payload.get("events", []):
                game = event_game(event, season)
                if game:
                    games[game.event_id] = game
            time.sleep(delay)
    return sorted(games.values(), key=lambda g: (g.date, g.event_id))


def fetch_teams(season: int, cache_path: Path) -> list[dict[str, str]]:
    """Return the season's FBS teams only (ESPN group 80 membership)."""
    teams = fetch_fbs_teams(season, cache_path)
    result = []
    for team in teams:
        name = team["team_name"]
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        result.append({"id": team["team_id"], "slug": slug, "name": name})
    return result


def parse_schedule_html(html: str, team_name: str, team_id: str, season: int) -> list[dict[str, str]]:
    """Extract schedule rows into game records where ESPN exposes a game link."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select("table"):
        for tr in table.select("tbody tr"):
            cells = tr.select("th, td")
            if len(cells) < 3:
                continue
            date_text = cells[0].get_text(" ", strip=True)
            opponent_cell = cells[1]
            result_cell = cells[2]
            result_text = result_cell.get_text(" ", strip=True)
            # ESPN game rows link the score to the event ID; skip headers, byes,
            # and future games, which have no final score/game link yet.
            game_link = result_cell.select_one('a[href*="gameId/"]') or result_cell.select_one('a[href*="game/"]')
            score_match = re.search(r"\b([WLT])\s+(\d+)\s*-\s*(\d+)\b", result_text)
            if not game_link or not score_match:
                continue
            game_id_match = re.search(r"(?:gameId/|game/)(\d+)", game_link.get("href", ""))
            opponent_link = next(
                (link for link in opponent_cell.select('a[href*="/team/"]') if link.get_text(" ", strip=True)),
                None,
            )
            opponent_id_match = re.search(r"/id/(\d+)", opponent_link.get("href", "")) if opponent_link else None
            if not game_id_match or not opponent_link:
                continue
            try:
                parsed_date = datetime.strptime(date_text, "%a, %b %d").date().replace(year=season)
            except ValueError:
                continue
            opponent_name = opponent_link.get_text(" ", strip=True)
            venue_text = opponent_cell.get_text(" ", strip=True)
            is_away = "@" in venue_text
            first_score, second_score = score_match.group(2), score_match.group(3)
            # ESPN's schedule result is winner-first (for example, a loss shown
            # as ``L 24-14`` means the opponent scored 24 and this team scored 14).
            team_score, opponent_score = (
                (first_score, second_score) if score_match.group(1) != "L"
                else (second_score, first_score)
            )
            rows.append({
                "season": str(season), "schedule_team_id": team_id,
                "schedule_team": team_name, "event_id": game_id_match.group(1),
                "date": parsed_date.isoformat(), "season_type": "2",
                "week": "", "home_team": opponent_name if is_away else team_name,
                "home_team_id": opponent_id_match.group(1) if is_away else team_id,
                "away_team": team_name if is_away else opponent_name,
                "away_team_id": team_id if is_away else opponent_id_match.group(1),
                "home_score": opponent_score if is_away else team_score,
                "away_score": team_score if is_away else opponent_score,
                "status": "Final", "venue": "",
                "neutral_site": str("*" in venue_text),
                "source": "ESPN schedule HTML",
            })
    return rows


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def collect_schedules(session: requests.Session, teams: list[dict[str, str]], season: int, raw_dir: Path, delay: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team in teams:
        url = f"https://www.espn.com/college-football/team/schedule/_/id/{quote(team['id'])}/season/{season}"
        response = request(session, url)
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{team['id']}-{team['slug']}.html").write_text(response.text, encoding="utf-8")
        rows.extend(parse_schedule_html(response.text, team["name"], team["id"], season))
        time.sleep(delay)
    return rows


def merge_games(scoreboard_games: list[Game], schedule_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Use schedule rows to fill scoreboard gaps, preferring scoreboard metadata."""
    merged = {game.event_id: asdict(game) for game in scoreboard_games}
    game_fields = list(Game.__dataclass_fields__)
    for row in schedule_rows:
        event_id = row.get("event_id", "")
        if not event_id:
            continue
        if event_id in merged:
            merged[event_id]["source"] = "ESPN scoreboard API + schedule HTML"
        else:
            merged[event_id] = {field: row.get(field, "") for field in game_fields}
    return sorted(merged.values(), key=lambda row: (row.get("date", ""), row.get("event_id", "")))


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Build a college football season dataset.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--include-schedules", action="store_true", help="retained for compatibility; schedules are included by default")
    parser.add_argument("--scoreboard-only", action="store_true", help="skip team schedule scraping; the game dataset may be incomplete")
    parser.add_argument("--output-dir", type=Path, default=project_root / "data")
    parser.add_argument("--delay", type=float, default=0.25, help="seconds between requests (default: 0.25)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")
    output = args.output_dir
    session = make_session()
    games = fetch_games(session, args.season, output / "raw" / f"scoreboard_{args.season}.jsonl", max(0, args.delay))
    schedule_rows: list[dict[str, str]] = []
    if not args.scoreboard_only:
        teams = fetch_teams(args.season, output / "raw" / f"fbs_teams_{args.season}.csv")
        schedule_rows = collect_schedules(session, teams, args.season, output / "raw" / f"schedules_{args.season}", max(0, args.delay))
        write_csv(output / "processed" / f"team_schedules_{args.season}.csv", schedule_rows)
        LOG.info("Wrote %d schedule rows across %d teams", len(schedule_rows), len(teams))
    merged_games = merge_games(games, schedule_rows)
    write_csv(output / "processed" / f"games_{args.season}.csv", merged_games)
    LOG.info("Wrote %d games (%d scoreboard, %d schedule fallback rows)", len(merged_games), len(games), len(schedule_rows))
    return 0
