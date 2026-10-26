"""
Fetch schedules (ESPN), grade finished picks, run the flags, write docs/index.html.

    python build.py
Env: FADE_DB = path to the fade board's database (odds + PrizePicks). Default ../fade-board/data/fade.db
"""
from __future__ import annotations

import html
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import espn
import sharp

HERE = os.path.dirname(os.path.abspath(__file__))
PT = ZoneInfo("America/Los_Angeles")
LEAGUES = ["NBA", "NHL", "NFL"]
BOOKS = {"pinnacle": "Pinnacle", "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "caesars": "Caesars"}
FLAG_TEXT = {
    "home_b2b": "NBA: home team on the second night of a back-to-back against a rested visitor. Back the visitor.",
    "public_fav": "NHL: public money piling onto a clear favorite. Back the underdog.",
}


def esc(x):
    return html.escape(str(x))


def odds(p):
    return "" if p is None else (f"+{p}" if p > 0 else f"\u2212{abs(p)}")


def pts(p):
    return "PK" if not p else (f"+{p:g}" if p > 0 else f"\u2212{abs(p):g}")


def when(s):
    return sharp.ts(s).astimezone(PT).strftime("%a %-I:%M %p")


def card(g):
    away, home = esc(g["away"]), esc(g["home"])
    ph, pa = g["p_home"], g["p_away"]
    if ph is not None:
        fav, p = (home, ph) if ph >= pa else (away, pa)
        prob = f"""<p class="fav">{fav} to win: <strong>{p * 100:.0f}%</strong></p>
        <div class="split" role="img" aria-label="{away} {pa * 100:.0f}%, {home} {ph * 100:.0f}%">
          <span class="a" style="width:{pa * 100:.1f}%"></span><span class="h" style="width:{ph * 100:.1f}%"></span></div>
        <div class="split-labels"><span>{esc(g['away_abbr'])} {pa * 100:.0f}%</span><span>{esc(g['home_abbr'])} {ph * 100:.0f}%</span></div>"""
    else:
        prob = '<p class="muted">No sharp price posted yet.</p>'
    line = f'<p class="muted">Market: {esc(g["line"])}</p>' if g["line"] else ""
    notes = "".join(f"<li>{esc(n)}</li>" for n in g["notes"])
    notes = f'<ul class="notes">{notes}</ul>' if notes else ""
    if g["pick"]:
        pk = g["pick"]
        num = pts(pk["point"]) if pk["market"] == "spreads" else "to win"
        verdict = f"""<div class="pick"><p><strong>{esc(pk['side'])} {num} ({odds(pk['price'])})</strong></p>
          <p class="muted">{esc(pk['why'])} Best price at {esc(BOOKS.get(pk['book'], pk['book']))}.</p></div>"""
        cls = "game has-pick"
    else:
        verdict = f'<p class="nopick">No play. {esc(g["near"])}</p>' if g["near"] else '<p class="nopick">No play.</p>'
        cls = "game"
    return f"""<article class="{cls}">
  <header><h3>{away} at {home}</h3><time>{when(g['start'])}</time></header>
  {prob}{line}{verdict}{notes}
</article>"""


def record_table(rec):
    def row(name, r):
        n = r["w"] + r["l"] + r["p"]
        clv = f"{100 * sum(r['clv']) / len(r['clv']):.0f}%" if r["clv"] else "n/a"
        return (f"<tr><th>{esc(name)}</th><td>{r['w']}\u2013{r['l']}{'' if not r['p'] else chr(8211) + str(r['p'])}</td>"
                f"<td>{r['units']:+.2f}u</td><td>{clv}</td><td>{n}</td></tr>")
    rows = [row(sharp.FLAG_NAMES[f], rec[f]) for f in sharp.FLAG_NAMES if f in rec]
    if not rows:
        return '<p class="muted">No graded picks yet. Each flag gets its own line here once games finish.</p>'
    rows.append(row("All flags", rec["all"]))
    return f"""<div class="scroll"><table><thead><tr><th>Flag</th><th>Record</th><th>Units</th>
      <th>Beat close</th><th>Picks</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b1f24;--muted:#5d6670;--rule:#dde1e6;--home:#2c5d8f;--away:#b9c4cf;
 --pick:#1d7a4f;--pick-bg:#e8f4ee;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#121519;--card:#1b2026;--ink:#e8ecf0;--muted:#9aa4ae;--rule:#2c333b;
 --home:#6ea6dc;--away:#3d4752;--pick:#5fcf98;--pick-bg:#173326;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Source Sans 3",system-ui,-apple-system,sans-serif;
 padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0)}
main{max-width:700px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:30px;line-height:1.15;margin:0 0 4px}
h2{font-size:22px;margin:36px 0 10px}
h3{font-size:18px;margin:0;line-height:1.25}
.muted{color:var(--muted);margin:4px 0 0;font-size:15px}
.stats{display:flex;gap:28px;margin:18px 0;flex-wrap:wrap}
.stats div{display:flex;flex-direction:column}
.stats b{font-size:26px;font-variant-numeric:tabular-nums}
.stats span{color:var(--muted);font-size:14px}
.about{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px;font-size:15px}
.about p{margin:0 0 8px}.about p:last-child{margin:0}
.about ul{margin:6px 0 8px;padding-left:20px}
.game{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px;margin:10px 0}
.game header{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
time{color:var(--muted);font-size:14px;white-space:nowrap}
.fav{margin:10px 0 6px}
.split{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--rule)}
.split .a{background:var(--away)}.split .h{background:var(--home)}
.split-labels{display:flex;justify-content:space-between;color:var(--muted);font-size:13px;margin-top:3px}
.pick{background:var(--pick-bg);border-radius:6px;padding:10px 12px;margin:12px 0 0}
.pick p{margin:0}.pick strong{color:var(--pick);font-size:17px}
.nopick{color:var(--muted);margin:10px 0 0;font-size:15px}
.notes{margin:8px 0 0;padding-left:20px;color:var(--muted);font-size:14.5px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 12px 6px 0;border-bottom:1px solid var(--rule);white-space:nowrap}
thead th{color:var(--muted);font-weight:500}
footer{margin-top:40px;color:var(--muted);font-size:14px}
"""


def render(by_league, rec, now, errors):
    n_games = sum(len(v) for v in by_league.values())
    n_picks = sum(1 for v in by_league.values() for g in v if g["pick"])
    all_rec = rec.get("all")
    rec_txt = f"{all_rec['w']}\u2013{all_rec['l']}" if all_rec else "0\u20130"
    sections = []
    for lg in LEAGUES:
        games = sorted(by_league.get(lg, []), key=lambda g: (g["pick"] is None, g["start"]))
        if games:
            sections.append(f"<section><h2>{lg}</h2>{''.join(card(g) for g in games)}</section>")
    err = "".join(f'<p class="muted">{esc(e)}</p>' for e in errors)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="refresh" content="300"><title>Sharp board</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<h1>Sharp board: NBA, NHL, NFL</h1>
<p class="muted">Updated {now.astimezone(PT).strftime("%a %b %-d, %-I:%M %p PT")}</p>
<div class="stats"><div><b>{n_games}</b><span>Games</span></div><div><b>{n_picks}</b><span>Picks</span></div>
<div><b>{rec_txt}</b><span>Record</span></div></div>
<div class="about">
<p>Every game starts from Pinnacle's price with the margin removed: the sharpest number available.
A pick appears only when a research-backed spot fires and that price hasn't already moved to account for it.</p>
<ul><li>{FLAG_TEXT['home_b2b']}</li><li>{FLAG_TEXT['public_fav']}</li>
<li>NFL: no pick flag until late season, when fading teams that have clinched top seeds applies. Rest spots are shown as context.</li></ul>
<p>Published edges like these are small and fade once known. The record below is the only proof that counts.</p>
</div>
{err}
<h2>Record</h2>{record_table(rec)}
{''.join(sections) or '<p class="muted">No games on the board right now.</p>'}
<footer>Forecasts and research. Not betting advice.</footer>
</main></body></html>"""


def main():
    fade_path = os.environ.get("FADE_DB", os.path.join(HERE, "..", "fade-board", "data", "fade.db"))
    fade = sqlite3.connect(f"file:{fade_path}?mode=ro", uri=True)
    picks = sqlite3.connect(os.path.join(HERE, "data", "sharp.db"))
    picks.executescript(sharp.SCHEMA)
    now = sharp.utcnow()
    today = now.astimezone(espn.ET).date()
    by_league, errors, live = {}, [], set()
    for lg in LEAGUES:
        try:
            upcoming, done = espn.board(lg, today)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{lg} schedule unavailable this update ({e.__class__.__name__}).")
            continue
        sharp.grade(picks, fade, done)
        games = sharp.analyze(fade, picks, lg, upcoming, now)
        live |= {f"{lg}:{g['id']}:{g['pick']['flag']}" for g in games if g["pick"]}
        by_league[lg] = games
    sharp.withdraw_missing(picks, live, now)
    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    with open(os.path.join(HERE, "docs", "index.html"), "w") as f:
        f.write(render(by_league, sharp.record(picks), now, errors))
    print(f"[sharp] {sum(map(len, by_league.values()))} games, {len(live)} picks")


if __name__ == "__main__":
    main()
