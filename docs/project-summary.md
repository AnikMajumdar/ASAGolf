# ASA Golf: Project Summary

## Purpose
ASA Golf is a performance analytics platform for the UC Davis Women's Golf team. The current phase covers only data collection, database design, and ingestion.

## Rules
- UC Davis women's players only. Women's events only.
- Only courses the team played.
- No fabricated data.
- Competitor data is kept at team/tournament level. No competitor player rows are stored.
- Seasons from 2022 onward. Currently only 2025 is loaded (see Open Items).
- Clippd is the only given data source. Automated HTML collection is allowed.
- The official UC Davis site is the roster authority.

## Approved Stack
Python 3.12, Pydantic, SQLAlchemy 2.x, Alembic, Neon PostgreSQL. Pandas was listed but is not used yet. Tooling: `uv` (system Python is 3.9, too old).

## Repository
- Remote: https://github.com/AnikMajumdar/ASAGolf (branch `main`)
- First commit: `40667ca`, "Add Clippd ingestion pipeline for 2025 UC Davis women's events"
- `.env` holds `DATABASE_URL` (Neon). It is git-ignored and must never be committed or printed.
- `.env.example` documents the variable. Use scheme `postgresql+psycopg://` (the plain `postgresql://` scheme would pick psycopg2, which is not installed).

### Layout
- `src/asa_golf/clippd.py`: parses Clippd player leaderboard HTML (Next.js RSC `self.__next_f.push` payloads). Keeps only "UC Davis" rows. Excludes substitutes, null strokes, and sentinel to-par values (e.g., 100000).
- `src/asa_golf/schemas.py`: Pydantic models. `CourseRound`, `PlayerRound`, `PlayerResult`, `ExcludedEntry`, `TournamentData`, `RosterPlayer`, `RosterFile`. Checks 18 holes, pars/yards sums, strokes 1–20, and round totals.
- `src/asa_golf/models.py`: SQLAlchemy 2.0 models (source of truth for the schema).
- `src/asa_golf/ingest.py`: `season_for`, `load_roster`, `match_roster`, `ingest_tournament` (idempotent delete-and-reinsert per tournament), and CLI `main`.
- `alembic/` and `alembic.ini`: migrations. `alembic/env.py` reads `DATABASE_URL`. Initial migration: `alembic/versions/8007b6d10455_initial_schema.py`.
- `data/roster/ucdavis_womens_golf_2024-25.json`: roster allowlist (9 players). Clippd "Abigail Leighton" is aliased to roster "Abby Leighton" via `clippd_names`.
- `data/raw/clippd/`: raw HTML for the two 2025 events, kept for re-parsing.
- `docs/data-sources.md`: sources, rules, and schema (updated to match the implementation).
- `tests/test_clippd_ingest.py`: 5 tests (substitute exclusion, Thompson load, hole-sum rejection, idempotent ingest, men's/out-of-season rejection).

## Schema (Postgres, applied on Neon)
- `season(id, label UNIQUE, start_year UNIQUE)`. Academic season runs Aug–Jul and is labeled by starting year, so spring 2025 events = `2024-25`.
- `tournament(id, clippd_tournament_id UNIQUE, season_id, name, venue, start_date, end_date)`
- `course(id, clippd_course_id UNIQUE, name)`
- `tournament_round(tournament_id, round_number, course_id, total_par, total_yards)` PK (tournament_id, round_number)
- `hole_par_yards(tournament_id, round_number, hole_number, par, yards)`
- `player(id, full_name UNIQUE, clippd_player_id UNIQUE NULL)`
- `roster_membership(player_id, season_id, source_url)` PK (player_id, season_id)
- `round_score(id, tournament_id, player_id, round_number, total_strokes)` UNIQUE (tournament_id, player_id, round_number)
- `hole_score(round_score_id, hole_number, strokes)` PK (round_score_id, hole_number), CHECK strokes 1–20
- Composite FKs use `ON DELETE CASCADE`.

Deferred: `team_result` (team leaderboard not parsed yet) and `ingest_run` (load history).

## Commands
```
uv sync --python 3.12
uv run pytest -q
uv run alembic upgrade head
uv run python -m asa_golf.ingest --roster data/roster/ucdavis_womens_golf_2024-25.json data/raw/clippd/234273_2025_big_west_women_player.html data/raw/clippd/232994_2025_thompson_invitational_player.html
```
Set `DATABASE_URL` (with the `postgresql+psycopg://` scheme) before running Alembic or ingest.

## Data Loaded (2025, in Neon)
- 2025 Big West Women's Golf Championship (Clippd 234273): 5 players, 15 rounds, 270 holes, 1 excluded (substitute Elina Kuang).
- 2025 Dr. Donnis Thompson Invitational (Clippd 232994): 5 players, 15 rounds, 270 holes, 0 excluded.
- Totals: 2 tournaments, 5 players, 5 roster memberships, 30 round scores, 540 hole scores, 108 hole-par rows.
- Hole-sum mismatches: 0. Round totals equal hole sums in all 30 rounds.
- Courses: Spanish Trail Canyon/Lakes (`EB-USA-207`), par 72, 6,315 yards. Royal Kaanapali (`CD-USA-7081`), par 72, 5,993 yards.
- Kuang is on the roster but has no stored rounds (her 2025 entries are substitute rows).

## Clippd Notes
- No public JSON API. The leaderboard is embedded in RSC chunks. Join the chunks, then use `raw_decode` from `{"playerLeaderboard":`.
- Tournament metadata includes `gender` ("Women"), used as the ingest gate.
- Competitor schools appear in the same payload. Filter `schoolName == "UC Davis"` before validation.
- Round IDs are 1–3 and match `courses[].roundId`.
- `robots.txt` returns 404. Terms of service have not been reviewed.
- `/teams` is not a valid route. `/results` and `/rankings` have no tournament index, and `?season=` has no effect.

## Roster Notes
- 2024-25 roster: `https://ucdavisaggies.com/sports/womens-golf/roster?season=2024-25` (the `/roster/season/...` form returns 404).
- 2026-27 roster is on the site at `/roster`. It is not ingested.

## Gotchas
- Pydantic `model_copy(update=...)` skips validation. Pass real `date` objects in tests.
- SQLite does not enforce FKs unless `PRAGMA foreign_keys=ON`. Ingest deletes children explicitly.
- The roster file's season must match the season derived from the event dates, or ingest raises.

## Open Items
1. 2022–2024 coverage: Clippd tournament IDs for those seasons are unknown. Options: user-supplied IDs, a golfstat schedule, or 2025 only (current choice).
2. Earlier rosters (2022–2024) not fetched.
3. Scorecard cross-check for one 2025 event. Hole values are not yet verified against an official scorecard.
4. Review Clippd terms before scheduled collection.
5. El Macero: confirm whether it had a women's event and which courses were played.
6. Team leaderboard (`team_result`) and `ingest_run` are deferred.
7. `.gitignore` covers `.venv`, caches, and `.env`. Add `*.db` if local SQLite files appear.

## Working Preferences
- Keep changes surgical. Do not commit secrets. Use the Co-authored-by trailer on commits.
- Confirm before destructive or shared-state actions.
- Use markdown links for file references in responses.
