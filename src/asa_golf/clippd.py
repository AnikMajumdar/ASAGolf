import json
import re
from pathlib import Path

from .schemas import CourseRound, ExcludedEntry, PlayerResult, PlayerRound, TournamentData

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_LEADERBOARD_RE = re.compile(r'\{"playerLeaderboard":')
TEAM_SCHOOL = "UC Davis"


def _rsc_text(html: str) -> str:
    return "".join(json.loads(chunk) for chunk in _PUSH_RE.findall(html))


def _leaderboard(html: str) -> dict:
    text = _rsc_text(html)
    match = _LEADERBOARD_RE.search(text)
    if match is None:
        raise ValueError("no playerLeaderboard payload found")
    obj, _ = json.JSONDecoder().raw_decode(text[match.start():])
    return obj


def _skip_reason(result: dict, round_count: int) -> str | None:
    rounds = result.get("rounds", [])
    if len(rounds) != round_count:
        return f"has {len(rounds)} rounds, expected {round_count}"
    for rnd in rounds:
        if rnd.get("playerStatus") == "SUBSTITUTE" or any(s is None for s in rnd.get("strokes", [])):
            return "substitute or missing hole scores"
    if any(total >= 100000 for total in result.get("scores", [])):
        return "sentinel to-par values"
    return None


def load_tournament(path: Path) -> TournamentData:
    html = Path(path).read_text(encoding="utf-8")
    board = _leaderboard(html)
    meta = board["tournament"]
    lb = board["playerLeaderboard"]

    courses = [
        CourseRound(
            round_number=c["roundId"],
            course_id=c["courseId"],
            course_name=c["courseName"],
            pars=c["pars"],
            yards=c["yards"],
            total_par=c["totalPar"],
            total_yards=c["totalYards"],
        )
        for c in lb["courses"]
    ]
    round_count = len(courses)

    players: list[PlayerResult] = []
    excluded: list[ExcludedEntry] = []
    for result in lb["results"]:
        name = result.get("playerName", "")
        school = result.get("schoolName") or ""
        if school != TEAM_SCHOOL:
            continue
        reason = _skip_reason(result, round_count)
        if reason:
            excluded.append(ExcludedEntry(player_name=name, school_name=school, reason=reason))
            continue
        rounds = [
            PlayerRound(
                round_number=rnd["roundId"],
                strokes=rnd["strokes"],
                total_strokes=result["strokes"][i],
            )
            for i, rnd in enumerate(result["rounds"])
        ]
        players.append(
            PlayerResult(
                clippd_player_id=str(result["playerId"]),
                player_name=name,
                school_name=school,
                rounds=rounds,
                total_strokes=result["totalStrokes"],
            )
        )

    return TournamentData(
        clippd_tournament_id=str(meta["tournamentId"]),
        name=meta["tournamentName"],
        gender=meta["gender"],
        start_date=meta["startDate"],
        end_date=meta["endDate"],
        venue=meta["venue"],
        courses=courses,
        players=players,
        excluded=excluded,
    )
