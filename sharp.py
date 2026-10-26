"""
Sharp board model.

Every game starts from Pinnacle's no-vig price. A pick is made only when a research-backed flag fires
and the sharp line hasn't already moved to price it in.

Pick flags (one per sport, the best-supported finding for each):
  NBA  home_b2b      Home team on the second night of a back-to-back, visitor on 1-2 days rest -> visitor ATS.
                     (19-season NBA study, Journal of Sports Economics 2010.)
  NHL  public_fav    Public heavily on the favorite -> underdog moneyline. (Paul & Weinbach 2009, NHL betting %.)
                     Proxy: PrizePicks heat on the favorite's players, from the fade board.
  NFL  (none yet)    Fading clinched top seeds is the best-supported NFL edge and only applies in
                     the last weeks of the season. Rest spots are shown as context.

Context notes (shown, never bet): rest gaps, short weeks and byes, big Pinnacle moves, props pulled.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from espn import norm
from teams import abbr_lookup

# ---- thresholds (starting points; tune once each flag has graded volume)
NBA_PRICED_IN = 1.5      # visitor spread already moved this many points toward visitor -> pass
NHL_FAV_MIN = 0.55       # favorite's no-vig win chance
NHL_HEAT_MIN = 10.0      # favorite heat minus dog heat (fade board units)
NHL_PRICED_IN = 0.03     # dog's win chance already up 3 points -> pass
BIG_MOVE = {"spreads": 2.0, "h2h": 0.05}
MOVE_CAP = 0.25

SPORT_KEY = {"NBA": "basketball_nba", "NFL": "americanfootball_nfl", "NHL": "icehockey_nhl"}
FLAG_NAMES = {"home_b2b": "NBA home back-to-back", "public_fav": "NHL public favorite"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS picks (
    pick_id TEXT PRIMARY KEY, league TEXT, flag TEXT, start TEXT,
    home TEXT, away TEXT, side TEXT, market TEXT, point REAL, price INTEGER, book TEXT,
    created_ts TEXT, updated_ts TEXT, close_point REAL, close_price INTEGER,
    home_score INTEGER, away_score INTEGER, result TEXT, units REAL
);"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def implied(p):
    if p is None:
        return None
    return 100 / (p + 100) if p > 0 else -p / (-p + 100)


def payout(p):
    return p / 100 if p > 0 else 100 / -p


def no_vig(a, b):
    ia, ib = implied(a), implied(b)
    return (None, None) if ia is None or ib is None else (ia / (ia + ib), ib / (ia + ib))


# ------------------------------------------------------------------ odds + PrizePicks from the fade board DB

def load_odds(fade: sqlite3.Connection, league: str) -> list[dict]:
    rows = fade.execute("""SELECT event_id, book, market, outcome, commence, home, away, point, price,
                                  open_point, open_price FROM odds_current WHERE sport = ?""",
                        (SPORT_KEY[league],)).fetchall()
    ev = {}
    for eid, book, mkt, oc, com, h, a, pt, pr, opt, opr in rows:
        e = ev.setdefault(eid, {"id": eid, "commence": com, "home": h, "away": a, "lines": {}})
        e["lines"][(book, mkt, oc)] = {"book": book, "point": pt, "price": pr, "open_point": opt, "open_price": opr}
    return list(ev.values())


def match(events, g):
    want = {norm(g["home"]), norm(g["away"])}
    for e in events:
        if {norm(e["home"]), norm(e["away"])} == want and abs((ts(e["commence"]) - ts(g["start"])).total_seconds()) < 18 * 3600:
            return e
    return None


def best(e, mkt, team):
    c = [l for (b, m, t), l in e["lines"].items() if m == mkt and t == team and l["price"] is not None]
    if not c:
        return None
    if mkt == "spreads":
        return max(c, key=lambda l: (l["point"] if l["point"] is not None else -99, payout(l["price"])))
    return max(c, key=lambda l: payout(l["price"]))


def pin(e, mkt, team):
    return e["lines"].get(("pinnacle", mkt, team))


def win_probs(e):
    """No-vig (home, away) from Pinnacle, else the average of the other books."""
    h, a = pin(e, "h2h", e["home"]), pin(e, "h2h", e["away"])
    if h and a:
        return no_vig(h["price"], a["price"])
    vals = []
    for (b, m, t), l in e["lines"].items():
        if m == "h2h" and t == e["home"]:
            other = e["lines"].get((b, "h2h", e["away"]))
            if other:
                vals.append(no_vig(l["price"], other["price"])[0])
    return (sum(vals) / len(vals), 1 - sum(vals) / len(vals)) if vals else (None, None)


def open_probs(e):
    h, a = pin(e, "h2h", e["home"]), pin(e, "h2h", e["away"])
    return no_vig(h["open_price"], a["open_price"]) if h and a else (None, None)


def pp_heat(fade: sqlite3.Connection, league: str, g) -> dict:
    """Fade-board heat per team for this game, plus how many props were pulled."""
    lookup = abbr_lookup(league)
    day = g["start"][:10]
    rows = fade.execute("""SELECT team, open_line, line, status FROM pp_current
                           WHERE league = ? AND odds_type = 'standard' AND substr(start_time,1,10) = ?""",
                        (league, day)).fetchall()
    out = {norm(g["home"]): {"heat": 0.0, "up": 0, "pulled": 0}, norm(g["away"]): {"heat": 0.0, "up": 0, "pulled": 0}}
    for team, o, l, status in rows:
        full = lookup.get((team or "").upper())
        if full not in out:
            continue
        if status == "removed":
            out[full]["pulled"] += 1
            continue
        if o and l != o:
            m = max(-MOVE_CAP, min(MOVE_CAP, (l - o) / max(o, 1.0)))
            out[full]["heat"] += m * 100
            out[full]["up"] += m > 0
    return out


# ------------------------------------------------------------------ flags

def context(league, g, e, heat) -> list[str]:
    notes = []
    hr, ar = g.get("home_rest"), g.get("away_rest")
    if league in ("NBA", "NHL"):
        for side, r in (("home", hr), ("away", ar)):
            if r == 0:
                notes.append(f"{g[side]} on the second night of a back-to-back.")
        if hr is not None and ar is not None and abs(hr - ar) >= 2:
            more = g["home"] if hr > ar else g["away"]
            notes.append(f"{more} has {abs(hr - ar)} more days of rest.")
    if league == "NFL":
        for side, r in (("home", hr), ("away", ar)):
            if r is not None and r <= 3:
                notes.append(f"{g[side]} on a short week.")
            if r is not None and r >= 12:
                notes.append(f"{g[side]} off a bye.")
    if e:
        mkt = "h2h" if league == "NHL" else "spreads"
        if mkt == "spreads":
            p = pin(e, "spreads", e["home"])
            if p and p["open_point"] is not None and p["point"] is not None and abs(p["point"] - p["open_point"]) >= BIG_MOVE[mkt]:
                toward = e["home"] if p["point"] < p["open_point"] else e["away"]
                notes.append(f"Pinnacle moved {abs(p['point'] - p['open_point']):g} points toward {toward}.")
        else:
            (ph, _), (oh, _) = win_probs(e), open_probs(e)
            if ph is not None and oh is not None and abs(ph - oh) >= BIG_MOVE[mkt]:
                toward = e["home"] if ph > oh else e["away"]
                notes.append(f"Pinnacle moved {abs(ph - oh) * 100:.0f} points of win chance toward {toward}. "
                             "Often a goalie change.")
    pulled = sum(v["pulled"] for v in heat.values())
    if pulled:
        notes.append(f"{pulled} PrizePicks props pulled for this game, usually injury or lineup news.")
    return notes


def nba_home_b2b(g, e):
    if g.get("home_rest") != 0 or g.get("away_rest") not in (1, 2):
        return None, None
    if not e:
        return None, "Rest spot fires, but there's no sportsbook line yet."
    p = pin(e, "spreads", e["away"])
    if p and p["open_point"] is not None and p["point"] is not None and p["open_point"] - p["point"] >= NBA_PRICED_IN:
        return None, f"Rest spot fires, but Pinnacle already moved {p['open_point'] - p['point']:g} points toward the visitor."
    b = best(e, "spreads", e["away"])
    if not b:
        return None, "Rest spot fires, but no visitor spread is posted."
    return {"flag": "home_b2b", "side": e["away"], "market": "spreads", **b,
            "why": f"{e['home']} is on the second night of a back-to-back and {e['away']} is rested."}, None


def nhl_public_fav(g, e, heat):
    if not e:
        return None, None
    ph, pa = win_probs(e)
    if ph is None:
        return None, None
    fav, dog, pf = (e["home"], e["away"], ph) if ph >= pa else (e["away"], e["home"], pa)
    if pf < NHL_FAV_MIN:
        return None, None
    hf, hd = heat[norm(fav)], heat[norm(dog)]
    if hf["heat"] - max(hd["heat"], 0) < NHL_HEAT_MIN or hf["up"] < 2:
        return None, None
    if hf["pulled"] or hd["pulled"]:
        return None, "Public is on the favorite, but props were pulled. Not fading news."
    oh, oa = open_probs(e)
    if oh is not None:
        dog_now, dog_open = (ph, oh) if dog == e["home"] else (pa, oa)
        if dog_now - dog_open >= NHL_PRICED_IN:
            return None, "Public is on the favorite, but the underdog's price has already shortened."
    b = best(e, "h2h", dog)
    if not b:
        return None, None
    return {"flag": "public_fav", "side": dog, "market": "h2h", **b,
            "why": f"PrizePicks action is piling onto {fav} players. Taking the underdog."}, None


def analyze(fade: sqlite3.Connection, picks: sqlite3.Connection, league: str, games: list[dict], now=None):
    now = now or utcnow()
    events = load_odds(fade, league)
    out = []
    for g in games:
        e = match(events, g)
        heat = pp_heat(fade, league, g)
        ph, pa = win_probs(e) if e else (None, None)
        pick, near = None, None
        if league == "NBA":
            pick, near = nba_home_b2b(g, e)
        elif league == "NHL":
            pick, near = nhl_public_fav(g, e, heat)
        row = {**g, "event": e, "p_home": ph, "p_away": pa, "notes": context(league, g, e, heat),
               "pick": pick, "near": near, "line": market_line(league, e)}
        if pick:
            save(picks, league, g, pick, now)
        out.append(row)
    picks.commit()
    return out


def market_line(league, e):
    if not e:
        return None
    if league == "NHL":
        return None
    p = pin(e, "spreads", e["home"]) or best(e, "spreads", e["home"])
    if not p or p["point"] is None:
        return None
    pt = p["point"]
    if pt == 0:
        return "Pick'em"
    fav = e["home"] if pt < 0 else e["away"]
    return f"{fav} by {abs(pt):g}"


def save(picks, league, g, pk, now):
    pid = f"{league}:{g['id']}:{pk['flag']}"
    r = picks.execute("SELECT start FROM picks WHERE pick_id=?", (pid,)).fetchone()
    if r and ts(r[0]) <= now:
        return
    picks.execute("""INSERT INTO picks (pick_id, league, flag, start, home, away, side, market, point, price, book,
                       created_ts, updated_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(pick_id) DO UPDATE SET point=excluded.point, price=excluded.price,
                       book=excluded.book, updated_ts=excluded.updated_ts""",
                  (pid, league, pk["flag"], g["start"], g["home"], g["away"], pk["side"], pk["market"],
                   pk["point"], pk["price"], pk["book"], now.isoformat(), now.isoformat()))


def withdraw_missing(picks, live: set[str], now):
    for (pid,) in picks.execute("SELECT pick_id FROM picks WHERE result IS NULL AND start > ?", (now.isoformat(),)):
        if pid not in live:
            picks.execute("DELETE FROM picks WHERE pick_id=?", (pid,))
    picks.commit()


# ------------------------------------------------------------------ grading + record

def grade(picks, fade, done: list[dict]) -> int:
    n = 0
    for (pid, league, start, home, away, side, mkt, pt, pr, book) in picks.execute(
            "SELECT pick_id, league, start, home, away, side, market, point, price, book FROM picks WHERE result IS NULL").fetchall():
        g = next((x for x in done if {norm(x["home"]), norm(x["away"])} == {norm(home), norm(away)}
                  and abs((ts(x["start"]) - ts(start)).total_seconds()) < 18 * 3600), None)
        if not g or g["home_score"] is None:
            continue
        hs, as_ = (g["home_score"], g["away_score"]) if norm(g["home"]) == norm(home) else (g["away_score"], g["home_score"])
        mine, theirs = (hs, as_) if side == home else (as_, hs)
        margin = mine - theirs + ((pt or 0) if mkt == "spreads" else 0)
        res = "win" if margin > 0 else "loss" if margin < 0 else "push"
        units = payout(pr) if res == "win" else -1.0 if res == "loss" else 0.0
        close = fade.execute("""SELECT h.point, h.price FROM odds_history h JOIN odds_current c
                                  ON c.event_id=h.event_id AND c.book=h.book AND c.market=h.market AND c.outcome=h.outcome
                                WHERE h.book='pinnacle' AND h.market=? AND h.outcome=? AND c.home=? AND c.away=?
                                  AND h.ts <= ? ORDER BY h.ts DESC LIMIT 1""", (mkt, side, home, away, start)).fetchone()
        picks.execute("""UPDATE picks SET home_score=?, away_score=?, result=?, units=?, close_point=?, close_price=?
                         WHERE pick_id=?""", (hs, as_, res, round(units, 3), *(close or (None, None)), pid))
        n += 1
    picks.commit()
    return n


def record(picks):
    rec = defaultdict(lambda: {"w": 0, "l": 0, "p": 0, "units": 0.0, "clv": []})
    for flag, res, u, mkt, pt, pr, cpt, cpr in picks.execute(
            "SELECT flag, result, units, market, point, price, close_point, close_price FROM picks WHERE result IS NOT NULL"):
        for k in (flag, "all"):
            r = rec[k]
            r[{"win": "w", "loss": "l", "push": "p"}[res]] += 1
            r["units"] += u or 0
            if mkt == "spreads" and cpt is not None:
                r["clv"].append(pt > cpt or (pt == cpt and payout(pr) > payout(cpr)))
            elif cpr is not None:
                r["clv"].append(payout(pr) > payout(cpr))
    return rec
