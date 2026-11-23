from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from asa_golf.clippd import load_tournament
from asa_golf.ingest import ingest_tournament, load_roster
from asa_golf.models import Base, HoleScore, RoundScore
from asa_golf.schemas import PlayerRound

DATA = Path(__file__).resolve().parents[1] / "data"
BIG_WEST = DATA / "raw/clippd/234273_2025_big_west_women_player.html"
THOMPSON = DATA / "raw/clippd/232994_2025_thompson_invitational_player.html"
ROSTER = load_roster(DATA / "roster/ucdavis_womens_golf_2024-25.json")


def test_big_west_excludes_substitute_and_keeps_uc_davis_only():
    data = load_tournament(BIG_WEST)
    assert data.gender == "Women"
    assert [p.player_name for p in data.players] == [
        "Vani Karimanal", "Yu Bai", "Skyler May", "Abigail Leighton", "Lauren Calderon",
    ]
    assert [e.player_name for e in data.excluded] == ["Elina Kuang"]
    assert data.courses[0].total_yards == 6315


def test_thompson_loads_all_uc_davis_rounds_with_course_totals():
    data = load_tournament(THOMPSON)
    assert len(data.players) == 5
    assert not data.excluded
    assert data.courses[0].total_par == 72
    assert data.courses[0].total_yards == 5993


def test_player_round_rejects_hole_sum_mismatch():
    with pytest.raises(ValidationError):
        PlayerRound(round_number=1, strokes=[4] * 17 + [5], total_strokes=74)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_ingest_is_idempotent_and_stores_hole_level_scores(session):
    data = load_tournament(BIG_WEST)
    ingest_tournament(session, data, ROSTER)
    session.commit()
    ingest_tournament(session, data, ROSTER)
    session.commit()

    assert session.scalar(select(func.count(RoundScore.id))) == 15
    assert session.scalar(select(func.count(HoleScore.hole_number))) == 15 * 18


def test_ingest_rejects_men_and_out_of_season_events(session):
    data = load_tournament(BIG_WEST)
    with pytest.raises(ValueError, match="only women"):
        ingest_tournament(session, data.model_copy(update={"gender": "Men"}), ROSTER)
    with pytest.raises(ValueError, match="season"):
        ingest_tournament(session, data.model_copy(update={"start_date": date(2023, 4, 13)}), ROSTER)
