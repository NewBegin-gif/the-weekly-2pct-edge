"""Het openbare logboek van de echte bot op theweekly2pctedge.com (Daan, 21 okt 2026: "Doen").

Idee: "verkoop het meetlint, niet de rendementsbelofte". Eén pagina, wekelijks bijgewerkt, uit de
publieke read-only endpoints van het botdashboard (geen databasetoegang nodig):
  /api/weekly-performance   gerealiseerde winst per week, % van het actieve kapitaal
  /api/strategy-comparison  per strategie: rendement per afgeronde ronde, aantal, houdduur
  /api/portfolio-history    gerealiseerd vs. open (unrealized) over de laatste 7 dagen

Regels (Daan): alleen percentages, nooit bedragen of kapitaal; een week vertraagd; geen signalen,
geen advies. De lekken (fees, time-decay, ...) zijn eerdere metingen met hun meetdatum.

Sinds Daans ja (21 okt 2026) is dit de homepage van w2e. Draait dagelijks in dagelijkse_data.py, maar
herschrijft alleen als er een nieuwe week bij komt (door de vertraging: op maandag), anders zou de pagina
elke dag van datum wisselen zonder nieuwe inhoud. Dan schuift ook de lastmod in w2e/sitemap.xml mee.

    python3 bouw/build_logboek.py                    # w2e/index.html, alleen bij een nieuwe week
    python3 bouw/build_logboek.py --forceer          # altijd herschrijven
    python3 bouw/build_logboek.py --uit <pad.html>   # los concept
"""
import datetime
import html
import json
import pathlib
import re
import statistics
import sys
import urllib.request

W2E = pathlib.Path(__file__).resolve().parent.parent
API = "https://bitcoin-cycle-bot-eu.replit.app/api/"
DOEL = 0.5
VERTRAGING_DAGEN = 7

# Gemeten lekken: (kop, uitleg, meetdatum). Alleen percentages; bron = eigen metingen op de bot.
LEKKEN = [
    ("Exchange fees took about a fifth of gross profit",
     "Between late April and early August, fees came to roughly 20% of gross trading profit. The bot now books the "
     "real fee per fill. The exchange charges 0.18% per taker order and 0.09% per maker order at the bot's volume.",
     "measured 5 Aug 2026; fee tiers read 8 Sep 2026"),
    ("Lowering the profit target over time gave money away",
     "A 'time-decay' rule lowered the sell target as a position aged. Of 152 sales it touched over 55 days, the "
     "original target was still reached in 78% of cases (median: 3 hours later). The rule gave up about 0.33% per "
     "trade, so it was switched off.",
     "measured 5 Aug 2026"),
    ("A safety filter froze the buy ladder",
     "A hard block on buying when RSI was above 70 also stopped the ladder from following the price, so a later "
     "shallow dip caught nothing. It became a taper: smaller orders between RSI 70 and 80, a hard block only above 80.",
     "changed 9 Aug 2026"),
    ("The weekly report undercounted by about half",
     "The report filtered on when a position started instead of when it was sold, so positions spanning two weeks "
     "disappeared. Fixed, and checked against the trade records.",
     "fixed 9 Aug 2026"),
]


def haal(pad):
    with urllib.request.urlopen(API + pad, timeout=60) as r:
        return json.load(r)


def pct(x, plus=True):
    return (f"{x:+.2f}%" if plus else f"{x:.2f}%").replace("+0.00%", "0.00%")


def main():
    homepage = "--uit" not in sys.argv
    uit = W2E / "index.html" if homepage else pathlib.Path(sys.argv[sys.argv.index("--uit") + 1])
    vandaag = datetime.date.today()
    grens = vandaag - datetime.timedelta(days=VERTRAGING_DAGEN)
    weken = []
    for w in haal("weekly-performance")["weeks"]:
        start = datetime.datetime.strptime(w["week_start"], "%d %b %Y").date()
        if start + datetime.timedelta(days=7) <= grens:
            weken.append((start, w["week_label"], float(w["profit_pct"])))
    weken.sort()
    marker = f"<!--logboek-tot:{weken[-1][1]} {weken[-1][0]}-->"
    if homepage and "--forceer" not in sys.argv and uit.exists() and marker in uit.read_text(encoding="utf-8"):
        print(f"logboek al bij tot {weken[-1][1]}; niets herschreven")
        return 0
    reeks = [p for _, _, p in weken]
    raak = sum(p >= DOEL for p in reeks)
    strat = haal("strategy-comparison?days=90")["strategies"]
    ph = haal("portfolio-history")
    open_pct = [u / t * 100 for u, t in zip(ph["unrealized_pnl"], ph["total_value"]) if t]
    ph_van, ph_tot = ph["timestamps"][0][:10], ph["timestamps"][-1][:10]

    hoogste = max(abs(p) for p in reeks) or 1
    rijen = []
    for start, label, p in reversed(weken):
        breed = max(2, round(abs(p) / hoogste * 100))
        kleur = "var(--hit)" if p >= DOEL else ("var(--neg)" if p < 0 else "var(--accent)")
        rijen.append(f'<tr><td>{label}</td><td class="d">{start:%d %b}</td>'
                     f'<td class="bar"><span style="width:{breed}%;background:{kleur}"></span></td>'
                     f'<td class="n">{pct(p)}</td></tr>')
    strat_rijen = "".join(
        f'<tr><td>{html.escape(s["strategy"])}</td><td class="n">{s["total_trades"]}</td>'
        f'<td class="n">{pct(s["roi_pct"])}</td><td class="n">{s["median_hold_hours"]:.0f} h</td></tr>'
        for s in sorted(strat, key=lambda s: -s["total_trades"]))
    lekken = "".join(f'<div class="lek"><h3>{html.escape(k)}</h3><p>{html.escape(t)}</p>'
                     f'<p class="meta">{html.escape(d)}</p></div>' for k, t, d in LEKKEN)
    eerste, laatste = weken[0], weken[-1]

    pagina = f"""<!DOCTYPE html>
<html lang="en">
{marker}
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<title>The Weekly 2% Edge | A live bitcoin bot's honest logbook</title>
<meta name="description" content="What a live BTC-EUR trading bot actually made each week since April 2026, in percentages, and where the edge leaks: fees, rules that backfired, reporting bugs. No signals, no advice.">
<link rel="canonical" href="https://theweekly2pctedge.com/">
<meta property="og:title" content="The Weekly 2% Edge | A live bitcoin bot's honest logbook">
<meta property="og:description" content="Every week of a live BTC-EUR bot in percentages, and where the edge leaks. No signals, no advice.">
<meta property="og:url" content="https://theweekly2pctedge.com/">
<meta property="og:type" content="website">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-CW1KZ258ZV"></script>
<script>window.dataLayer = window.dataLayer || []; function gtag(){{dataLayer.push(arguments);}} gtag('js', new Date()); gtag('config', 'G-CW1KZ258ZV');</script>
<script type="application/ld+json">
{{"@context": "https://schema.org", "@type": "WebSite", "name": "The Weekly 2% Edge", "url": "https://theweekly2pctedge.com/",
 "description": "The public logbook of a live BTC-EUR trading bot, in percentages.",
 "publisher": {{"@type": "Person", "name": "Daniel Haket", "alternateName": "Daan",
  "description": "Former banker in Rotterdam who built and runs the bot.", "sameAs": ["https://www.linkedin.com/in/daniel-haket-8305a33"]}}}}
</script>
<style>
:root {{ --bg:#050b14; --card:#0b121f; --text:#f8fafc; --muted:#94a3b8; --accent:#6366f1; --hit:#22c55e; --neg:#f43f5e; --border:#1e293b; }}
* {{ box-sizing:border-box; margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
body {{ background:var(--bg); color:var(--text); line-height:1.6; -webkit-font-smoothing:antialiased; }}
main {{ max-width:860px; margin:0 auto; padding:3rem 1.25rem 4rem; }}
.kicker {{ font-family:monospace; font-size:.75rem; letter-spacing:.12em; color:var(--accent); text-transform:uppercase; }}
h1 {{ font-size:clamp(1.8rem,4.5vw,2.6rem); line-height:1.15; margin:.6rem 0 1rem; }}
h2 {{ font-size:1.35rem; margin:3rem 0 1rem; }}
h3 {{ font-size:1.02rem; margin-bottom:.35rem; }}
p {{ color:#cbd5e1; margin-bottom:1rem; }}
.lead {{ font-size:1.1rem; }}
.kaarten {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; margin:2rem 0; }}
.kaart {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.1rem 1.2rem; }}
.kaart b {{ display:block; font-size:1.6rem; font-variant-numeric:tabular-nums; }}
.kaart span {{ color:var(--muted); font-size:.85rem; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; font-variant-numeric:tabular-nums; }}
td, th {{ padding:.4rem .5rem; border-bottom:1px solid var(--border); text-align:left; }}
th {{ color:var(--muted); font-weight:500; font-size:.8rem; }}
td.d {{ color:var(--muted); white-space:nowrap; }}
td.n, th.n {{ text-align:right; white-space:nowrap; }}
td.bar {{ width:55%; }}
td.bar span {{ display:block; height:.7rem; border-radius:3px; }}
.lek {{ background:var(--card); border:1px solid var(--border); border-left:3px solid var(--neg); border-radius:0 10px 10px 0; padding:1rem 1.2rem; margin-bottom:1rem; }}
.lek p {{ margin-bottom:.4rem; }}
.meta {{ color:var(--muted); font-size:.8rem; }}
.box {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.2rem 1.4rem; margin:1.5rem 0; }}
.disclaimer {{ font-size:.85rem; color:var(--muted); border-top:1px solid var(--border); padding-top:1.5rem; margin-top:3rem; }}
form {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:.8rem; }}
input {{ flex:1; min-width:200px; padding:.7rem .9rem; border-radius:8px; border:1px solid var(--border); background:#030712; color:var(--text); }}
button {{ padding:.7rem 1.2rem; border-radius:8px; border:0; background:var(--accent); color:#fff; font-weight:600; cursor:pointer; }}
</style>
</head>
<body>
<header style="border-bottom:1px solid var(--border);padding:1.1rem 1.25rem"><a href="/" style="color:var(--text);text-decoration:none;font-weight:700"><span style="color:var(--accent)">&#9679;</span> The Weekly 2% Edge</a></header>
<main>
<p class="kicker">Live bot logbook &middot; updated weekly, one week delayed</p>
<h1>The name promised 2% a week. Here is what the bot actually made.</h1>
<p class="lead">Since April 2026 a bitcoin bot I built has traded BTC-EUR around the clock with real money. This page shows every week it has run, in percentages only, and the places where profit leaked away. I don't sell signals, copy-trading or advice. I publish the measuring tape, not a return promise.</p>
<p>The realistic goal turned out to be <strong>{DOEL}% a week</strong>, not 2%. Measured that way:</p>

<div class="kaarten">
<div class="kaart"><b>{len(reeks)}</b><span>weeks logged ({eerste[1]} to {laatste[1]} 2026)</span></div>
<div class="kaart"><b>{pct(statistics.median(reeks), False)}</b><span>median week (realized)</span></div>
<div class="kaart"><b>{raak} of {len(reeks)}</b><span>weeks at or above {DOEL}%</span></div>
<div class="kaart"><b>{pct(min(reeks))}</b><span>worst week &middot; best {pct(max(reeks))}</span></div>
</div>

<h2>Every week, realized profit as % of the capital in play</h2>
<table>
<tr><th>Week</th><th>Starts</th><th></th><th class="n">Realized</th></tr>
{''.join(rijen)}
</table>
<p class="meta">After exchange fees on both the buy and the sell. Green: at or above the {DOEL}% goal. Red: a losing week. Each week is measured against the capital the bot had in play that week, so deposits don't inflate the percentages.</p>

<h2>What these numbers don't show</h2>
<div class="box">
<p><strong>Realized is not the whole picture.</strong> The bot is built to sell a position only above its buy price, so almost every closed trade is a winner. That is a design choice, not skill. Losses mostly wait in open positions instead of showing up in the weekly figure. The rare forced exits at a loss are included above.</p>
<p>Over the last seven days ({ph_van} to {ph_tot}), the open positions were worth between <strong>{pct(min(open_pct))}</strong> and <strong>{pct(max(open_pct))}</strong> of the account compared with what was paid for them. In a deep bitcoin drop, that number gets much larger before any of it shows up in the weekly figure.</p>
</div>

<h2>Where the edge leaks</h2>
<p>A bot that only ever sells at a profit still loses money in quieter ways. These are the leaks I measured on this bot, each with the date it was measured or fixed.</p>
{lekken}

<h2>Which strategy earns what, last 90 days</h2>
<table>
<tr><th>Strategy</th><th class="n">Closed trades</th><th class="n">Return per trade</th><th class="n">Median hold</th></tr>
{strat_rijen}
</table>
<p class="meta">Return per trade = net profit divided by the amount invested in those trades, after fees, closed trades only.</p>

<h2>How this is measured</h2>
<p>Every figure comes from the bot's own records through its read-only dashboard, the same numbers I look at. This page shows percentages only: no amounts, no account size, no open orders. Weeks appear here one week after they end. The bot runs on Replit and trades on Bitvavo. Data read on {vandaag:%d %b %Y}.</p>

<div class="box">
<h3>One honest email a week</h3>
<p>What changed on the bot, what broke, and what I measured. No tips.</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank"><input type="hidden" name="utm_source" value="theweekly2pctedge"><input type="hidden" name="utm_campaign" value="weekmail"><input type="email" name="email" placeholder="you@example.com" required><button type="submit">Subscribe</button></form>
</div>

<div class="box" id="build-notes">
<h3>The build notes of this bot</h3>
<p>How it is built and guarded: the ladder, the safety checks, the monitoring, and the mistakes above in full detail. It's an engineering document, not a strategy that promises returns. It doesn't exist as a product yet. Leave your email if you'd want it, and I'll only write it if enough people do.</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank" onsubmit="if(window.gtag)gtag('event','bouwnotities_aanmelding')"><input type="hidden" name="utm_source" value="theweekly2pctedge"><input type="hidden" name="utm_campaign" value="bouwnotities"><input type="email" name="email" placeholder="you@example.com" required><button type="submit">I'd want the build notes</button></form>
</div>

<p class="disclaimer">This is a personal logbook, not financial advice and not an offer of any service. Crypto is volatile and you can lose your entire stake. Past weeks say nothing about future weeks. I don't run money for others and don't sell signals. &mdash; Daan, Rotterdam</p>
</main>
</body>
</html>
"""
    uit.write_text(pagina, encoding="utf-8")
    if homepage:
        sm = W2E / "sitemap.xml"
        sm.write_text(re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{vandaag}</lastmod>", sm.read_text(encoding="utf-8"), count=1),
                      encoding="utf-8")
    print(f"{len(reeks)} weken ({eerste[1]}-{laatste[1]}), mediaan {statistics.median(reeks):.2f}%, "
          f"doel geraakt {raak}/{len(reeks)}, open {min(open_pct):.2f}..{max(open_pct):.2f}% -> {uit}")


if __name__ == "__main__":
    sys.exit(main())
