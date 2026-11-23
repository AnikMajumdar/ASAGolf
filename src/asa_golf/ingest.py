import argparse
import os
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .clippd import load_tournament
from .models import (
    Course,
    HoleScore,
    HolePar,
    Player,
    RosterMembership,
    RoundScore,
    Season,
    Tournament,
    TournamentRound,
)
from .schemas import RosterFile, RosterPlayer, TournamentData

TEAM_GENDER = "Women"
TEAM_SCHOOL = "UC Davis"


def season_for(start: date) -> tuple[int, str]:
    """Golf seasons run August to July; the label is named by its starting year."""
    start_year = start.year if start.month >= 8 else start.year - 1
    return start_year, f"{start_year}-{str(start_year + 1)[-2:]}"


def load_roster(path: Path) -> RosterFile:
    return RosterFile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def match_roster(clippd_name: str, roster: RosterFile) -> RosterPlayer | None:
    for player in roster.players:
        if clippd_name in player.clippd_names or clippd_name == player.full_name:
            return player
    return None


def _get_or_create_season(session: Session, start_year: int, label: str) -> Season:
    season = session.scalar(select(Season).where(Season.start_year == start_year))
    if season is None:
        season = Season(start_year=start_year, label=label)
        session.add(season)
        session.flush()
    return season


def _get_or_create_course(session: Session, course_id: str, name: str) -> Course:
    course = session.scalar(select(Course).where(Course.clippd_course_id == course_id))
    if course is None:
        course = Course(clippd_course_id=course_id, name=name)
        session.add(course)
        session.flush()
    return course


def ingest_tournament(session: Session, data: TournamentData, roster: RosterFile) -> dict[str, int]:
    if data.gender != TEAM_GENDER:
        raise ValueError(f"{data.name} is '{data.gender}', but only women's events are in scope")

    start_year, label = season_for(data.start_date)
    if label != roster.season:
        raise ValueError(f"{data.name} is in season {label}, but roster file is {roster.season}")

    season = _get_or_create_season(session, start_year, label)

    tournament = session.scalar(
        select(Tournament).where(Tournament.clippd_tournament_id == data.clippd_tournament_id)
    )
    if tournament is None:
        tournament = Tournament(clippd_tournament_id=data.clippd_tournament_id, season_id=season.id)
        session.add(tournament)
    tournament.season_id = season.id
    tournament.name = data.name
    tournament.venue = data.venue
    tournament.start_date = data.start_date
    tournament.end_date = data.end_date
    session.flush()

    # Re-running a tournament replaces its rows, so ingestion is idempotent.
    # Children are deleted explicitly so this also holds where FK cascades are not enforced (e.g. SQLite).
    score_ids = select(RoundScore.id).where(RoundScore.tournament_id == tournament.id)
    session.execute(delete(HoleScore).where(HoleScore.round_score_id.in_(score_ids)))
    session.execute(delete(RoundScore).where(RoundScore.tournament_id == tournament.id))
    session.execute(delete(HolePar).where(HolePar.tournament_id == tournament.id))
    session.execute(delete(TournamentRound).where(TournamentRound.tournament_id == tournament.id))
    session.flush()

    for course_round in data.courses:
        course = _get_or_create_course(session, course_round.course_id, course_round.course_name)
        tr = TournamentRound(
            tournament_id=tournament.id,
            round_number=course_round.round_number,
            course_id=course.id,
            total_par=course_round.total_par,
            total_yards=course_round.total_yards,
        )
        tr.holes = [
            HolePar(
                round_number=course_round.round_number,
                hole_number=h + 1,
                par=course_round.pars[h],
                yards=course_round.yards[h],
            )
            for h in range(len(course_round.pars))
        ]
        session.add(tr)
    session.flush()

    counts = {"players": 0, "rounds": 0, "holes": 0, "excluded": len(data.excluded)}
    for result in data.players:
        if result.school_name != TEAM_SCHOOL:
            continue
        roster_player = match_roster(result.player_name, roster)
        if roster_player is None:
            raise ValueError(f"{result.player_name} is not on the {roster.season} roster")

        player = session.scalar(select(Player).where(Player.full_name == roster_player.full_name))
        if player is None:
            player = Player(full_name=roster_player.full_name)
            session.add(player)
        if player.clippd_player_id is None:
            player.clippd_player_id = result.clippd_player_id
        session.flush()

        if session.get(RosterMembership, (player.id, season.id)) is None:
            session.add(RosterMembership(player_id=player.id, season_id=season.id, source_url=roster.source_url))

        counts["players"] += 1
        for rnd in result.rounds:
            score = RoundScore(
                tournament_id=tournament.id,
                player_id=player.id,
                round_number=rnd.round_number,
                total_strokes=rnd.total_strokes,
            )
            score.holes = [
                HoleScore(hole_number=h + 1, strokes=strokes) for h, strokes in enumerate(rnd.strokes)
            ]
            session.add(score)
            counts["rounds"] += 1
            counts["holes"] += len(rnd.strokes)
    session.flush()
    return counts


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or os.environ["DATABASE_URL"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Clippd women's tournament HTML into the database.")
    parser.add_argument("--roster", type=Path, required=True, help="Roster JSON, e.g. data/roster/*.json")
    parser.add_argument("files", nargs="+", type=Path, help="Saved Clippd player leaderboard HTML files")
    args = parser.parse_args()

    roster = load_roster(args.roster)
    engine = make_engine()
    with Session(engine) as session, session.begin():
        for path in args.files:
            data = load_tournament(path)
            counts = ingest_tournament(session, data, roster)
            print(f"{data.name}: {counts}")


if __name__ == "__main__":
    main()
