import os, sys, sqlite3
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(1, os.path.join(HERE, "..", "fade-board"))
import scraper, espn, sharp, build

now = datetime.now(timezone.utc).replace(microsecond=0)
def iso(dt): return dt.strftime("%Y-%m-%dT%H:%MZ")
tonight = now + timedelta(hours=6)

def ev(i, start, home, ha, away, aa, done=False, hs=None, as_=None):
    return {"id": i, "date": iso(start), "status": {"type": {"completed": done}},
            "competitions": [{"neutralSite": False, "competitors": [
                {"homeAway": "home", "team": {"displayName": home, "abbreviation": ha}, "score": str(hs) if hs is not None else "0"},
                {"homeAway": "away", "team": {"displayName": away, "abbreviation": aa}, "score": str(as_) if as_ is not None else "0"}]}]}
nba = espn.parse({"events": [
    ev("1", tonight - timedelta(days=1), "Boston Celtics", "BOS", "Miami Heat", "MIA", True, 110, 100),
    ev("2", tonight - timedelta(days=2), "Orlando Magic", "ORL", "New York Knicks", "NY", True, 99, 101),
    ev("3", tonight, "Boston Celtics", "BOS", "New York Knicks", "NY")]}, "NBA")
espn.add_rest(nba)
g = nba[2]; assert (g["home_rest"], g["away_rest"]) == (0, 1), (g["home_rest"], g["away_rest"])

fade = scraper.connect(":memory:")
def odds(eid, sport, book, mkt, team, home, away, pt, pr, opt=None, opr=None, start=tonight):
    fade.execute("INSERT INTO odds_current VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, book, mkt, team, sport, start.isoformat(), home, away, pt, pr, pt if opt is None else opt, pr if opr is None else opr, now.isoformat(), now.isoformat()))
H, A = "Boston Celtics", "New York Knicks"
odds("e1","basketball_nba","pinnacle","spreads",H,H,A,-5.5,-108,-6.0); odds("e1","basketball_nba","pinnacle","spreads",A,H,A,5.5,-108,6.0)
odds("e1","basketball_nba","fanduel","spreads",A,H,A,6.0,-112)
odds("e1","basketball_nba","pinnacle","h2h",H,H,A,None,-220); odds("e1","basketball_nba","pinnacle","h2h",A,H,A,None,185)

NH, NA = "New York Rangers", "Columbus Blue Jackets"
nhl = espn.parse({"events": [ev("9", tonight, NH, "NYR", NA, "CBJ")]}, "NHL"); espn.add_rest(nhl)
odds("e9","icehockey_nhl","pinnacle","h2h",NH,NH,NA,None,-190,opr=-185); odds("e9","icehockey_nhl","pinnacle","h2h",NA,NH,NA,None,170,opr=165)
odds("e9","icehockey_nhl","draftkings","h2h",NA,NH,NA,None,175)
pst = tonight.isoformat()
rows = [{"projection_id": f"n{i}", "league": "NHL", "player_id": f"q{i}", "team": "NYR", "opponent": "CBJ", "game_id": "x",
         "stat_type": "Shots", "odds_type": "standard", "line": l, "start_time": pst, "status": "pre_game"} for i, l in enumerate([2.5, 3.5, 1.5])]
scraper.store_pp(fade, rows, [], (now - timedelta(hours=3)).isoformat(), {"NHL"})
for r, l in zip(rows, [3.5, 4.5, 2.5]): r["line"] = l
scraper.store_pp(fade, rows, [], (now - timedelta(hours=1)).isoformat(), {"NHL"})
fade.commit()

picks = sqlite3.connect(":memory:"); picks.executescript(sharp.SCHEMA)
nb = sharp.analyze(fade, picks, "NBA", [g], now)
print("NBA:", nb[0]["pick"] and {k: nb[0]["pick"][k] for k in ("side","point","price","book")}, nb[0]["near"], nb[0]["notes"])
assert nb[0]["pick"]["side"] == A and nb[0]["pick"]["point"] == 6.0 and nb[0]["pick"]["book"] == "fanduel"
nh = sharp.analyze(fade, picks, "NHL", nhl, now)
print("NHL:", nh[0]["pick"] and {k: nh[0]["pick"][k] for k in ("side","price","book")}, nh[0]["near"])
assert nh[0]["pick"]["side"] == NA and nh[0]["pick"]["price"] == 175

done = espn.parse({"events": [ev("3", tonight, H, "BOS", A, "NY", True, 104, 100), ev("9", tonight, NH, "NYR", NA, "CBJ", True, 4, 2)]}, "NBA")
assert sharp.grade(picks, fade, done) == 2
rec = sharp.record(picks); print({k: (v["w"], v["l"], round(v["units"],2)) for k, v in rec.items()})
html = build.render({"NBA": nb, "NHL": nh, "NFL": []}, rec, now, [])
open("/tmp/sharp.html", "w").write(html); print("rendered", len(html))
