"""Dashboard-momentopname en volatiliteit voor /how-it-works/ en /zo-werkt-het/ (Daan, 27 okt 2026).

Wat de pagina laat zien is het dashboard van de bot, maar alleen relatief en altijd minstens 24 uur oud, zodat
het nooit een live signaal is. Daarom kiest dit module eerst een ankermoment T: de nieuwste meting uit
/api/portfolio-history die minstens MIN_LEEFTIJD vóór de bouw ligt. Alles wat getoond wordt komt van op of vóór T.

Bronnen (publieke read-only endpoints van het botdashboard; velden nagelezen in dashboard/app.py van de bot):
  /api/portfolio-history   timestamps, btc_price, total_value, unrealized_pnl, realized_pnl (EUR)
                           -> alleen tijd, BTC-koers en de verhouding unrealized/total_value (%)
  /api/grid-multiplier     ladderstap fine/coarse (euro per BTC-koersstap), RSI, modus, ATR, rsi-rem, ...
                           -> alleen stap, RSI, modus, rem-vlaggen; capital_budget (EUR) wordt nooit gelezen
  /api/decision-stream     per beslissing: created_at, decision_type, strategy, level, price, reason, data
                           -> alleen tijd, soort, strategie, prijs en data.profit_pct; 'reason' en de rest van
                              'data' bevatten eurobedragen en worden nooit gelezen
  /api/telegram-feed       verzonden meldingen (tekst met eurobedragen)
                           -> alleen het exposure-percentage en de cap uit de hartslagregel
                              "Exposure: <b>12.3%</b> ... cap 50%"; de tekst zelf wordt nooit bewaard
grid-multiplier heeft geen historie. Elke run (ook als het logboek niet herschreven wordt) bewaart daarom een
opgeschoonde kopie in de cache (W2E_CACHE, standaard ~/.cache/w2e); de pagina gebruikt de nieuwste kopie van op of
vóór T. Is die er nog niet (eerste run), dan de stap van nu, en dat staat er dan bij.

Volatiliteit: dagcandles BTC-EUR van de publieke Bitvavo-API (geen sleutel), gerealiseerd en op jaarbasis:
standaardafwijking (steekproef) van de dagelijkse log-rendementen van de slotkoersen x wortel(365), want bitcoin
handelt elke dag. Het getal komt met de datum van de laatste candle en het aantal rendementen.

Alleen stdlib. --bron <map> (zelfde vlag als build_logboek.py) leest alles uit <map>/<naam>.json, zie bron_naam().
"""
import datetime
import json
import math
import os
import pathlib
import re
import statistics
import sys
import urllib.request

import build_logboek as B

MIN_LEEFTIJD = datetime.timedelta(hours=24)
BITVAVO_CANDLES = "https://api.bitvavo.com/v2/BTC-EUR/candles?interval=1d&limit=365"
FINE_TREDEN, COARSE_TREDEN = 20, 10  # src/config.py van de bot: FINE_GRID_LEVELS, COARSE_GRID_LEVELS (ladderdiepte)
VOLGENDE_VERKOPEN = 8
BESLIS_LIMIET = 500  # maximum van /api/decision-stream
CACHE = pathlib.Path(os.environ.get("W2E_CACHE") or pathlib.Path.home() / ".cache" / "w2e")


def bron_naam(pad):
    """'decision-stream?type=TTP_FIRE&limit=500' -> 'decision-stream-TTP_FIRE' (bestandsnaam onder --bron)."""
    basis, _, query = pad.partition("?")
    soort = re.search(r"type=([A-Z_]+)", query)
    return basis + (f"-{soort.group(1)}" if soort else "")


def _haal(pad, url=None):
    """JSON van de bot-API (of een vaste url); None bij elke fout, zodat een sectie netjes wegvalt."""
    try:
        if "--bron" in sys.argv:
            bestand = pathlib.Path(sys.argv[sys.argv.index("--bron") + 1]) / (bron_naam(pad) + ".json")
            return json.loads(bestand.read_text(encoding="utf-8")) if bestand.exists() else None
        with urllib.request.urlopen(url or B.API + pad, timeout=60) as r:
            return json.load(r)
    except Exception as fout:  # netwerk, 500, kapotte JSON: de pagina bouwt zonder dit onderdeel
        print(f"  (bron {pad} niet bruikbaar: {fout})")
        return None


def _tijd(s):
    """ISO of 'YYYY-MM-DD HH:MM' -> naive UTC datetime; None als het niet te lezen is."""
    if not s:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(datetime.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def _getal(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------- opschonen: wat er níet in staat, kan er niet uit

def schoon_grid(g):
    if not isinstance(g, dict):
        return None
    stappen = g.get("effective_steps") or {}
    uit = {
        "fine_stap": _getal(stappen.get("fine")),
        "coarse_stap": _getal(stappen.get("coarse")),
        "rsi": _getal(g.get("current_rsi")),
        "modus": str(g.get("mode") or "")[:30],
        "rsi_rem": bool(g.get("rsi_rem_enabled", True)),
        "rsi_taper": bool(g.get("rsi_taper_enabled", False)),
        "rsi_blok": _getal(g.get("rsi_hard_block")),
        "rsi_drempel": _getal(g.get("rsi_overbought_threshold")),
    }
    return uit if uit["fine_stap"] and uit["coarse_stap"] else None


def schoon_beslissingen(antwoord, soort):
    rijen = []
    for r in (antwoord or {}).get("rows") or []:
        t, prijs = _tijd(r.get("created_at")), _getal(r.get("price"))
        if t is None or prijs is None or r.get("decision_type") != soort:
            continue
        data = r.get("data") if isinstance(r.get("data"), dict) else {}
        rijen.append({"t": t, "prijs": prijs, "strategie": str(r.get("strategy") or "")[:20],
                      "trede": r.get("level"),  # alleen intern om plaatsing en verkoop te koppelen; nooit getoond
                      "pct": _getal(data.get("profit_pct")) if soort == "TTP_FIRE" else None})
    return sorted(rijen, key=lambda r: r["t"])


EXPOSURE = re.compile(r"Exposure:\s*(?:<b>)?\s*([0-9]+(?:\.[0-9]+)?)\s*%")
CAP = re.compile(r"\bcap\s+([0-9]+(?:\.[0-9]+)?)\s*%")


def schoon_exposure(antwoord):
    rijen = []
    for r in (antwoord or {}).get("rows") or []:
        t, tekst = _tijd(r.get("created_at")), str(r.get("text") or "")
        m = EXPOSURE.search(tekst)
        if t is None or not m:
            continue
        cap = CAP.search(tekst)
        rijen.append({"t": t, "pct": float(m.group(1)), "cap": float(cap.group(1)) if cap else None})
    return sorted(rijen, key=lambda r: r["t"])


# ---------------------------------------------------------------- cache van grid-multiplier (heeft geen historie)

def cache_bewaar(nu, grid):
    if not grid:
        return
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / f"grid-{nu:%Y%m%dT%H%M}.json").write_text(json.dumps(grid), encoding="utf-8")
        for oud in CACHE.glob("grid-*.json"):  # 30 dagen is ruim genoeg
            t = datetime.datetime.strptime(oud.stem[5:], "%Y%m%dT%H%M")
            if nu - t > datetime.timedelta(days=30):
                oud.unlink()
    except OSError as fout:
        print(f"  (cache {CACHE} niet bruikbaar: {fout})")


def cache_op(t_anker):
    beste = None
    for f in CACHE.glob("grid-*.json") if CACHE.exists() else []:
        try:
            t = datetime.datetime.strptime(f.stem[5:], "%Y%m%dT%H%M")
        except ValueError:
            continue
        if t <= t_anker and (beste is None or t > beste[0]):
            beste = (t, f)
    if not beste:
        return None, None
    try:
        return schoon_grid_cache(json.loads(beste[1].read_text(encoding="utf-8"))), beste[0]
    except (OSError, ValueError):
        return None, None


def schoon_grid_cache(d):
    """De cache bevat al opgeschoonde velden; nog één keer filteren op de bekende sleutels."""
    sleutels = ("fine_stap", "coarse_stap", "rsi", "modus", "rsi_rem", "rsi_taper", "rsi_blok", "rsi_drempel")
    return {k: d.get(k) for k in sleutels} if isinstance(d, dict) and d.get("fine_stap") else None


# ---------------------------------------------------------------- momentopname

def ladder(prijs, stap, n):
    """Treden op veelvouden van de stap onder de koers (zo legt manage_grid_ladder ze; een bezette trede slaat de bot
    over, dat is hier niet te zien)."""
    if not prijs or not stap or stap <= 0:
        return []
    eerste = math.floor(prijs / stap) * stap
    if eerste >= prijs:
        eerste -= stap
    return [{"prijs": eerste - k * stap, "afstand": (eerste - k * stap) / prijs * 100 - 100} for k in range(n)]


def momentopname(nu, ph, grid_nu=None):
    """Alles wat het dashboard toont, op of vóór T = nu - 24 uur. nu is naive UTC; grid_nu is de opgeschoonde
    grid-multiplier van deze run (main() bewaart hem al in de cache)."""

    reeks = []
    for ts, prijs, u, tot in zip(ph.get("timestamps", []), ph.get("btc_price", []),
                                 ph.get("unrealized_pnl", []), ph.get("total_value", [])):
        t, p = _tijd(ts), _getal(prijs)
        if t and p:
            reeks.append({"t": t, "prijs": p, "open": (u / tot * 100) if tot else None})
    grens = nu - MIN_LEEFTIJD
    oud = [r for r in reeks if r["t"] <= grens]
    if not oud:
        return None
    anker = oud[-1]
    T, P = anker["t"], anker["prijs"]

    grid, grid_t = cache_op(T)
    stap_bron = "cache"
    if not grid:
        grid, grid_t, stap_bron = grid_nu, nu, "nu"

    kopen = [r for r in schoon_beslissingen(_haal(f"decision-stream?type=BUY_PLACED&limit={BESLIS_LIMIET}"), "BUY_PLACED")
             if r["t"] <= T]
    plaatsingen = [r for r in schoon_beslissingen(
        _haal(f"decision-stream?type=LIMIT_SELL_PLACED&limit={BESLIS_LIMIET}"), "LIMIT_SELL_PLACED") if r["t"] <= T]
    verkopen = [r for r in schoon_beslissingen(_haal(f"decision-stream?type=TTP_FIRE&limit={BESLIS_LIMIET}"), "TTP_FIRE")
                if r["t"] <= T]

    # open verkooporders op T: laatste plaatsing per (strategie, trede) zonder latere verkoop op die trede
    laatste = {}
    for r in plaatsingen:
        laatste[(r["strategie"], r["trede"])] = r
    open_verkoop = []
    for sleutel, r in laatste.items():
        if sleutel[1] is None:
            continue
        verkocht = any(v["strategie"] == sleutel[0] and v["trede"] == sleutel[1] and v["t"] >= r["t"] for v in verkopen)
        if not verkocht and r["prijs"] > P:
            open_verkoop.append({"prijs": r["prijs"], "afstand": r["prijs"] / P * 100 - 100})
    open_verkoop.sort(key=lambda r: r["prijs"])

    exposure = [r for r in schoon_exposure(_haal("telegram-feed?limit=100&zoek=Exposure")) if r["t"] <= T]
    venster_van = reeks[0]["t"]
    return {
        "T": T, "prijs": P, "gebouwd": nu,
        "koers": [r for r in oud],
        "open_op_T": anker["open"],
        "grid": grid, "grid_t": grid_t, "stap_bron": stap_bron,
        "fine": ladder(P, grid and grid["fine_stap"], FINE_TREDEN),
        "coarse": ladder(P, grid and grid["coarse_stap"], COARSE_TREDEN),
        "volgende_verkopen": open_verkoop[:VOLGENDE_VERKOPEN],
        "aantal_open_verkopen": len(open_verkoop),
        "kopen_venster": [r for r in kopen if r["t"] >= venster_van],
        "verkopen_venster": [r for r in verkopen if r["t"] >= venster_van],
        "verkopen": verkopen,
        "exposure": exposure[-1] if exposure else None,
        "exposure_reeks": exposure[-60:],
        "beslis_van": min([r["t"] for r in kopen + plaatsingen + verkopen], default=None),
    }


# ---------------------------------------------------------------- volatiliteit

def volatiliteit():
    """Gerealiseerde jaarvolatiliteit uit dagcandles; None als de candles er niet zijn."""
    candles = _haal("bitvavo-candles", url=BITVAVO_CANDLES)
    rijen = []
    for c in candles or []:
        try:
            t = datetime.datetime.fromtimestamp(int(c[0]) / 1000, datetime.timezone.utc).date()
            slot = float(c[4])
        except (TypeError, ValueError, IndexError):
            continue
        if slot > 0:
            rijen.append((t, slot))
    rijen.sort()
    if len(rijen) < 60:
        return None
    rendementen = [math.log(b[1] / a[1]) for a, b in zip(rijen, rijen[1:])]
    dag = statistics.stdev(rendementen)
    return {"jaar_pct": dag * math.sqrt(365) * 100, "dag_pct": dag * 100, "n": len(rendementen),
            "van": rijen[0][0], "tot": rijen[-1][0],
            # gewone dagbeweging (mediaan van |rendement|) als tastbaar voorbeeld naast het jaargetal
            "mediaan_dag_pct": statistics.median(abs(r) for r in rendementen) * 100}
