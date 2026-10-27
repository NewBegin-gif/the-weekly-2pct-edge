"""Het dashboard van de bot als inline SVG + tabellen, in het Engels en Nederlands (Daan, 27 okt 2026).

Alles komt uit w2e_data.momentopname(): relatief (procenten) of als BTC-koers, en op of vóór T (minstens 24 uur oud).
BTC-koersen staan altijd in een element met class "px"; de uitvoercontrole in build_logboek.py
(geen_bedragen) haalt alleen die weg voordat hij naar eurobedragen zoekt. Een bedrag zonder die class laat de bouw
stoppen. Geen JavaScript: tooltips zijn SVG-<title>, elke grafiek heeft een tabel ernaast.
"""
import math
import statistics

import build_logboek as B

MAANDEN_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


# ---------------------------------------------------------------- opmaak per taal

def f_pct(x, taal="en", plus=True, dec=2):
    if x is None:
        return "–"
    s = f"{x:+.{dec}f}%" if plus else f"{x:.{dec}f}%"
    if plus and abs(x) < 0.5 * 10 ** -dec:
        s = f"{0:.{dec}f}%"
    if taal == "nl":
        s = s.replace(".", ",")
    return s.replace("-", "−")


def f_getal(x, taal="en", dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".") if taal == "nl" else s


def f_px(p, taal="en"):
    """BTC-koers als tekst (zonder opmaak-element); de aanroeper zet hem in class 'px'."""
    return f"€{f_getal(p, taal)}" if taal == "en" else f"€ {f_getal(p, taal)}"


def px(p, taal="en"):
    return f'<span class="px">{f_px(p, taal)}</span>'


def d_kort(d, taal="en"):
    return f"{d.day} {MAANDEN_NL[d.month - 1]}" if taal == "nl" else f"{d.day} {d:%b}"


def d_lang(d, taal="en"):
    return f"{d_kort(d, taal)} {d.year}"


def d_tijd(t, taal="en"):
    return f"{d_lang(t, taal)}, {t:%H:%M} UTC"


L = {
    "en": dict(
        geen="The dashboard snapshot is not available in this build. It appears once the bot's read-only dashboard "
             "has data that is at least 24 hours old.",
        T="Snapshot", oud="at least 24 hours old, never live",
        exposure="Exposure", exposure_sub="of capital in BTC (cap {cap})", exposure_geen="not reported before T",
        koers="BTC price at T", stap="Ladder step", stap_sub="fine rungs, as % of the price; coarse {c}",
        rsi="RSI (daily)", rsi_sub={"taper": "buy size tapers above {d}, block above {b}", "uit": "RSI brake off",
                                    "blok": "buys pause above {b}"},
        open="Open positions", open_sub="vs. what was paid, % of account",
        verkopen="Sales in window", verkopen_sub="median {m} per sale, before fees",
        prijs_titel="BTC price up to T, and the orders around it at T",
        prijs_desc=("Line chart of the BTC-EUR price from {van} to {tot}, with the bot's buys (blue dots) and sales "
                    "(green dots). On the right, at T: open sell orders above the price, and the fine and coarse buy "
                    "ladders below it."),
        kol_verkoop="Sells", kol_fine="Fine", kol_coarse="Coarse", nu_lbl="T",
        kopen_lgd="Buy filled", verkopen_lgd="Sale", ladder_lgd="Ladder rung (limit buy)", sell_lgd="Open sell order",
        tbl_ladder="Ladder and sell orders at T", tbl_ladder_kop=("Side", "BTC price", "Distance from price"),
        kant_sell="Sell order", kant_fine="Fine rung", kant_coarse="Coarse rung",
        ladder_noot=("Rungs sit on multiples of the step below the price; a rung that already holds a position is "
                     "skipped by the bot, which this view can't show. Sell orders come from the bot's decision log."),
        geen_ladder=("No ladder in this snapshot: the step size is only shown from a reading at least 24 hours old, "
                     "and the first one is stored by the daily build."),
        mom_titel="Every sale in the decision log", mom_desc="Dot chart of each sale's price gain from buy to sell, before fees, {van} to {tot}.",
        mom_tbl="Latest {n} sales", mom_kop=("Date", "Strategy", "Gain, buy to sell"),
        mom_noot=("Each dot is one sale: the price gain from the position's buy price to its sell price, before "
                  "exchange fees ({n} sales, {van} to {tot}). A sale is only placed above the buy price, so none are "
                  "below zero."),
        exp_titel="Exposure over time", exp_desc="Line chart of exposure as % of capital, from the bot's hourly status messages.",
    ),
    "nl": dict(
        geen="De momentopname van het dashboard staat nog niet op deze pagina. Hij verschijnt zodra het read-only dashboard van de bot "
             "gegevens heeft die minstens 24 uur oud zijn.",
        T="Momentopname", oud="minstens 24 uur oud, nooit live",
        exposure="Exposure", exposure_sub="van het kapitaal in BTC (plafond {cap})", exposure_geen="niet gemeld vóór T",
        koers="BTC-koers op T", stap="Ladderstap", stap_sub="fijne treden, als % van de koers; grof {c}",
        rsi="RSI (dag)", rsi_sub={"taper": "kleinere aankopen boven {d}, stop boven {b}", "uit": "RSI-rem uit",
                                  "blok": "aankopen gepauzeerd boven {b}"},
        open="Open posities", open_sub="t.o.v. de aankoopprijs, % van de rekening",
        verkopen="Verkopen in deze periode", verkopen_sub="mediaan {m} per verkoop, vóór kosten",
        prijs_titel="BTC-koers tot T, en de orders eromheen op T",
        prijs_desc=("Lijngrafiek van de BTC-EUR-koers van {van} tot {tot}, met de aankopen (blauwe stippen) en "
                    "verkopen (groene stippen) van de bot. Rechts, op T: open verkooporders boven de koers en de fijne "
                    "en grove koopladder eronder."),
        kol_verkoop="Verkoop", kol_fine="Fijn", kol_coarse="Grof", nu_lbl="T",
        kopen_lgd="Aankoop gevuld", verkopen_lgd="Verkoop", ladder_lgd="Laddertrede (limietkoop)", sell_lgd="Open verkooporder",
        tbl_ladder="Ladder en verkooporders op T", tbl_ladder_kop=("Kant", "BTC-koers", "Afstand tot koers"),
        kant_sell="Verkooporder", kant_fine="Fijne trede", kant_coarse="Grove trede",
        ladder_noot=("Treden liggen op veelvouden van de stap onder de koers; een trede waar al een positie op zit, "
                     "slaat de bot over, en dat is hier niet te zien. Verkooporders komen uit het beslislog van de bot."),
        geen_ladder=("Geen ladder in deze momentopname: de stapgrootte staat er alleen in vanaf een meting van minstens "
                     "24 uur oud, en de eerste wordt door de dagelijkse bouw bewaard."),
        mom_titel="Elke verkoop uit het beslislog", mom_desc="Stippengrafiek van de koerswinst per verkoop, van aankoop tot verkoop, vóór kosten, {van} tot {tot}.",
        mom_tbl="Laatste {n} verkopen", mom_kop=("Datum", "Strategie", "Winst, aankoop tot verkoop"),
        mom_noot=("Elke stip is één verkoop: de koersstijging van de aankoopprijs van die positie tot de verkoopprijs, "
                  "vóór beurskosten ({n} verkopen, {van} tot {tot}). De bot zet een verkoop alleen boven de "
                  "aankoopprijs, dus geen enkele ligt onder nul."),
        exp_titel="Exposure door de tijd", exp_desc="Lijngrafiek van de exposure als % van het kapitaal, uit de statusberichten van de bot.",
    ),
}


# ---------------------------------------------------------------- koersgrafiek met ladder

def _schaal(lo, hi, a, b):
    return lambda v: a + (hi - v) / (hi - lo) * (b - a) if hi > lo else (a + b) / 2


def _ticks(lo, hi, n=5):
    ruw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(ruw)) if ruw > 0 else 1
    stap = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= ruw), default=mag * 10)
    t = math.ceil(lo / stap) * stap
    uit = []
    while t <= hi:
        uit.append(t)
        t += stap
    return uit


def koersgrafiek(m, taal, breedte, hoogte, soort, id_):
    t = L[taal]
    koers = m["koers"]
    links, rechts, boven, onder = (62, 16, 26, 30) if soort == "wide" else (48, 6, 26, 26)
    paneel = 300 if soort == "wide" else 132  # breedte van het orderpaneel rechts
    x0, x1 = links, breedte - rechts - paneel - (24 if soort == "wide" else 10)
    p0 = x1 + (24 if soort == "wide" else 10)
    waarden = [r["prijs"] for r in koers] + [r["prijs"] for r in m["fine"] + m["coarse"] + m["volgende_verkopen"]]
    lo, hi = min(waarden), max(waarden)
    marge = (hi - lo) * 0.06 or hi * 0.01
    lo, hi = lo - marge, hi + marge
    y = _schaal(lo, hi, boven, hoogte - onder)
    tmin, tmax = koers[0]["t"], m["T"]
    span = (tmax - tmin).total_seconds() or 1

    def x(tt):
        return x0 + (tt - tmin).total_seconds() / span * (x1 - x0)

    d = []
    for tk in _ticks(lo, hi, 5 if soort == "wide" else 4):
        d.append(f'<line class="ax-line" x1="{x0}" x2="{breedte - rechts}" y1="{y(tk):.1f}" y2="{y(tk):.1f}"/>'
                 f'<text class="ax px" x="{x0 - 6}" y="{y(tk) + 4:.1f}" text-anchor="end">'
                 f'{f_getal(tk / 1000, taal, 0 if tk % 1000 == 0 else 1)}k</text>')
    # tijd-as: begin en T
    d.append(f'<text class="ax" x="{x0}" y="{hoogte - 8}">{d_kort(tmin, taal)}</text>'
             f'<text class="ax" x="{x1}" y="{hoogte - 8}" text-anchor="end">T · {d_kort(tmax, taal)}</text>')
    pad = " ".join(f"{'M' if i == 0 else 'L'}{x(r['t']):.1f},{y(r['prijs']):.1f}" for i, r in enumerate(koers))
    d.append(f'<path class="koerslijn" d="{pad}"/>')
    for r in m["kopen_venster"]:
        d.append(f'<circle class="pt-koop px" cx="{x(r["t"]):.1f}" cy="{y(r["prijs"]):.1f}" r="3.2"><title>'
                 f'{t["kopen_lgd"]} · {d_tijd(r["t"], taal)} · {f_px(r["prijs"], taal)}</title></circle>')
    for r in m["verkopen_venster"]:
        d.append(f'<circle class="pt-verkoop" cx="{x(r["t"]):.1f}" cy="{y(r["prijs"]):.1f}" r="3.2"><title>'
                 f'{t["verkopen_lgd"]} · {d_tijd(r["t"], taal)} · {f_pct(r["pct"], taal)}</title></circle>')
    yT = y(m["prijs"])
    d.append(f'<line class="prijs-T" x1="{x0}" x2="{breedte - rechts}" y1="{yT:.1f}" y2="{yT:.1f}"/>'
             f'<circle class="pt-T" cx="{x1:.1f}" cy="{yT:.1f}" r="4.5"/>')
    # orderpaneel: drie kolommen
    kol = (paneel - 8) / 3
    kolommen = [(t["kol_verkoop"], m["volgende_verkopen"], "o-verkoop", t["kant_sell"]),
                (t["kol_fine"], m["fine"], "o-fine", t["kant_fine"]),
                (t["kol_coarse"], m["coarse"], "o-coarse", t["kant_coarse"])]
    d.append(f'<rect class="paneel" x="{p0 - 6}" y="{boven - 20}" width="{paneel + 6}" height="{hoogte - onder - boven + 26}" rx="3"/>')
    for i, (kop, rijen, klasse, kant) in enumerate(kolommen):
        cx = p0 + i * (kol + 4)
        d.append(f'<text class="ax kolkop" x="{cx + kol / 2:.1f}" y="{boven - 7}" text-anchor="middle">{kop}</text>')
        for r in rijen:
            d.append(f'<rect class="{klasse} px" x="{cx:.1f}" y="{y(r["prijs"]) - 1.5:.1f}" width="{kol:.1f}" height="3" rx="1.5">'
                     f'<title>{kant} · {f_px(r["prijs"], taal)} · {f_pct(r["afstand"], taal)}</title></rect>')
    d.append(f'<text class="val px" x="{p0 + paneel:.1f}" y="{yT - 6:.1f}" text-anchor="end">T {f_px(m["prijs"], taal)}</text>')
    beschr = t["prijs_desc"].format(van=d_tijd(tmin, taal), tot=d_tijd(tmax, taal))
    return (f'<svg class="{soort}" viewBox="0 0 {breedte} {hoogte}" role="img" aria-labelledby="{id_}-t {id_}-d">'
            f'<title id="{id_}-t">{B.e(t["prijs_titel"])}</title><desc id="{id_}-d">{B.e(beschr)}</desc>'
            f'{"".join(d)}</svg>')


def momentengrafiek(m, taal, breedte, hoogte, soort, id_):
    t = L[taal]
    rijen = [r for r in m["verkopen"] if r["pct"] is not None]
    links, rechts, boven, onder = (46, 12, 14, 26) if soort == "wide" else (40, 6, 14, 24)
    hi = max([r["pct"] for r in rijen] + [1.0]) * 1.1
    lo = min([r["pct"] for r in rijen] + [0.0])
    y = _schaal(lo, hi, boven, hoogte - onder)
    t0, t1 = rijen[0]["t"], rijen[-1]["t"]
    span = (t1 - t0).total_seconds() or 1

    def x(tt):
        return links + (tt - t0).total_seconds() / span * (breedte - links - rechts)

    d = []
    for tk in _ticks(max(lo, 0), hi, 4):
        d.append(f'<line class="ax-line" x1="{links}" x2="{breedte - rechts}" y1="{y(tk):.1f}" y2="{y(tk):.1f}"/>'
                 f'<text class="ax" x="{links - 6}" y="{y(tk) + 4:.1f}" text-anchor="end">{f_pct(tk, taal, False, 1)}</text>')
    d.append(f'<line class="zero" x1="{links}" x2="{breedte - rechts}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    for r in rijen:
        d.append(f'<circle class="pt-verkoop" cx="{x(r["t"]):.1f}" cy="{y(r["pct"]):.1f}" r="2.6"><title>'
                 f'{d_tijd(r["t"], taal)} · {B.e(r["strategie"])} · {f_pct(r["pct"], taal)}</title></circle>')
    d.append(f'<text class="ax" x="{links}" y="{hoogte - 7}">{d_kort(t0, taal)}</text>'
             f'<text class="ax" x="{breedte - rechts}" y="{hoogte - 7}" text-anchor="end">{d_lang(t1, taal)}</text>')
    beschr = t["mom_desc"].format(van=d_lang(t0, taal), tot=d_lang(t1, taal))
    return (f'<svg class="{soort}" viewBox="0 0 {breedte} {hoogte}" role="img" aria-labelledby="{id_}-t {id_}-d">'
            f'<title id="{id_}-t">{B.e(t["mom_titel"])}</title><desc id="{id_}-d">{B.e(beschr)}</desc>{"".join(d)}</svg>')


def sparkline(reeks, breedte=132, hoogte=34):
    if len(reeks) < 2:
        return ""
    w = [r["pct"] for r in reeks]
    lo, hi = min(w + [0]), max(w) * 1.1 or 1
    y = _schaal(lo, hi, 3, hoogte - 3)
    n = len(w) - 1
    pad = " ".join(f"{'M' if i == 0 else 'L'}{2 + i / n * (breedte - 4):.1f},{y(v):.1f}" for i, v in enumerate(w))
    return f'<svg class="spark" viewBox="0 0 {breedte} {hoogte}" aria-hidden="true"><path d="{pad}"/></svg>'


# ---------------------------------------------------------------- het dashboard

def dashboard(m, taal="en"):
    t = L[taal]
    if not m:
        return f'<p class="dash-leeg">{t["geen"]}</p>'
    g = m["grid"] or {}
    exp = m["exposure"]
    tegels = []
    if exp:
        cap = f_pct(exp["cap"], taal, False, 0) if exp["cap"] is not None else "–"
        tegels.append((t["exposure"], f_pct(exp["pct"], taal, False, 1), t["exposure_sub"].format(cap=cap),
                       sparkline(m["exposure_reeks"])))
    else:
        tegels.append((t["exposure"], "–", t["exposure_geen"], ""))
    tegels.append((t["koers"], px(m["prijs"], taal), d_tijd(m["T"], taal), ""))
    if g.get("fine_stap"):
        tegels.append((t["stap"], f'{f_pct(g["fine_stap"] / m["prijs"] * 100, taal, False, 2)}',
                       t["stap_sub"].format(f=f_pct(g["fine_stap"] / m["prijs"] * 100, taal, False, 2),
                                            c=f_pct(g["coarse_stap"] / m["prijs"] * 100, taal, False, 2)), ""))
    if g.get("rsi") is not None:
        if not g.get("rsi_rem"):
            sub = t["rsi_sub"]["uit"]
        elif g.get("rsi_taper"):
            sub = t["rsi_sub"]["taper"].format(d=f_getal(g.get("rsi_drempel") or 70, taal),
                                               b=f_getal(g.get("rsi_blok") or 80, taal))
        else:
            sub = t["rsi_sub"]["blok"].format(b=f_getal(g.get("rsi_blok") or 70, taal))
        tegels.append((t["rsi"], f_getal(g["rsi"], taal, 1), sub, ""))
    if m["open_op_T"] is not None:
        tegels.append((t["open"], f_pct(m["open_op_T"], taal), t["open_sub"], ""))
    pcts = [r["pct"] for r in m["verkopen"] if r["pct"] is not None]
    if pcts:
        tegels.append((t["verkopen"], f_getal(len(pcts), taal),
                       t["verkopen_sub"].format(m=f_pct(statistics.median(pcts), taal)), ""))
    tegel_html = "".join(f'<div class="tegel"><dt>{a}</dt><dd>{b}</dd><p>{c}</p>{s}</div>' for a, b, c, s in tegels)

    koers = (f'<figure class="chart dash-chart" style="margin:0">{koersgrafiek(m, taal, 960, 420, "wide", f"kw-{taal}")}'
             f'{koersgrafiek(m, taal, 360, 330, "narrow", f"kn-{taal}")}'
             f'<ul class="legend"><li><span class="sw dot koop"></span>{t["kopen_lgd"]}</li>'
             f'<li><span class="sw dot verkoop"></span>{t["verkopen_lgd"]}</li>'
             f'<li><span class="sw o-fine"></span>{t["ladder_lgd"]}</li>'
             f'<li><span class="sw o-verkoop"></span>{t["sell_lgd"]}</li></ul>'
             f'<figcaption class="chart-note">{t["ladder_noot"]}'
             f'{" " + t["geen_ladder"] if not m["fine"] else ""}</figcaption></figure>')
    regels = ([(t["kant_sell"], r) for r in reversed(m["volgende_verkopen"])]
              + [(t["kant_fine"], r) for r in m["fine"]] + [(t["kant_coarse"], r) for r in m["coarse"]])
    k = t["tbl_ladder_kop"]
    ladder_tbl = (f'<details><summary>{t["tbl_ladder"]} ({len(regels)})</summary><div class="tbl" tabindex="0" role="region" aria-label="{t["tbl_ladder"]}"><table>'
                  f'<thead><tr><th scope="col">{k[0]}</th><th scope="col" class="r">{k[1]}</th><th scope="col" class="r">{k[2]}</th></tr></thead><tbody>'
                  + "".join(f'<tr><td>{a}</td><td class="r">{px(r["prijs"], taal)}</td><td class="r">{f_pct(r["afstand"], taal)}</td></tr>'
                            for a, r in regels) + "</tbody></table></div></details>")
    momenten = ""
    rijen = [r for r in m["verkopen"] if r["pct"] is not None]
    if len(rijen) >= 2:
        n_tbl = min(100, len(rijen))
        k = t["mom_kop"]
        momenten = (f'<h3 class="dash-h3">{t["mom_titel"]}</h3><figure class="chart" style="margin:0">'
                    f'{momentengrafiek(m, taal, 960, 240, "wide", f"mw-{taal}")}{momentengrafiek(m, taal, 360, 220, "narrow", f"mn-{taal}")}'
                    f'<figcaption class="chart-note">{t["mom_noot"].format(n=f_getal(len(rijen), taal), van=d_lang(rijen[0]["t"], taal), tot=d_tijd(rijen[-1]["t"], taal))}</figcaption></figure>'
                    f'<details><summary>{t["mom_tbl"].format(n=n_tbl)}</summary><div class="tbl" tabindex="0" role="region" aria-label="{t["mom_tbl"].format(n=n_tbl)}"><table>'
                    f'<thead><tr><th scope="col">{k[0]}</th><th scope="col">{k[1]}</th><th scope="col" class="r">{k[2]}</th></tr></thead><tbody>'
                    + "".join(f'<tr><td><time datetime="{r["t"]:%Y-%m-%dT%H:%MZ}">{d_tijd(r["t"], taal)}</time></td>'
                              f'<td><span class="code">{B.e(r["strategie"])}</span></td><td class="r">{f_pct(r["pct"], taal)}</td></tr>'
                              for r in reversed(rijen[-n_tbl:])) + "</tbody></table></div></details>")
    return f"""<p class="dash-stempel"><strong>{t["T"]}: <time datetime="{m["T"]:%Y-%m-%dT%H:%MZ}">{d_tijd(m["T"], taal)}</time></strong> · {t["oud"]}</p>
<dl class="tegels">{tegel_html}</dl>
{koers}
{ladder_tbl}
{momenten}"""
