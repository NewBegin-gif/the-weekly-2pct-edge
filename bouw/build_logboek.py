"""Het openbare logboek van de echte bot op theweekly2pctedge.com (Daan, 21 okt 2026: "Doen").

Idee: "verkoop het meetlint, niet de rendementsbelofte". Eén homepage, wekelijks bijgewerkt, uit de
publieke read-only endpoints van het botdashboard (geen databasetoegang nodig):
  /api/weekly-performance   gerealiseerde winst per week, % van het actieve kapitaal
  /api/strategy-comparison  per strategie: rendement per afgeronde ronde, aantal, houdduur
  /api/portfolio-history    gerealiseerd vs. open (unrealized) over de laatste 7 dagen

Regels (Daan): alleen percentages, nooit bedragen of kapitaal; een week vertraagd; geen signalen,
geen advies. De lekken (fees, time-decay, ...) zijn eerdere metingen met hun meetdatum.

Sinds Daans ja (21 okt 2026) is dit de homepage van w2e. Draait dagelijks in dagelijkse_data.py, maar
herschrijft alleen als er een nieuwe week bij komt (door de vertraging: op maandag), anders zou de pagina
elke dag van datum wisselen zonder nieuwe inhoud. Bij elke herschrijving komen mee (zelfde data, zelfde run):
  index.html            de homepage (met de <!--logboek-tot:...--> marker)
  method/index.html     hoe elk getal berekend wordt (lastmod schuift alleen als de tekst verandert)
  404.html              de foutpagina in dezelfde huisstijl
  llms.txt              samenvatting voor taalmodellen, met de actuele cijfers en de datum
  weekly-series.csv     de weekreeks (week, maandag, % gerealiseerd), de Dataset-download
  sitemap.xml           / en /method/ met lastmod
  og-image.png          bouw/og-basis.png met de staven van alle weken erop getekend (stdlib-PNG)
robots.txt en de favicons zijn statisch. Alleen stdlib.
Vertraging (22 okt 2026, besluit na Codex-review): de weekresultaten zijn zeven dagen vertraagd; de open-bandbreedte
en de strategietabel zijn gelezen op de bouwdatum, en dat staat er overal bij.

    python3 bouw/build_logboek.py                    # homepage + bijbehorende bestanden, alleen bij een nieuwe week
    python3 bouw/build_logboek.py --forceer          # altijd herschrijven
    python3 bouw/build_logboek.py --uit <pad.html>   # los concept van de homepage, verder niets
    python3 bouw/build_logboek.py --bron <map>       # lees de drie API-antwoorden uit <map>/*.json (test zonder netwerk);
                                                     # 'data gelezen' = laatste tijdstip in portfolio-history
"""
import csv
import datetime
import html
import io
import json
import pathlib
import re
import statistics
import sys
import urllib.request

W2E = pathlib.Path(__file__).resolve().parent.parent
API = "https://bitcoin-cycle-bot-eu.replit.app/api/"
SITE = "https://theweekly2pctedge.com"
DOEL = 0.5
NAAM_BELOFTE = 2.0
VERTRAGING_DAGEN = 7
GA4 = "G-CW1KZ258ZV"
LINKEDIN = "https://www.linkedin.com/in/daniel-haket-8305a33"

# Gemeten lekken. Alleen percentages; bron = eigen metingen op de bot. 'cijfer' en 'nu' herhalen alleen wat in
# 'uitleg' staat (kop van de kaart), 'iso' is de meetdatum voor <time>.
LEKKEN = [
    dict(kop="Exchange fees took about a fifth of gross profit",
         uitleg="Between late April and early August, fees came to roughly 20% of gross trading profit. The bot now "
                "books the real fee per fill. The exchange charges 0.18% per taker order and 0.09% per maker order at "
                "the bot's volume.",
         datum="measured 5 Aug 2026; fee tiers read 8 Sep 2026", iso="2026-08-05",
         cijfer="~20%", cijfer_uitleg="of gross profit went to fees", nu="Real fee now booked per fill"),
    dict(kop="Lowering the profit target over time gave money away",
         uitleg="A 'time-decay' rule lowered the sell target as a position aged. Of 152 sales it touched over 55 "
                "days, the original target was still reached in 78% of cases (median: 3 hours later). The rule gave "
                "up about 0.33% per trade, so it was switched off.",
         datum="measured 5 Aug 2026", iso="2026-08-05",
         cijfer="0.33%", cijfer_uitleg="given up per trade", nu="Rule switched off"),
    dict(kop="A safety filter froze the buy ladder",
         uitleg="A hard block on buying when RSI was above 70 also stopped the ladder from following the price, so "
                "a later shallow dip caught nothing. It became a taper: smaller orders between RSI 70 and 80, a hard "
                "block only above 80.",
         datum="changed 9 Aug 2026", iso="2026-08-09",
         cijfer="RSI 70", cijfer_uitleg="hard block that froze the ladder", nu="Now a taper; hard block only above 80"),
    dict(kop="One weekly report missed about half of that week's profit",
         uitleg="In one week of the bot's Telegram weekly report, about half of the realized profit was missing. The "
                "report filtered on when a position started instead of when it was sold, so positions spanning two "
                "weeks disappeared. Fixed, and checked against the trade records.",
         datum="fixed 9 Aug 2026", iso="2026-08-09",
         cijfer="~½", cijfer_uitleg="of one week's realized profit missing from the report",
         nu="Fixed and checked against trade records"),
]

TITEL = "The Weekly 2% Edge | A live bitcoin bot's honest logbook"
OMSCHRIJVING = ("A live bitcoin bot's weekly results after fees, in percentages. Realized profit, open positions and "
                "dated mistakes. No signals or advice.")
OG_BEELD = f"{SITE}/og-image.png"
OG_ALT = ("The Weekly 2% Edge: realized weekly profit of a live bitcoin bot in percentages, "
          "drawn against the 0.5% goal and the 2% in the name.")


def haal(pad):
    if "--bron" in sys.argv:
        bestand = pathlib.Path(sys.argv[sys.argv.index("--bron") + 1]) / (pad.split("?")[0] + ".json")
        return json.loads(bestand.read_text(encoding="utf-8"))
    with urllib.request.urlopen(API + pad, timeout=60) as r:
        return json.load(r)


def pct(x, plus=True):
    """Voor in de pagina: echt minteken, altijd twee decimalen."""
    s = (f"{x:+.2f}%" if plus else f"{x:.2f}%").replace("+0.00%", "0.00%")
    return s.replace("-", "−")


def e(s):
    return html.escape(str(s), quote=True)


def kort(d):
    return f"{d.day} {d:%b}"


def lang(d):
    return f"{d.day} {d:%b %Y}"


def schrijf(pad, inhoud):
    """Schrijft alleen als de inhoud anders is; geeft terug of er iets veranderde."""
    pad.parent.mkdir(parents=True, exist_ok=True)
    if pad.exists() and pad.read_text(encoding="utf-8") == inhoud:
        return False
    pad.write_text(inhoud, encoding="utf-8")
    return True


# ---------------------------------------------------------------- huisstijl (gedeeld door alle pagina's)

CSS = """
:root{
  color-scheme:light dark;
  --bg:#f6f3ec; --surface:#fffdf8; --sunk:#efeadf; --ink:#1b1f24; --ink-2:#434a54; --muted:#5f646c;
  --rule:#e2dccd; --rule-2:#cfc7b4; --brass:#7d5e22; --hit:#1f7a52; --below:#3f73b8; --neg:#c2412d;
  --btn:#1b1f24; --btn-ink:#fffdf8; --focus:#3f73b8;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Charter,"Bitstream Charter",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f1318; --surface:#161b22; --sunk:#1c222b; --ink:#ece8df; --ink-2:#c3c6cb; --muted:#9aa1aa;
  --rule:#262d36; --rule-2:#36404b; --brass:#d4ac5e; --hit:#2f9e68; --below:#5b8fd6; --neg:#e0604a;
  --btn:#ece8df; --btn-ink:#0f1318; --focus:#5b8fd6;
}}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:400 1.0625rem/1.65 var(--sans);-webkit-font-smoothing:antialiased;overflow-wrap:break-word}
a{color:inherit;text-decoration-thickness:1px;text-underline-offset:.18em;text-decoration-color:var(--rule-2)}
a:hover{text-decoration-color:currentColor}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px;border-radius:3px}
.skip{position:absolute;left:-999px;top:0;background:var(--surface);padding:.6rem 1rem;z-index:9}
.skip:focus{left:1rem;top:1rem}
.wrap{max-width:1080px;margin:0 auto;padding:0 1rem}
@media (min-width:700px){.wrap{padding:0 2rem}}
.prose{max-width:42rem}
h1,h2,h3{font-family:var(--serif);font-weight:600;color:var(--ink);letter-spacing:-.01em;line-height:1.15;margin:0}
h1{font-size:clamp(2rem,6.2vw,3.4rem);letter-spacing:-.02em}
h2{font-size:clamp(1.5rem,3.6vw,2.1rem);margin-bottom:.75rem}
h3{font-size:1.2rem;margin-bottom:.4rem}
p{margin:0 0 1rem}
strong{font-weight:650}
.kicker{font:600 .75rem/1.4 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--brass);margin:0 0 .9rem}
.muted{color:var(--muted)}
.small{font-size:.875rem}
.num{font-variant-numeric:tabular-nums}

/* kop */
.top{border-bottom:1px solid var(--rule);background:var(--bg)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:1rem;min-height:3.75rem;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:.6rem;text-decoration:none;font:650 1.02rem/1 var(--serif);letter-spacing:-.01em}
.brand svg{flex:none}
.nav{display:flex;gap:1.1rem;font-size:.9rem}
.nav a{text-decoration:none;color:var(--ink-2)}
.nav a:hover,.nav a[aria-current]{color:var(--ink);text-decoration:underline}
@media (max-width:520px){.nav .opt{display:none}}

/* hero */
.hero{padding:2.4rem 0 2.6rem;border-bottom:1px solid var(--rule)}
.hero-grid{display:grid;gap:1.6rem;grid-template-areas:"head" "answer" "lead"}
@media (min-width:900px){.hero{padding:4rem 0 4rem}.hero-grid{grid-template-columns:1.15fr 1fr;column-gap:3.5rem;row-gap:1.4rem;grid-template-areas:"head answer" "lead answer";align-items:start}}
.hero-head{grid-area:head}.hero-lead{grid-area:lead}.answer{grid-area:answer}
.hero-lead p{font-size:1.1rem;color:var(--ink-2);max-width:36rem}
.answer{position:relative;background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1.4rem 1.3rem 1.2rem 1.9rem;
  box-shadow:0 1px 0 var(--rule),0 18px 40px -28px rgba(27,31,36,.35)}
.answer::before{content:"";position:absolute;top:0;bottom:0;left:.85rem;border-left:3px double var(--neg);opacity:.55}
.answer-label{font:600 .75rem/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 .35rem}
.hero-num{font:700 clamp(3.6rem,15vw,5.4rem)/1 var(--sans);letter-spacing:-.04em;margin:0 0 .4rem;color:var(--ink)}
.answer-sub{color:var(--ink-2);margin:0 0 1.1rem}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:0 0 1rem;border-top:1px solid var(--rule)}
.facts div{padding:.7rem .2rem .65rem 0;border-bottom:1px solid var(--rule)}
.facts div:nth-child(odd){padding-right:.8rem;border-right:1px solid var(--rule)}
.facts div:nth-child(even){padding-left:.8rem}
.facts dt{font-size:.8rem;color:var(--muted);line-height:1.3}
.facts dd{margin:.15rem 0 0;font-weight:650;font-size:1.1rem;line-height:1.25}
.facts dd span{font-weight:400;font-size:.85rem;color:var(--muted)}
.answer-note{font-size:.9rem;color:var(--ink-2);margin:0;padding:.75rem .85rem;background:var(--sunk);border-radius:3px}

/* secties */
section{padding:3.2rem 0;border-bottom:1px solid var(--rule)}
@media (min-width:900px){section{padding:4.4rem 0}}
.sec-head{max-width:42rem;margin-bottom:1.6rem}
.sec-head p{color:var(--ink-2)}

/* grafiek */
.chart{background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1rem .6rem .5rem}
@media (min-width:700px){.chart{padding:1.4rem 1.4rem .8rem}}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart .narrow{display:none}
@media (max-width:640px){.chart .wide{display:none}.chart .narrow{display:block}}
.ax{font:11px var(--sans);fill:var(--muted);font-variant-numeric:tabular-nums}
.ax-line{stroke:var(--rule);stroke-width:1}
.zero{stroke:var(--ink-2);stroke-width:1}
.ref{stroke-width:1.5;stroke-dasharray:5 4;fill:none}
.ref-goal{stroke:var(--ink-2)}.ref-name{stroke:var(--brass)}
.ref-lbl{font:600 11px var(--sans);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}
.ref-lbl.goal{fill:var(--ink-2)}.ref-lbl.name{fill:var(--brass)}
.val{font:600 11px var(--sans);fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round;font-variant-numeric:tabular-nums}
.b-hit{fill:var(--hit)}.b-below{fill:var(--below)}.b-neg{fill:var(--neg)}
.wk .hit-area{fill:transparent}
.wk:hover path{opacity:.75}
.legend{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;list-style:none;margin:.9rem 0 0;padding:0 .2rem;font-size:.85rem;color:var(--ink-2)}
.legend li{display:flex;align-items:center;gap:.45rem}
.sw{width:.8rem;height:.8rem;border-radius:2px;display:inline-block;flex:none}
.sw.hit{background:var(--hit)}.sw.below{background:var(--below)}.sw.neg{background:var(--neg)}
.sw.line{height:0;border-top:2px dashed var(--ink-2);border-radius:0;width:1.1rem}
.sw.line.name{border-color:var(--brass)}
.chart-note{margin:1rem 0 0;font-size:.9rem;color:var(--muted);max-width:44rem}

/* tabellen */
details{margin-top:1.2rem;border:1px solid var(--rule);border-radius:4px;background:var(--surface)}
summary{cursor:pointer;padding:.85rem 1rem;font-weight:600;font-size:.95rem}
details[open] summary{border-bottom:1px solid var(--rule)}
.tbl{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.92rem;font-variant-numeric:tabular-nums}
caption{text-align:left;padding:0 0 .6rem;font-size:.85rem;color:var(--muted)}
th,td{padding:.55rem .75rem;text-align:left;border-bottom:1px solid var(--rule);vertical-align:baseline}
thead th{font:600 .72rem/1.3 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--rule-2)}
tbody tr:last-child td{border-bottom:0}
.r{text-align:right;white-space:nowrap}
td.lbl{white-space:nowrap}
code,.code{font-family:var(--mono);font-size:.88em}
.goal-met{font-size:.8rem;color:var(--hit);font-weight:600}
.plain-tbl{background:var(--surface);border:1px solid var(--rule);border-radius:4px}

/* gerealiseerd vs open */
.two{display:grid;gap:1rem}
@media (min-width:760px){.two{grid-template-columns:1fr 1fr;gap:1.25rem}}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1.3rem 1.3rem 1.1rem}
.card p:last-child{margin-bottom:0}
.tag{display:inline-block;font:600 .7rem/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;padding:.35rem .5rem;border-radius:2px;margin-bottom:.8rem}
.tag.in{background:color-mix(in srgb,var(--hit) 16%,transparent);color:var(--ink)}
.tag.out{background:color-mix(in srgb,var(--neg) 14%,transparent);color:var(--ink)}
.card ul{margin:.4rem 0 0;padding-left:1.1rem;color:var(--ink-2)}
.card li{margin-bottom:.3rem}
.range{margin:1.25rem 0 0;background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1.3rem 1.3rem 1.1rem}
.range h3{font-size:1.1rem}
.track{position:relative;height:1.6rem;margin:1.2rem .4rem .3rem}
.track .base{position:absolute;left:0;right:0;top:.6rem;height:.4rem;border-radius:.2rem;background:var(--sunk);border:1px solid var(--rule)}
.track .band{position:absolute;top:.6rem;height:.4rem;border-radius:.2rem;background:var(--neg);opacity:.85}
.track .zero-tick{position:absolute;top:0;height:1.6rem;width:0;border-left:2px solid var(--ink)}
.track .dot{position:absolute;top:.4rem;width:.8rem;height:.8rem;margin-left:-.4rem;border-radius:50%;background:var(--neg);box-shadow:0 0 0 2px var(--surface)}
.range-vals{display:flex;gap:2rem;margin:1rem 0 0;padding-top:.8rem;border-top:1px solid var(--rule)}
.range-vals dt{font-size:.8rem;color:var(--muted)}
.range-vals dd{margin:0;font-weight:650;font-size:1.25rem}
.ticks{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted);margin:0 .3rem;font-variant-numeric:tabular-nums}
.callout{margin-top:1.25rem;border-left:3px solid var(--brass);padding:.2rem 0 .2rem 1rem;max-width:44rem}
.callout p{color:var(--ink-2)}

/* lekken */
.leaks{display:grid;gap:1rem;counter-reset:lek}
@media (min-width:760px){.leaks{grid-template-columns:1fr 1fr;gap:1.25rem}}
.leak{background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1.2rem 1.3rem 1.1rem;display:flex;flex-direction:column}
.leak-top{display:flex;justify-content:space-between;align-items:baseline;gap:.8rem;font:600 .72rem/1.3 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:.9rem}
.leak-top time{letter-spacing:.02em;text-transform:none;text-align:right}
.leak-fig{font:700 2rem/1 var(--sans);letter-spacing:-.02em;color:var(--neg);margin:0 0 .2rem}
.leak-fig-sub{font-size:.85rem;color:var(--muted);margin:0 0 .9rem}
.leak p.txt{color:var(--ink-2);font-size:.97rem}
.leak .now{margin:auto 0 0;padding-top:.75rem;border-top:1px solid var(--rule);font-size:.88rem;font-weight:600}
.leak .now::before{content:"Now: ";font-weight:400;color:var(--muted)}

/* regels */
.rules{list-style:none;padding:0;margin:0;display:grid;gap:.8rem}
@media (min-width:760px){.rules{grid-template-columns:1fr 1fr;gap:1rem 2rem}}
.rules li{padding-left:1.6rem;position:relative;color:var(--ink-2)}
.rules li::before{content:"";position:absolute;left:0;top:.62em;width:.75rem;border-top:2px solid var(--brass)}
.rules strong{color:var(--ink)}

/* auteur + aanmelden */
.author{display:grid;gap:1.25rem}
@media (min-width:760px){.author{grid-template-columns:auto 1fr;gap:2rem;align-items:start}}
.mono-badge{width:4.5rem;height:4.5rem;border-radius:50%;display:grid;place-items:center;background:var(--sunk);border:1px solid var(--rule);font:600 1.5rem/1 var(--serif);color:var(--brass)}
.signup{display:grid;gap:1rem}
@media (min-width:760px){.signup{grid-template-columns:1fr 1fr;gap:1.25rem}}
.box{background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:1.3rem}
.box p{color:var(--ink-2)}
form{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.4rem}
input[type=email]{flex:1 1 12rem;min-width:0;font:inherit;font-size:1rem;padding:.7rem .85rem;border-radius:3px;border:1px solid var(--rule-2);background:var(--bg);color:var(--ink)}
button{font:600 .95rem/1.2 var(--sans);padding:.75rem 1.1rem;border-radius:3px;border:0;background:var(--btn);color:var(--btn-ink);cursor:pointer}
button:hover{opacity:.9}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

/* voet */
.foot{padding:2.4rem 0 3rem;font-size:.88rem;color:var(--muted)}
.foot .disclaimer{max-width:44rem;color:var(--ink-2)}
.foot-links{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;margin:1rem 0 0;padding:0;list-style:none}

/* methode */
.doc{padding:2.6rem 0 3.4rem}
.doc h1{font-size:clamp(2rem,5.5vw,3rem);margin-bottom:1rem}
.doc h2{font-size:1.5rem;margin:2.6rem 0 .7rem}
.doc .lead{font-size:1.15rem;color:var(--ink-2)}
.doc p,.doc li{color:var(--ink-2)}
.doc ul{padding-left:1.2rem}
.doc li{margin-bottom:.4rem}
.formula span{display:block}.formula .in{padding-left:1.5rem}
.formula{font-family:var(--mono);font-size:.92rem;background:var(--surface);border:1px solid var(--rule);border-left:3px solid var(--brass);border-radius:3px;padding:.9rem 1rem;color:var(--ink);overflow-x:auto}
.crumbs{font-size:.85rem;color:var(--muted);margin-bottom:1.2rem}

/* grootboek: folio per sectie, editiestrook */
.folio{font:600 .72rem/1.4 var(--mono);letter-spacing:.12em;color:var(--brass);text-transform:uppercase;display:flex;align-items:center;gap:.7rem;margin:0 0 .9rem}
.folio::after{content:"";flex:1;border-top:1px solid var(--rule-2);max-width:9rem}
.folio b{font-weight:700;color:var(--ink)}
.edition-bar{border-bottom:1px solid var(--rule);background:var(--sunk)}
.edition{display:flex;flex-wrap:wrap;gap:.35rem 1.6rem;padding-top:.8rem;padding-bottom:.8rem;font:.75rem/1.5 var(--mono);color:var(--muted);letter-spacing:.02em}
.edition strong{color:var(--ink);font-weight:600}
.edition a{color:var(--ink-2)}
.hero-num{font-variant-numeric:tabular-nums}
.answer::before{border-left-color:var(--brass)}
.leak-top a{text-decoration:none;color:inherit}
.leak-top a:hover{color:var(--ink)}
.leak .now{border-top-style:dashed;color:var(--ink)}
.leak-fig{font-family:var(--mono);letter-spacing:-.06em}
.chart .narrow .ax,.chart .narrow .ref-lbl{font-size:13px}
.chart .narrow .val{font-size:12px}
@media (max-width:520px){
  .hero{padding:1.6rem 0 2rem}.hero-grid{gap:1.2rem}
  .hero h1{font-size:clamp(1.85rem,8vw,2.15rem)}
  .answer{padding:1.15rem 1rem 1rem 1.6rem}.answer::before{left:.7rem}
  .hero-num{font-size:3.8rem}.answer-sub{margin-bottom:.75rem}
  #strategies table{table-layout:fixed;font-size:.78rem}
  #strategies th,#strategies td{padding:.6rem .35rem;white-space:normal;overflow-wrap:anywhere}
  #strategies th:first-child{width:28%}
  #strategies .code{font-size:1em}
}

@media print{.top .nav,.signup,.skip{display:none}body{background:#fff}}
"""

MERK = ('<svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" '
        'fill="#1b1f24"/><path d="M7 23h18" stroke="#d4ac5e" stroke-width="1.6"/><rect x="9" y="15" width="3.2" '
        'height="8" rx="1" fill="#2f9e68"/><rect x="14.4" y="11" width="3.2" height="12" rx="1" fill="#2f9e68"/>'
        '<rect x="19.8" y="17" width="3.2" height="6" rx="1" fill="#5b8fd6"/><path d="M6 8.5h20" stroke="#d4ac5e" '
        'stroke-width="1.3" stroke-dasharray="2.5 2"/></svg>')


def kop_html(titel, omschrijving, canoniek, extra_head="", robots="index,follow,max-image-preview:large"):
    return f"""<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titel)}</title>
<meta name="description" content="{e(omschrijving)}">
<meta name="robots" content="{robots}">
<meta name="author" content="Daniel Haket">
<meta name="theme-color" content="#f6f3ec" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1318" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
{f'<link rel="canonical" href="{canoniek}">' if canoniek else ''}
{extra_head}<script async src="https://www.googletagmanager.com/gtag/js?id={GA4}"></script>
<script>window.dataLayer = window.dataLayer || []; function gtag(){{dataLayer.push(arguments);}} gtag('js', new Date()); gtag('config', '{GA4}');</script>
<style>{CSS}</style>
</head>"""


def social(titel, omschrijving, url, soort="website"):
    return f"""<meta property="og:type" content="{soort}">
<meta property="og:site_name" content="The Weekly 2% Edge">
<meta property="og:title" content="{e(titel)}">
<meta property="og:description" content="{e(omschrijving)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{OG_BEELD}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(OG_ALT)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(titel)}">
<meta name="twitter:description" content="{e(omschrijving)}">
<meta name="twitter:image" content="{OG_BEELD}">
<meta name="twitter:image:alt" content="{e(OG_ALT)}">
"""


def ld(obj):
    tekst = json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")
    json.loads(tekst)  # moet parsen, anders geen pagina
    return f'<script type="application/ld+json">\n{tekst}\n</script>\n'


def bovenbalk(actief):
    def link(href, tekst, sleutel, klasse=""):
        attr = (' aria-current="page"' if sleutel == actief else "") + (f' class="{klasse}"' if klasse else "")
        return f'<a href="{href}"{attr}>{tekst}</a>'
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
<a class="brand" href="/">{MERK}<span>The Weekly 2% Edge</span></a>
<nav class="nav" aria-label="Main">{link("/#weeks", "Weeks", "weeks", "opt")}{link("/#leaks", "Leaks", "leaks", "opt")}{link("/method/", "Method", "method")}{link("/#follow", "Follow", "follow")}</nav>
</div></header>"""


VOET_DISCLAIMER = ("This is a personal logbook, not financial advice and not an offer of any service. Crypto is "
                   "volatile and you can lose your entire stake. Past weeks say nothing about future weeks. I don't "
                   "run money for others and don't sell signals. &mdash; Daan, Rotterdam")


def voet(regel=""):
    return f"""<footer class="foot"><div class="wrap">
<p class="disclaimer">{VOET_DISCLAIMER}</p>
{f'<p>{regel}</p>' if regel else ''}<ul class="foot-links">
<li><a href="/">The logbook</a></li><li><a href="/method/">Method</a></li><li><a href="/weekly-series.csv">Weekly series (CSV)</a></li><li><a href="{LINKEDIN}" rel="me noopener">Daniel Haket on LinkedIn</a></li>
</ul>
</div></footer>"""


# ---------------------------------------------------------------- grafiek

def balk_pad(x, y0, y1, w):
    """Staaf vanaf de nullijn y0 tot y1, ronde 4px-kop aan de data-kant, vierkant aan de basis."""
    h = abs(y1 - y0)
    r = min(4.0, w / 2, h)
    if y1 <= y0:  # omhoog
        return (f"M{x:.1f},{y0:.1f}V{y1 + r:.1f}Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f}H{x + w - r:.1f}"
                f"Q{x + w:.1f},{y1:.1f} {x + w:.1f},{y1 + r:.1f}V{y0:.1f}Z")
    return (f"M{x:.1f},{y0:.1f}V{y1 - r:.1f}Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f}H{x + w - r:.1f}"
            f"Q{x + w:.1f},{y1:.1f} {x + w:.1f},{y1 - r:.1f}V{y0:.1f}Z")


def klasse(p):
    return "b-hit" if p >= DOEL else ("b-neg" if p < 0 else "b-below")


def grafiek(weken, breedte, hoogte, links, rechts, boven, onder, max_labels, soort, titel_id):
    reeks = [p for _, _, p in weken]
    hi = max(NAAM_BELOFTE, max(reeks)) * 1.06
    lo = min(0.0, min(reeks) * 1.1)
    stap = 0.5 if hi <= 3 else 1.0
    pw, ph = breedte - links - rechts, hoogte - boven - onder
    if lo < 0:  # 18px onder de laagste staaf voor het waardelabel
        lo -= (hi - lo) * 18 / ph

    def y(v):
        return boven + (hi - v) / (hi - lo) * ph

    n = len(weken)
    band = pw / n
    bw = min(24.0, max(3.0, band * 0.68))
    delen = []
    k = -int(-lo // stap) if lo < 0 else 0  # eerste tick op of boven lo
    while k * stap <= hi + 1e-9:
        t = k * stap
        delen.append(f'<line class="ax-line" x1="{links}" x2="{breedte - rechts}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                     f'<text class="ax" x="{links - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{f"{t:.1f}%".replace("-", chr(8722))}</text>')
        k += 1
    # staven
    beste = max(range(n), key=lambda i: reeks[i])
    slechtste = min(range(n), key=lambda i: reeks[i])
    label_bij = {beste, n - 1} if soort == "wide" else {beste}
    if reeks[slechtste] < 0:
        label_bij.add(slechtste)
    stride = max(1, -(-n // max_labels))
    y0 = y(0)
    for i, (start, label, p) in enumerate(weken):
        x = links + i * band + (band - bw) / 2
        y1 = y(p)
        if abs(y1 - y0) < 1.5:
            y1 = y0 - 1.5 if p >= 0 else y0 + 1.5
        jaar = start.isocalendar()[0]
        delen.append(f'<g class="wk"><title>{label} {jaar} (week of {lang(start)}): {pct(p)} realized'
                     f'{" · goal met" if p >= DOEL else ""}</title>'
                     f'<rect class="hit-area" x="{links + i * band:.1f}" y="{boven}" width="{band:.1f}" height="{ph}"/>'
                     f'<path class="{klasse(p)}" d="{balk_pad(x, y0, y1, bw)}"/></g>')
        ty = y1 - 6 if p >= 0 else y1 + 14
        # geen waardelabel dat aan de rechterkant over het label van een referentielijn valt
        botst = (x + bw / 2 + 24 > breedte - rechts
                 and any(abs(ty - 4 - y(v)) < 13 for v in (DOEL, NAAM_BELOFTE)))
        if i in label_bij and not botst:
            delen.append(f'<text class="val" x="{x + bw / 2:.1f}" y="{ty:.1f}" text-anchor="middle">{pct(p)}</text>')
        if (n - 1 - i) % stride == 0 and not (i in label_bij and p < 0):
            delen.append(f'<text class="ax" x="{x + bw / 2:.1f}" y="{hoogte - onder + 18}" text-anchor="middle">{label}</text>')
    delen.append(f'<line class="zero" x1="{links}" x2="{breedte - rechts}" y1="{y0:.1f}" y2="{y0:.1f}"/>')
    # referentielijnen
    for waarde, k, tekst in ((DOEL, "goal", "goal"), (NAAM_BELOFTE, "name", "the name" if rechts > 50 else "name")):
        delen.append(f'<line class="ref ref-{k}" x1="{links}" x2="{breedte - rechts + 4}" y1="{y(waarde):.1f}" y2="{y(waarde):.1f}"/>'
                     f'<text class="ref-lbl {k}" x="{breedte - rechts + 8}" y="{y(waarde) + 4:.1f}">{tekst}</text>')
    eerste, laatste = weken[0], weken[-1]
    beschrijving = (f"Bar chart of realized profit per week, {eerste[1]} to {laatste[1]}, as a percentage of the capital "
                    f"in play. Median {pct(statistics.median(reeks))}, best {pct(max(reeks))}, worst {pct(min(reeks))}. "
                    f"{sum(p >= DOEL for p in reeks)} of {n} weeks reached the {DOEL}% goal; no week came near "
                    f"the {NAAM_BELOFTE:g}% in the name." if max(reeks) < NAAM_BELOFTE else
                    f"Bar chart of realized profit per week, {eerste[1]} to {laatste[1]}, as a percentage of the capital "
                    f"in play. Median {pct(statistics.median(reeks))}, best {pct(max(reeks))}, worst {pct(min(reeks))}.")
    return (f'<svg class="{soort}" viewBox="0 0 {breedte} {hoogte}" role="img" aria-labelledby="{titel_id}-t {titel_id}-d">'
            f'<title id="{titel_id}-t">Realized profit per week, % of capital in play</title>'
            f'<desc id="{titel_id}-d">{e(beschrijving)}</desc>{"".join(delen)}</svg>')


def bereik_html(lo, hi):
    """Horizontale strook: laagste tot hoogste open-resultaat, met de nullijn."""
    schaal = max(1.0, -(-max(abs(lo), abs(hi)) // 1))
    def pos(v):
        return (v + schaal) / (2 * schaal) * 100
    links, rechts = pos(min(lo, hi)), pos(max(lo, hi))
    return f"""<div class="track" aria-hidden="true">
<div class="base"></div><div class="band" style="left:{links:.1f}%;width:{max(.8, rechts - links):.1f}%"></div>
<div class="zero-tick" style="left:50%"></div>
<span class="dot" style="left:{links:.1f}%"></span><span class="dot" style="left:{rechts:.1f}%"></span>
</div>
<div class="ticks" aria-hidden="true"><span>{pct(-schaal).replace(".00", "")}</span><span>0%</span><span>{pct(schaal).replace(".00", "")}</span></div>
<dl class="range-vals"><div><dt>Lowest reading</dt><dd>{pct(lo)}</dd></div><div><dt>Highest reading</dt><dd>{pct(hi)}</dd></div></dl>"""


# ---------------------------------------------------------------- OG-beeld (stdlib: PNG lezen, staven tekenen, schrijven)
# bouw/og-basis.png is het vaste deel (kop, merk, labels 'the name: 2%' / 'goal 0.5%', tijdloze onderregel). De
# staven, stippellijnen en nullijn tekent dit script bij elke herschrijving, zodat het beeld niet veroudert.
OG_BASIS = W2E / "bouw" / "og-basis.png"
OG_X0, OG_X1, OG_NUL, OG_PX = 120, 1030, 521, 98.0  # grafiekvlak; px per procentpunt (0,5% -> y 472, 2% -> y 325)
OG_KLEUR = dict(hit=(31, 122, 82), below=(63, 115, 184), neg=(194, 65, 45), naam=(125, 94, 34), doel=(67, 74, 84),
                nul=(27, 31, 36))


def png_lees(pad):
    import struct
    import zlib
    data = pad.read_bytes()
    pos, w, h, kleur, idat = 8, 0, 0, 0, b""
    while pos < len(data):
        lengte, soort = struct.unpack(">I4s", data[pos:pos + 8])
        stuk = data[pos + 8:pos + 8 + lengte]
        if soort == b"IHDR":
            w, h, diepte, kleur, _, _, interlace = struct.unpack(">IIBBBBB", stuk)
            if diepte != 8 or kleur not in (2, 6) or interlace:
                raise ValueError("og-basis.png moet 8-bit RGB(A) zonder interlace zijn")
        elif soort == b"IDAT":
            idat += stuk
        pos += 12 + lengte
    bpp = 3 if kleur == 2 else 4
    ruw, rij_len = zlib.decompress(idat), w * bpp
    rijen, vorige = [], bytearray(rij_len)
    for r in range(h):
        f, rij = ruw[r * (rij_len + 1)], bytearray(ruw[r * (rij_len + 1) + 1:(r + 1) * (rij_len + 1)])
        for i in range(rij_len):
            a = rij[i - bpp] if i >= bpp else 0
            b, c = vorige[i], (vorige[i - bpp] if i >= bpp else 0)
            if f == 1:
                rij[i] = (rij[i] + a) & 255
            elif f == 2:
                rij[i] = (rij[i] + b) & 255
            elif f == 3:
                rij[i] = (rij[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                rij[i] = (rij[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        vorige = rij  # de ontfilterde rij, nog met alfa
        rijen.append(rij if bpp == 3 else bytearray(v for k, v in enumerate(rij) if k % 4 != 3))  # alfa weg
    return w, h, rijen


def og_beeld(weken):
    """Teken de staven op de basis en geef de PNG-bytes terug (of None als de basis ontbreekt)."""
    import struct
    import zlib
    if not OG_BASIS.exists():
        return None
    w, h, px = png_lees(OG_BASIS)

    def zet(x0, y0, x1, y1, kleur):
        x0, x1 = max(0, int(round(x0))), min(w, int(round(x1)))
        for y in range(max(0, int(round(y0))), min(h, int(round(y1)))):
            px[y][x0 * 3:x1 * 3] = bytes(kleur) * (x1 - x0)

    def y(v):
        return OG_NUL - max(-0.4, min(2.6, v)) * OG_PX

    for waarde, kleur, streep in ((NAAM_BELOFTE, OG_KLEUR["naam"], 8), (DOEL, OG_KLEUR["doel"], 8)):
        x = OG_X0
        while x < OG_X1:
            zet(x, y(waarde) - 1, min(x + streep, OG_X1), y(waarde) + 1, kleur)
            x += streep + 6
    band = (OG_X1 - OG_X0) / len(weken)
    bw = min(24.0, band * 0.62)
    for i, (_, _, p) in enumerate(weken):
        x = OG_X0 + i * band + (band - bw) / 2
        kleur = OG_KLEUR["hit" if p >= DOEL else ("neg" if p < 0 else "below")]
        boven, onder = (y(p), OG_NUL) if p >= 0 else (OG_NUL, y(p))
        if onder - boven < 2:
            boven, onder = (OG_NUL - 2, OG_NUL) if p >= 0 else (OG_NUL, OG_NUL + 2)
        zet(x, boven, x + bw, onder, kleur)
    zet(OG_X0, OG_NUL - 1, OG_X1, OG_NUL + 1, OG_KLEUR["nul"])
    ruw = b"".join(b"\x00" + bytes(r) for r in px)

    def stuk(soort, inhoud):
        return struct.pack(">I", len(inhoud)) + soort + inhoud + struct.pack(">I", zlib.crc32(soort + inhoud))
    return (b"\x89PNG\r\n\x1a\n" + stuk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + stuk(b"IDAT", zlib.compress(ruw, 9)) + stuk(b"IEND", b""))


# ---------------------------------------------------------------- pagina's

def csv_tekst(weken):
    uit = io.StringIO()
    w = csv.writer(uit, lineterminator="\n")
    w.writerow(["week", "week_start_monday", "realized_pct_of_capital_in_play"])
    for start, label, p in weken:
        w.writerow([f"{start.isocalendar()[0]}-{label}", start.isoformat(), f"{p:.2f}"])
    return uit.getvalue()


def persoon():
    return {"@type": "Person", "@id": f"{SITE}/#daan", "name": "Daniel Haket", "alternateName": "Daan",
            "description": "Former banker (23 years in international finance) in Rotterdam who built and runs the bot.",
            "address": {"@type": "PostalAddress", "addressLocality": "Rotterdam", "addressCountry": "NL"},
            "sameAs": [LINKEDIN]}


def homepage(c):
    weken, reeks = c["weken"], c["reeks"]
    eerste, laatste = weken[0], weken[-1]
    periode = c["periode"]
    n = len(reeks)
    verlies = [p for p in reeks if p < 0]
    verlies_tekst = ("none" if not verlies else f"{len(verlies)}")
    wide = grafiek(weken, 960, 340, 46, 70, 22, 34, 13, "wide", "cw")
    narrow = grafiek(weken, 360, 260, 42, 42, 22, 32, 6, "narrow", "cn")

    tabel = "".join(
        f'<tr><td class="lbl">{label} {start.isocalendar()[0]}</td><td><time datetime="{start}">{kort(start)}</time></td>'
        f'<td class="r">{pct(p)}</td><td class="r">{"<span class=goal-met>goal met</span>" if p >= DOEL else ("loss" if p < 0 else "")}</td></tr>'
        for start, label, p in reversed(weken))
    strat_rijen = "".join(
        f'<tr><td><span class="code">{e(s["strategy"])}</span></td><td class="r">{int(s["total_trades"])}</td>'
        f'<td class="r">{pct(float(s["roi_pct"]))}</td><td class="r">{float(s["median_hold_hours"]):.0f} h</td></tr>'
        for s in sorted(c["strat"], key=lambda s: -s["total_trades"]))
    lekken = "".join(
        f'<article class="leak" id="leak-{i}"><div class="leak-top"><a href="#leak-{i}" aria-label="Link to leak {i}">Leak {i}</a><time datetime="{l["iso"]}">{e(l["datum"])}</time></div>'
        f'<p class="leak-fig">{e(l["cijfer"])}</p><p class="leak-fig-sub">{e(l["cijfer_uitleg"])}</p>'
        f'<h3>{e(l["kop"])}</h3><p class="txt">{e(l["uitleg"])}</p><p class="now">{e(l["nu"])}</p></article>'
        for i, l in enumerate(LEKKEN, 1))

    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": f"{SITE}/#website", "name": "The Weekly 2% Edge", "url": f"{SITE}/",
         "inLanguage": "en", "description": "The public logbook of a live BTC-EUR trading bot, in percentages.",
         "publisher": {"@id": f"{SITE}/#daan"}, "author": {"@id": f"{SITE}/#daan"}},
        persoon(),
        {"@type": "WebPage", "@id": f"{SITE}/#webpage", "url": f"{SITE}/", "name": TITEL, "description": OMSCHRIJVING,
         "isPartOf": {"@id": f"{SITE}/#website"}, "about": {"@id": f"{SITE}/#weekly-series"},
         "author": {"@id": f"{SITE}/#daan"}, "inLanguage": "en", "dateModified": c["gelezen"].isoformat(),
         "primaryImageOfPage": {"@type": "ImageObject", "url": OG_BEELD, "width": 1200, "height": 630}},
        {"@type": "Dataset", "@id": f"{SITE}/#weekly-series", "name": "Weekly realized profit of a live BTC-EUR trading bot",
         "description": (f"Realized profit per calendar week (Monday to Sunday) of a live BTC-EUR trading bot on Bitvavo, "
                         f"as a percentage of the capital the bot had in play that week, after exchange fees on both "
                         f"the buy and the sell, rare forced loss sales included. Percentages only, no amounts. Each "
                         f"week is published one week after it ends. Covers {periode}."),
         "url": f"{SITE}/", "creator": {"@id": f"{SITE}/#daan"}, "isAccessibleForFree": True,
         "temporalCoverage": f"{eerste[0].isoformat()}/{(laatste[0] + datetime.timedelta(days=6)).isoformat()}",
         "dateModified": c["gelezen"].isoformat(),
         "keywords": ["bitcoin", "BTC-EUR", "trading bot", "realized profit", "weekly returns", "trading fees"],
         "measurementTechnique": "Realized profit of positions sold in the week, after fees on buy and sell, divided by the capital in play that week.",
         "variableMeasured": {"@type": "PropertyValue", "name": "Realized weekly profit", "unitText": "percent of capital in play"},
         "distribution": {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE}/weekly-series.csv"}},
    ]}

    head = kop_html(TITEL, OMSCHRIJVING, f"{SITE}/", social(TITEL, OMSCHRIJVING, f"{SITE}/") + ld(graph))
    return f"""<!DOCTYPE html>
<html lang="en">
{c["marker"]}
{head}
<body>
{bovenbalk("logbook")}
<main id="main">

<div class="hero"><div class="wrap hero-grid">
<div class="hero-head">
<p class="kicker">Live bot logbook &middot; {e(periode)} &middot; weeks published 7 days late</p>
<h1>The name promised 2% a week. Here is what the bot actually made.</h1>
</div>
<aside class="answer" aria-label="The short answer">
<p class="answer-label">Median week &middot; realized, after fees</p>
<p class="hero-num">{pct(c["mediaan"])}</p>
<p class="answer-sub">of the capital in play, over {n} weeks ({e(periode)}). The realistic goal is {DOEL}% a week.</p>
<dl class="facts">
<div><dt>Goal of {DOEL}% reached</dt><dd>{c["raak"]} <span>of {n} weeks</span></dd></div>
<div><dt>Average week</dt><dd>{pct(c["gemiddeld"])}</dd></div>
<div><dt>Best week</dt><dd>{pct(max(reeks))}</dd></div>
<div><dt>Losing weeks</dt><dd>{verlies_tekst}{f' <span>worst {pct(min(reeks))}</span>' if verlies else ''}</dd></div>
</dl>
<p class="answer-note">Not in these figures: positions the bot still holds. Over the last seven days they stood between <strong>{pct(c["open_lo"])}</strong> and <strong>{pct(c["open_hi"])}</strong> of the account. <a href="#realized-vs-open">Why that matters</a></p>
</aside>
<div class="hero-lead">
<p>Since April 2026 a bitcoin bot I built has traded BTC-EUR around the clock with real money. This page shows every week it has run, in percentages only, and the places where profit leaked away.</p>
<p>I don't sell signals, copy-trading or advice. I publish the measuring tape, not a return promise.</p>
</div>
</div></div>
<div class="edition-bar"><div class="wrap edition">
<span>Ledger through <strong>{e(laatste[1])} {laatste[0].isocalendar()[0]}</strong> (week of {lang(laatste[0])})</span>
<span>Data read <time datetime="{c["gelezen"].isoformat()}">{lang(c["gelezen"])}</time></span>
<a href="/method/">Read the method</a>
</div></div>

<section id="weeks"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>01</b> Weekly ledger</p>
<h2>Every week, realized profit as % of the capital in play</h2>
<p>After exchange fees on both the buy and the sell, rare forced loss sales included. Each week is measured against the capital the bot had in play that week, so deposits don't inflate the percentages.</p>
</div>
<figure class="chart" style="margin:0">
{wide}
{narrow}
<ul class="legend" aria-label="Legend">
<li><span class="sw hit"></span>At or above the {DOEL}% goal</li>
<li><span class="sw below"></span>Positive, below the goal</li>
<li><span class="sw neg"></span>Losing week</li>
<li><span class="sw line"></span>Goal, {DOEL}%</li>
<li><span class="sw line name"></span>The name, {NAAM_BELOFTE:g}%</li>
</ul>
<figcaption class="chart-note">{n} weeks, {e(periode)}. The newest week shown ended at least seven days before this page was built. Hover a bar for its value, or open the table.</figcaption>
</figure>
<details>
<summary>All {n} weeks as a table</summary>
<div class="tbl"><table>
<caption class="sr">Realized profit per week, newest first</caption>
<thead><tr><th scope="col">Week</th><th scope="col">Starts</th><th scope="col" class="r">Realized</th><th scope="col" class="r"><span class="sr">Status</span></th></tr></thead>
<tbody>{tabel}</tbody>
</table></div>
</details>
<p class="small muted" style="margin-top:.9rem">The same series as a file: <a href="/weekly-series.csv">weekly-series.csv</a> (week, Monday it starts, % realized).</p>
</div></section>

<section id="realized-vs-open"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>02</b> Open exposure</p>
<h2>Realized vs. open: the part most bot results leave out</h2>
<p>Every weekly figure above is <em>realized</em>: profit that was locked in by selling. The bitcoin the bot still holds is <em>open</em>, and it is not in those figures.</p>
</div>
<div class="two">
<div class="card">
<span class="tag in">In the weekly figure</span>
<h3>Realized</h3>
<p>A position counts the moment it is sold, in the week of the sale.</p>
<ul><li>Fees on the buy and the sell are already taken off.</li><li>The rare forced exits at a loss are included.</li><li>Once it's in, it doesn't change.</li></ul>
</div>
<div class="card">
<span class="tag out">Not in the weekly figure</span>
<h3>Open</h3>
<p>Bitcoin bought but not yet sold. Its value moves with the price, every minute.</p>
<ul><li>Nothing is locked in until it's sold.</li><li>A falling price shows up here first.</li><li>It reaches the weekly figure only when sold.</li></ul>
</div>
</div>
<div class="range">
<h3>Open positions, last seven days</h3>
<p class="small muted" style="margin:0">{kort(c["ph_van"])} to {lang(c["ph_tot"])}: what the open positions were worth compared with what was paid for them, as % of the account. Lowest and highest reading.</p>
{bereik_html(c["open_lo"], c["open_hi"])}
</div>
<div class="callout">
<p><strong>Why almost every closed trade is a winner.</strong> The bot is built to sell a position only above its buy price. That is a design choice, not skill. Losses mostly wait in open positions instead of showing up in the weekly figure. In a deep bitcoin drop, the open number gets much larger before any of it shows up in the weekly figure.</p>
</div>
</div></section>

<section id="leaks"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>03</b> Measured leaks</p>
<h2>Where the edge leaks</h2>
<p>A bot that only ever sells at a profit still loses money in quieter ways. These are the leaks I measured on this bot, each with the date it was measured or fixed.</p>
</div>
<div class="leaks">{lekken}</div>
</div></section>

<section id="strategies"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>04</b> Strategy ledger</p>
<h2>Which strategy earns what, last 90 days</h2>
<p>The bot runs several strategies side by side. Names as the bot logs them; the 90 days run up to {lang(c["gelezen"])}.</p>
</div>
<div class="tbl plain-tbl"><table>
<thead><tr><th scope="col">Strategy</th><th scope="col" class="r">Closed trades</th><th scope="col" class="r">Return per trade</th><th scope="col" class="r">Median hold</th></tr></thead>
<tbody>{strat_rijen}</tbody>
</table></div>
<p class="chart-note">Return per trade = net profit divided by the amount invested in those trades, after fees, closed trades only. It is not a weekly return: a trade can be open for days.</p>
</div></section>

<section id="rules"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>05</b> Method</p>
<h2>The rules of this logbook</h2>
<p>Every figure comes from the bot's own records through its read-only dashboard, the same numbers I look at. A script builds the weekly series and summaries from the dashboard; the dated leak measurements and reference goals are maintained separately. <a href="/method/">How each number is computed</a>.</p>
</div>
<ul class="rules">
<li><strong>Percentages only.</strong> No amounts, no account size, no order details.</li>
<li><strong>Weeks one week delayed.</strong> A week's result appears here seven days after it ends. The open-position range and the strategy table are read on the build date.</li>
<li><strong>Fees on both sides.</strong> Every figure is after the exchange fee on the buy and on the sell.</li>
<li><strong>Loss sales count.</strong> The rare forced exits at a loss are in the weekly figures.</li>
<li><strong>Open positions shown next to it.</strong> Realized profit is never presented as the whole picture.</li>
<li><strong>No signals, no advice, no copy-trading.</strong> This is a logbook, not a service.</li>
</ul>
<p class="small muted" style="margin-top:1.4rem">The bot runs on Replit and trades on Bitvavo.</p>
</div></section>

<section id="about"><div class="wrap author">
<div class="mono-badge" aria-hidden="true">DH</div>
<div class="prose">
<h2>Who keeps this logbook</h2>
<p>I'm Daan (Daniel Haket), a former banker: 23 years in international finance. I live in Rotterdam. I built this bot with Replit's AI agent, and it has traded BTC-EUR on Bitvavo with real money since April 2026.</p>
<p>The name promised 2% a week. This page is the measuring tape: what the bot really does, week by week, including the parts that went wrong. <a href="{LINKEDIN}" rel="me noopener">LinkedIn</a></p>
</div>
</div></section>

<section id="follow" style="border-bottom:0"><div class="wrap">
<div class="sec-head"><h2>Follow the logbook</h2></div>
<div class="signup">
<div class="box">
<h3>One honest email a week</h3>
<p>What changed on the bot, what broke, and what I measured. No tips.</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank"><input type="hidden" name="utm_source" value="theweekly2pctedge"><input type="hidden" name="utm_campaign" value="weekmail"><label class="sr" for="mail-week">Email address</label><input id="mail-week" type="email" name="email" placeholder="you@example.com" autocomplete="email" required><button type="submit">Subscribe</button></form>
</div>
<div class="box" id="build-notes">
<h3>The build notes of this bot</h3>
<p>How it is built and guarded: the ladder, the safety checks, the monitoring, and the mistakes above in full detail. It's an engineering document, not a strategy that promises returns. It doesn't exist as a product yet. Leave your email if you'd want it, and I'll only write it if enough people do.</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank" onsubmit="if(window.gtag)gtag('event','bouwnotities_aanmelding')"><input type="hidden" name="utm_source" value="theweekly2pctedge"><input type="hidden" name="utm_campaign" value="bouwnotities"><label class="sr" for="mail-notes">Email address</label><input id="mail-notes" type="email" name="email" placeholder="you@example.com" autocomplete="email" required><button type="submit">I'd want the build notes</button></form>
</div>
</div>
</div></section>

</main>
{voet(f"Weeks {e(periode)} &middot; data read on {lang(c['gelezen'])} &middot; a new week is added seven days after it ends.")}
</body>
</html>
"""


def methode(c):
    url = f"{SITE}/method/"
    titel = "Method: how every number is computed | The Weekly 2% Edge"
    omschr = ("How this bitcoin bot logbook measures weekly profit, fees, open positions and loss sales, with a "
              "seven-day delay for weekly results.")
    fee_lek = LEKKEN[0]
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "TechArticle", "@id": f"{url}#article", "headline": "How every number in the logbook is computed",
         "description": omschr, "url": url, "mainEntityOfPage": url, "inLanguage": "en",
         "author": {"@id": f"{SITE}/#daan"}, "publisher": {"@id": f"{SITE}/#daan"},
         "isPartOf": {"@id": f"{SITE}/#website"}, "about": {"@id": f"{SITE}/#weekly-series"}, "image": OG_BEELD},
        persoon(),
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "The logbook", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Method", "item": url}]},
    ]}
    head = kop_html(titel, omschr, url, social(titel, omschr, url, "article") + ld(graph))
    return f"""<!DOCTYPE html>
<html lang="en">
{head}
<body>
{bovenbalk("method")}
<main id="main" class="doc"><div class="wrap"><div class="prose">
<nav class="crumbs" aria-label="Breadcrumb"><a href="/">The logbook</a> &rsaquo; Method</nav>
<p class="kicker">Method</p>
<h1>How every number on the logbook is computed</h1>
<p class="lead">The logbook shows one thing per week: how much profit the bot locked in, as a percentage of the money it had in play. This page explains exactly what goes into that number, what stays out, and why it is published a week late.</p>

<h2>The weekly figure</h2>
<div class="formula"><span>weekly % =</span><span class="in">realized profit of all positions sold that week, after fees</span><span class="in">&divide; capital the bot had in play that week</span><span class="in">&times; 100</span></div>
<ul>
<li><strong>A week</strong> runs Monday to Sunday and carries its ISO week number (W17, W18, &hellip;).</li>
<li><strong>A position counts in the week it is sold</strong>, not the week it was opened. Until 9 Aug 2026 the report filtered on the start of a position, so positions spanning two weeks went missing; that was fixed and checked against the trade records (leak 4 on the logbook).</li>
<li><strong>The divisor is the capital the bot had in play that week</strong>, so deposits don't inflate the percentages.</li>
</ul>

<h2>Fees on both sides</h2>
<p>Every trade pays the exchange twice: once on the buy, once on the sell. Both are taken off before a trade counts as profit. The bot books the real fee per fill. At the bot's volume, the exchange charges 0.18% per taker order and 0.09% per maker order ({e(fee_lek["datum"])}).</p>
<p>Fees matter more than they look: between late April and early August they came to roughly 20% of gross trading profit (leak 1).</p>

<h2>Loss sales are included</h2>
<p>The bot is built to sell a position only above its buy price, so almost every closed trade is a winner. That is a design choice, not skill. The rare forced exits at a loss are part of the weekly figure, the same as any other sale.</p>

<h2>Realized vs. open</h2>
<p>Because losing positions are usually held rather than sold, the weekly figure alone would flatter the bot. So the logbook shows the open side next to it: for each reading over the seven days before the page is built, the unrealized result of the positions still held (what they're worth minus what was paid) as a percentage of the total account value. The lowest and highest reading are shown.</p>
<p>Unlike the weekly figures, this range is not a week old: it covers the seven days up to the build, so a drop in open positions is visible before it can reach any weekly figure. The same goes for the strategy table below, which covers the 90 days up to the build.</p>

<h2>The one-week delay</h2>
<p>A week's result appears on the logbook {VERTRAGING_DAGEN} days after it ends. The delay applies to the weekly results; the open-position range and the strategy table are read on the build date, which the page states. The page is checked daily, but it is only rebuilt when a new week becomes eligible, so the date on it changes only when there is something new. The weekly figures are a record of finished weeks, not a live feed.</p>

<h2>The goal line and the name</h2>
<p>The name promised {NAAM_BELOFTE:g}% a week. Measured honestly, the realistic goal turned out to be {DOEL}% a week. The chart draws both lines, so every week can be read against the goal and against the name.</p>

<h2>The strategy table</h2>
<p>The bot runs several strategies side by side. For each one, over the last 90 days: the number of closed trades, the median time a position was held, and the return per trade, which is net profit divided by the amount invested in those trades, after fees, closed trades only. That is not a weekly return.</p>

<h2>The leaks</h2>
<p>The {len(LEKKEN)} leaks on the logbook are measurements I made on this bot, each with the date it was measured or changed. They are not updated weekly; a new leak is added when one is measured.</p>

<h2>What is never shown</h2>
<ul>
<li>Amounts in euros, the account size, or how much is in play.</li>
<li>Order sizes, open orders, or anything that could be read as a signal.</li>
<li>Advice, predictions, or a return anyone should expect.</li>
</ul>

<h2>Where the data comes from</h2>
<p>All figures come from the bot's own records through its read-only dashboard, the same numbers I look at. The bot runs on Replit and trades on Bitvavo. A script builds the weekly series and summaries from the dashboard; the dated leak measurements and reference goals are maintained separately. The weekly series is also available as a file: <a href="/weekly-series.csv">weekly-series.csv</a>.</p>
<p><a href="/">&larr; Back to the logbook</a></p>
</div></div></main>
{voet()}
</body>
</html>
"""


def pagina_404():
    titel = "Page not found | The Weekly 2% Edge"
    return f"""<!DOCTYPE html>
<html lang="en">
{kop_html(titel, "This page doesn't exist on The Weekly 2% Edge.", "", robots="noindex")}
<body>
{bovenbalk("")}
<main id="main" class="doc"><div class="wrap"><div class="prose">
<p class="kicker">Error 404</p>
<h1>This page doesn't exist (anymore)</h1>
<p class="lead">The Weekly 2% Edge used to carry short tool summaries. Those are gone: this site is now the public logbook of a live bitcoin bot, in percentages.</p>
<ul>
<li><a href="/">The logbook</a>: every week the bot has run, the open positions, and the leaks.</li>
<li><a href="/method/">Method</a>: how each number is computed.</li>
</ul>
</div></div></main>
{voet()}
</body>
</html>
"""


def llms(c):
    weken, reeks = c["weken"], c["reeks"]
    laatste = weken[-1]
    naam = sum(p >= NAAM_BELOFTE for p in reeks)
    naam_tekst = (f"no week reached the {NAAM_BELOFTE:g}% in the name" if not naam else
                  f"{naam} of {len(reeks)} weeks reached the {NAAM_BELOFTE:g}% in the name")
    return f"""# The Weekly 2% Edge

> The public logbook of a live BTC-EUR trading bot: realized profit per week as a percentage of the capital in play (after fees on the buy and the sell, rare forced loss sales included, published one week late), the open positions next to it, and the measured places where profit leaked away. Percentages only; no signals, no advice. Data read on {c["gelezen"].isoformat()}.

The site is written and run by Daan (Daniel Haket), a Dutch former banker (23 years in international finance) in Rotterdam, the Netherlands. He built the bot with Replit's AI agent; it runs on Replit and has traded BTC-EUR on Bitvavo with real money since April 2026. The name promised 2% a week; the site is the measuring tape, not a return promise.

## Key pages
- [The logbook]({SITE}/): every week since {weken[0][1]} {weken[0][0].isocalendar()[0]} in a chart and table, realized vs. open positions, the {len(LEKKEN)} measured leaks, and returns per strategy over the last 90 days
- [Method]({SITE}/method/): how every number is computed, what is included and what is never shown
- [Weekly series (CSV)]({SITE}/weekly-series.csv): week, Monday it starts, realized % of capital in play

## Current figures ({c["periode"]}, {len(reeks)} weeks)
- Median week: {pct(c["mediaan"]).replace(chr(8722), "-")} realized; average week {pct(c["gemiddeld"]).replace(chr(8722), "-")}
- Goal of {DOEL}% a week reached in {c["raak"]} of {len(reeks)} weeks; {naam_tekst}
- Best week {pct(max(reeks)).replace(chr(8722), "-")}, worst week {pct(min(reeks)).replace(chr(8722), "-")}
- Open positions over {c["ph_van"]} to {c["ph_tot"]} (not delayed): between {pct(c["open_lo"]).replace(chr(8722), "-")} and {pct(c["open_hi"]).replace(chr(8722), "-")} of the account versus what was paid

## Method in short
- Weekly figure = realized profit of positions sold that week (Monday to Sunday), after exchange fees on both sides, divided by the capital in play that week
- Positions count in the week they are sold; rare forced loss sales are included
- Open (unrealized) positions are shown separately because the bot normally only sells above its buy price
- Return per trade (strategy table) = net profit divided by the amount invested in those trades, after fees, closed trades only

## Rules
- Percentages only: never euro amounts, account size or order details
- Weekly results one week delayed: a week appears seven days after it ends
- No signals, no advice, no copy-trading; not an offer of any service
- Past weeks say nothing about future weeks; crypto is volatile and you can lose your entire stake

## Data freshness
- Latest week shown: {laatste[1]} {laatste[0].isocalendar()[0]} (week starting {laatste[0].isoformat()})
- The page is checked daily and rebuilt only when a new week becomes eligible; this file is regenerated in the same run
- The weekly series and summaries come from the dashboard at build time; leak measurements retain their stated measurement dates
- Weekly results are delayed seven days; the open-position range and the strategy table are current as of the build date

## Contact
- [Daniel Haket on LinkedIn]({LINKEDIN})
"""


def sitemap(lastmod):
    regels = "".join(f"  <url><loc>{SITE}{pad}</loc><lastmod>{d}</lastmod></url>\n" for pad, d in lastmod)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{regels}</urlset>\n'


def main():
    is_home = "--uit" not in sys.argv
    uit = W2E / "index.html" if is_home else pathlib.Path(sys.argv[sys.argv.index("--uit") + 1])
    vandaag = datetime.date.today()
    ph = haal("portfolio-history")
    if "--bron" in sys.argv:  # test zonder netwerk: 'gelezen' is het moment van de laatste meting
        vandaag = datetime.date.fromisoformat(ph["timestamps"][-1][:10])
    grens = vandaag - datetime.timedelta(days=VERTRAGING_DAGEN)
    weken = []
    for w in haal("weekly-performance")["weeks"]:
        start = datetime.datetime.strptime(w["week_start"], "%d %b %Y").date()
        if start + datetime.timedelta(days=7) <= grens:
            weken.append((start, w["week_label"], float(w["profit_pct"])))
    weken.sort()
    marker = f"<!--logboek-tot:{weken[-1][1]} {weken[-1][0]}-->"
    if is_home and "--forceer" not in sys.argv and uit.exists() and marker in uit.read_text(encoding="utf-8"):
        print(f"logboek al bij tot {weken[-1][1]}; niets herschreven")
        return 0
    reeks = [p for _, _, p in weken]
    open_pct = [u / t * 100 for u, t in zip(ph["unrealized_pnl"], ph["total_value"]) if t]
    eerste, laatste = weken[0], weken[-1]
    j0, j1 = eerste[0].isocalendar()[0], laatste[0].isocalendar()[0]
    c = dict(
        weken=weken, reeks=reeks, marker=marker, gelezen=vandaag,
        periode=f"{eerste[1]} to {laatste[1]} {j1}" if j0 == j1 else f"{eerste[1]} {j0} to {laatste[1]} {j1}",
        mediaan=statistics.median(reeks), gemiddeld=statistics.fmean(reeks), raak=sum(p >= DOEL for p in reeks),
        strat=haal("strategy-comparison?days=90")["strategies"],
        open_lo=min(open_pct), open_hi=max(open_pct),
        ph_van=datetime.date.fromisoformat(ph["timestamps"][0][:10]),
        ph_tot=datetime.date.fromisoformat(ph["timestamps"][-1][:10]),
    )
    pagina = homepage(c)
    for blok in re.findall(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S):
        json.loads(blok)
    uit.write_text(pagina, encoding="utf-8")
    if is_home:
        oud = {}
        sm = W2E / "sitemap.xml"
        if sm.exists():
            oud = dict(re.findall(r"<loc>" + re.escape(SITE) + r"([^<]*)</loc><lastmod>([^<]*)</lastmod>",
                                  sm.read_text(encoding="utf-8")))
        methode_nieuw = schrijf(W2E / "method" / "index.html", methode(c))
        schrijf(W2E / "404.html", pagina_404())
        schrijf(W2E / "llms.txt", llms(c))
        schrijf(W2E / "weekly-series.csv", csv_tekst(weken))
        og = og_beeld(weken)
        if og and (not (W2E / "og-image.png").exists() or (W2E / "og-image.png").read_bytes() != og):
            (W2E / "og-image.png").write_bytes(og)
        schrijf(sm, sitemap([("/", vandaag), ("/method/", vandaag if methode_nieuw or "/method/" not in oud else oud["/method/"])]))
    print(f"{len(reeks)} weken ({eerste[1]}-{laatste[1]}), mediaan {c['mediaan']:.2f}%, "
          f"doel geraakt {c['raak']}/{len(reeks)}, open {c['open_lo']:.2f}..{c['open_hi']:.2f}% -> {uit}")


if __name__ == "__main__":
    sys.exit(main())
