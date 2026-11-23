from datetime import date

from pydantic import BaseModel, Field, model_validator

HOLES = 18
MIN_STROKES = 1
MAX_STROKES = 20


class CourseRound(BaseModel):
    round_number: int = Field(ge=1)
    course_id: str
    course_name: str
    pars: list[int]
    yards: list[int]
    total_par: int
    total_yards: int

    @model_validator(mode="after")
    def check_totals(self) -> "CourseRound":
        if len(self.pars) != HOLES or len(self.yards) != HOLES:
            raise ValueError(f"round {self.round_number} must have {HOLES} holes")
        if sum(self.pars) != self.total_par:
            raise ValueError(f"round {self.round_number} hole pars do not sum to total_par")
        if sum(self.yards) != self.total_yards:
            raise ValueError(f"round {self.round_number} hole yards do not sum to total_yards")
        return self


class PlayerRound(BaseModel):
    round_number: int = Field(ge=1)
    strokes: list[int]
    total_strokes: int

    @model_validator(mode="after")
    def check_strokes(self) -> "PlayerRound":
        if len(self.strokes) != HOLES:
            raise ValueError(f"round {self.round_number} must have {HOLES} hole scores")
        if any(not MIN_STROKES <= s <= MAX_STROKES for s in self.strokes):
            raise ValueError(f"round {self.round_number} has a hole score outside {MIN_STROKES}-{MAX_STROKES}")
        if sum(self.strokes) != self.total_strokes:
            raise ValueError(f"round {self.round_number} hole strokes do not sum to total_strokes")
        return self


class PlayerResult(BaseModel):
    clippd_player_id: str
    player_name: str
    school_name: str
    rounds: list[PlayerRound] = Field(min_length=1)
    total_strokes: int

    @model_validator(mode="after")
    def check_total(self) -> "PlayerResult":
        if sum(r.total_strokes for r in self.rounds) != self.total_strokes:
            raise ValueError(f"{self.player_name}: round totals do not sum to total_strokes")
        return self


class ExcludedEntry(BaseModel):
    player_name: str
    school_name: str
    reason: str


class TournamentData(BaseModel):
    clippd_tournament_id: str
    name: str
    gender: str
    start_date: date
    end_date: date
    venue: str
    courses: list[CourseRound]
    players: list[PlayerResult]
    excluded: list[ExcludedEntry] = []


class RosterPlayer(BaseModel):
    full_name: str
    clippd_names: list[str] = Field(min_length=1)


class RosterFile(BaseModel):
    season: str
    source_url: str
    players: list[RosterPlayer]
