"""Schedules, results and rest days from ESPN's public scoreboard feed (no key needed)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
PATHS = {"NBA": "basketball/nba", "NFL": "football/nfl", "NHL": "hockey/nhl"}
LOOKBACK = {"NBA": 4, "NHL": 4, "NFL": 16}   # days back needed to find each team's previous game
LOOKAHEAD = {"NBA": 1, "NHL": 1, "NFL": 7}   # days ahead to show on the board


def norm(s: str) -> str:
    return s.lower().replace(".", "").replace("é", "e").strip()


def fetch(league: str, start: date, end: date) -> list[dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{PATHS[league]}/scoreboard"
    r = requests.get(url, params={"dates": f"{start:%Y%m%d}-{end:%Y%m%d}", "limit": 1000}, timeout=30)
    r.raise_for_status()
    return parse(r.json(), league)


def parse(payload: dict, league: str) -> list[dict]:
    games = []
    for ev in payload.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in teams or "away" not in teams:
            continue
        status = (ev.get("status") or {}).get("type") or {}
        def score(c):
            try:
                return int(float(c.get("score")))
            except (TypeError, ValueError):
                return None
        games.append({
            "league": league,
            "id": str(ev.get("id")),
            "start": ev.get("date"),
            "home": teams["home"]["team"]["displayName"],
            "away": teams["away"]["team"]["displayName"],
            "home_abbr": teams["home"]["team"].get("abbreviation"),
            "away_abbr": teams["away"]["team"].get("abbreviation"),
            "home_score": score(teams["home"]),
            "away_score": score(teams["away"]),
            "completed": bool(status.get("completed")),
            "neutral": bool(comp.get("neutralSite")),
        })
    return games


def local_day(iso: str) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET).date()


def add_rest(games: list[dict]) -> None:
    """Days of rest before each game for both teams (0 = second night of a back-to-back)."""
    by_team: dict[str, list[date]] = {}
    for g in games:
        for side in ("home", "away"):
            by_team.setdefault(norm(g[side]), []).append(local_day(g["start"]))
    for g in games:
        d = local_day(g["start"])
        for side in ("home", "away"):
            prior = [x for x in by_team[norm(g[side])] if x < d]
            g[f"{side}_rest"] = (d - max(prior)).days - 1 if prior else None


def board(league: str, today: date) -> tuple[list[dict], list[dict]]:
    """(upcoming games with rest days, recently completed games for grading)."""
    games = fetch(league, today - timedelta(days=LOOKBACK[league]), today + timedelta(days=LOOKAHEAD[league]))
    add_rest(games)
    upcoming = [g for g in games if not g["completed"] and local_day(g["start"]) >= today]
    done = [g for g in games if g["completed"]]
    return upcoming, done
