# ASA Golf: Data Sources and Proposed Schema (Phase 1, 2025 scope)

Status: 2025 scope implemented and tested. Migration generated. Not yet applied to Neon.

## Scope

- UC Davis women's golf only.
- Seasons: 2025 for now. 2022 onward is the target; 2022–2024 coverage is not yet found.
- Player records: UC Davis roster members only. Competitor data is kept at team/tournament level.
- Only courses the team played in the in-scope events.

## Sources

| Source | Role | Access | Status |
|---|---|---|---|
| Clippd Scoreboard (`scoreboard.clippd.com`) | Hole-level strokes, course pars and yards | Automated HTML fetch; leaderboard JSON is embedded in Next.js RSC payloads | Used for 2025 events |
| UC Davis Athletics roster (`ucdavisaggies.com/sports/womens-golf/roster`) | Authority for player roster membership | Automated HTML fetch | Used for roster allowlist |
| El Macero Classic (UC Davis-hosted) | Men's event | n/a | Excluded: men's-only |

Clippd's `robots.txt` returns 404. Its terms have not been reviewed. Automated HTML collection was approved.

## Verified 2025 Data

| Clippd tournament | Dates | Course (Clippd `courseId`) | Par / yards | UC Davis rows loaded | Excluded |
|---|---|---|---|---|---|
| 234273 — 2025 Big West Women's Championship | Apr 13–15, 2025 | Spanish Trail CC – Canyon/Lakes (`EB-USA-207`) | 72 / 6,315 | Karimanal, Bai, May, Leighton, Calderon | Kuang (substitute; null strokes; sentinel totals of 100000) |
| 232994 — 2025 Dr. Donnis Thompson Invitational | Mar 24–26, 2025 | Kaanapali Golf Resort – Royal Kaanapali (`CD-USA-7081`) | 72 / 5,993 | Karimanal, Leighton, May, Bai, Calderon | None |

Validation done:
- Each round's 18 hole strokes sum to the reported round total (30 of 30 checked rounds, both events).
- Each player's three round totals sum to the reported total.
- Each UC Davis player name matches the official roster (2024–25 list).

Not yet validated: hole values against an official scorecard or a second source.

## Ingestion Rules (proposed)

1. Keep only rows where `schoolName == "UC Davis"` and the player is on the official roster for that season.
2. Drop rounds with `playerStatus == SUBSTITUTE` or null strokes. Never store sentinel values (for example 100000).
3. Reject any round where the hole sum differs from the reported total.
4. Store course pars and yards per round from the tournament's `courses` payload.
5. Keep the raw payload per tournament for re-parsing.

## Proposed Schema (SQLAlchemy / Postgres)

```
season            (id, label UNIQUE, start_year UNIQUE)
tournament        (id, clippd_tournament_id UNIQUE, season_id FK, name, venue, start_date, end_date)
course            (id, clippd_course_id UNIQUE, name)
tournament_round  (tournament_id FK, round_number, course_id FK, total_par, total_yards, PK(tournament_id, round_number))
hole_par_yards    (tournament_id, round_number, hole_number, par, yards, PK(all three), FK to tournament_round)
player            (id, full_name UNIQUE, clippd_player_id UNIQUE NULL)
roster_membership (player_id FK, season_id FK, source_url, PK(player_id, season_id))
round_score       (id, tournament_id FK, player_id FK, round_number, total_strokes, UNIQUE(tournament_id, player_id, round_number))
hole_score        (round_score_id FK, hole_number, strokes, PK(round_score_id, hole_number), CHECK strokes BETWEEN 1 AND 20)
```

Notes:
- `season` is labelled by academic year (Aug–Jul), e.g. the Mar/Apr 2025 events are season `2024-25`.
- `player` has no team membership column. Membership is by `roster_membership`.
- Competitor schools are not stored. Only UC Davis rows reach the database.
- `clippd_player_id` links to Clippd for re-ingestion. The roster match uses names listed in `data/roster/`. Clippd's "Abigail Leighton" maps to roster "Abby Leighton" through `clippd_names`.
- Deferred from the first pass: `team_result` (the team leaderboard is not parsed yet) and `ingest_run` (load history).


## Pydantic Models (implemented in `src/asa_golf/schemas.py`)

- `CourseRound`: 18 pars and yards per round; hole sums must equal the course totals.
- `PlayerRound`: 18 hole strokes (1–20 each); hole sum must equal the round total.
- `PlayerResult`: round totals must sum to the player total.
- `RosterFile` / `RosterPlayer`: roster JSON in `data/roster/`, with Clippd name aliases.

## Open Items

1. 2022–2024 Clippd events: not discovered. Clippd has no browsable index, and web search found no UC Davis tournament pages. Options: you supply tournament IDs, or we use golfstat's UC Davis schedule to find events.
2. Scorecard cross-check for at least one 2025 event.
3. Roster for 2022–2024 seasons: only 2024–25 and 2026–27 pages were fetched. Earlier rosters are needed for those seasons.
4. Clippd terms of use review before scheduled collection.
5. El Macero course eligibility for the women's team, if a women's event was played there.
