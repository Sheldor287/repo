# College Football 2026 Data Builder

A small, source-aware Python project for collecting 2026 FBS game data. It combines ESPN's public scoreboard JSON endpoint with BeautifulSoup-based team schedule scraping. The HTML schedule is important: ESPN scoreboard responses can omit games, so schedule records fill gaps in the normalized game file. Raw responses and normalized CSVs are kept separately so source changes can be audited.

## Scope and sources

- Season default: **2026** (override with `--season`).
- Scoreboard/game metadata: ESPN's public college football scoreboard endpoint.
- Schedule HTML: ESPN team schedule pages, parsed with BeautifulSoup. HTML layouts can change; inspect `data/raw/` and adjust selectors when needed.
- This project collects schedules and scores only. It does not claim a full play-by-play or advanced statistics dataset.

Respect each site's terms and robots guidance. Use a descriptive User-Agent, keep requests sequential, and don't bypass access controls.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Build the dataset

```powershell
python -m pip install -e .
python -m cfb_scraper --season 2026
```

The collector gets the season's FBS membership from ESPN's FBS group, intersects it with actual team entries in [ESPN's team directory](https://www.espn.com/college-football/teams), and scrapes each FBS team's schedule by default. It merges finished schedule rows into `games_2026.csv`, deduplicating by ESPN event ID. Use `--scoreboard-only` only when you intentionally want the faster, potentially incomplete scoreboard extract.

## Markov analysis

Install the project in editable mode once, then run the analysis from the repository root:

```powershell
python -m cfb_analysis --season 2026
```

The module writes `data/processed/fbs_markov_rankings_2026.csv` and `data/processed/fbs_game_edges_2026.csv`. It estimates latent strength from score-weighted Bradley–Terry outcomes across the FBS game graph; rank is based on latent strength, not record-first sorting. Record, scoring, strength of schedule, PageRank, HITS, Katz, eigenvector, and other graph measures are reported separately. It combines the game CSV with normalized schedule rows, deduplicating by ESPN event ID; if the schedule CSV is empty, it recovers finished games from cached FBS HTML. FCS games count toward record and scoring, while only FBS-vs-FBS results enter the latent model. See `math.md` for equations and interpretation.

Use `--games PATH`, `--teams PATH`, or `--output PATH` to override the default input/output files. Pass `--refresh-fbs-teams` to refresh the cached FBS list.

Project layout and outputs:

- `src/cfb_scraper/` and `src/cfb_analysis/` — installable Python packages.
- `notebooks/` — exploratory notebooks.
- `data/raw/scoreboard_2026.jsonl` — one source payload per event/date request.
- `data/raw/fbs_teams_2026.csv` and `data/raw/schedules_2026/` — season FBS membership and downloaded team schedule pages. Older non-FBS pages are retained under `data/raw/archive/legacy_schedule_pages_2026/`.
- `data/processed/games_2026.csv` — normalized game data.
- `data/processed/team_schedules_2026.csv` — finished rows from FBS-owned schedules, with `schedule_team` identifying the FBS team; an opponent can be FCS.
- `data/processed/fbs_markov_rankings_2026.csv` — record-first FBS ranking with Markov columns.

The scraper defaults to a conservative request delay and retries transient failures. `--output-dir` can point outputs elsewhere.

## Data caveats

The current season may be incomplete until the season finishes. ESPN is a source, not an official data guarantee. Schedule HTML may omit venue and time details, and its layout can change; spot-check records against source pages before analysis.


