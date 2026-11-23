from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Season(Base):
    __tablename__ = "season"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(7), unique=True)  # e.g. "2024-25"
    start_year: Mapped[int] = mapped_column(Integer, unique=True)


class Tournament(Base):
    __tablename__ = "tournament"

    id: Mapped[int] = mapped_column(primary_key=True)
    clippd_tournament_id: Mapped[str] = mapped_column(String(32), unique=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"))
    name: Mapped[str] = mapped_column(String(255))
    venue: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    rounds: Mapped[list["TournamentRound"]] = relationship(cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    clippd_course_id: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class TournamentRound(Base):
    __tablename__ = "tournament_round"

    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournament.id"), primary_key=True)
    round_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    total_par: Mapped[int] = mapped_column(Integer)
    total_yards: Mapped[int] = mapped_column(Integer)

    holes: Mapped[list["HolePar"]] = relationship(cascade="all, delete-orphan")


class HolePar(Base):
    __tablename__ = "hole_par_yards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tournament_id", "round_number"],
            ["tournament_round.tournament_id", "tournament_round.round_number"],
            ondelete="CASCADE",
        ),
        CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_hole_number"),
    )

    tournament_id: Mapped[int] = mapped_column(primary_key=True)
    round_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    hole_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    par: Mapped[int] = mapped_column(Integer)
    yards: Mapped[int] = mapped_column(Integer)


class Player(Base):
    __tablename__ = "player"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True)
    clippd_player_id: Mapped[str | None] = mapped_column(String(32), unique=True)


class RosterMembership(Base):
    __tablename__ = "roster_membership"

    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), primary_key=True)
    source_url: Mapped[str] = mapped_column(String(512))


class RoundScore(Base):
    __tablename__ = "round_score"
    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id", "round_number", name="uq_round_score"),
        ForeignKeyConstraint(
            ["tournament_id", "round_number"],
            ["tournament_round.tournament_id", "tournament_round.round_number"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournament.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))
    round_number: Mapped[int] = mapped_column(Integer)
    total_strokes: Mapped[int] = mapped_column(Integer)

    holes: Mapped[list["HoleScore"]] = relationship(cascade="all, delete-orphan")


class HoleScore(Base):
    __tablename__ = "hole_score"
    __table_args__ = (
        CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_score_hole_number"),
        CheckConstraint("strokes BETWEEN 1 AND 20", name="ck_strokes_range"),
    )

    round_score_id: Mapped[int] = mapped_column(
        ForeignKey("round_score.id", ondelete="CASCADE"), primary_key=True
    )
    hole_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    strokes: Mapped[int] = mapped_column(Integer)
