"""Opdrachtregel van de levering (python3 -m levering <opdracht>).

  serve                                         HTTP-dienst op 127.0.0.1 (+ wachtrij-draad). Zonder
                                                PADDLE_WEBHOOK_GEHEIM draait hij in stand-by: /healthz werkt, elke
                                                webhook krijgt 401 (zo kan alles live vóór de goedkeuring van Paddle).
  nieuwe-versie --versie V --bestand PAD [--commit SHA] [--changelog BESTAND]
                                                een documentversie registreren (het bestand blijft buiten de webroot)
  send-update --versie V [--dry-run]            actieve abonnees mailen; --dry-run verstuurt en schrijft niets
  wachtrij                                      wachtende leveringsmails nu versturen (anders doet serve het zelf)
  export --uit PAD.csv                          alle abonnees naar CSV voor de boekhouding (rechten 600; weigert een
                                                pad in een webroot of in de repo: dit bestand wordt nooit geserveerd)
  maandrapport --bot-repo PAD                   commits sinds de laatste documentversie (voor Claude, maandelijks)
  abonnees                                      actieve abonnees tonen (e-mail, taal, status, actief tot)
"""
import argparse
import logging
import pathlib
import sys

from .instellingen import Instellingen
from .kern import Levering, export_abonnees, maandrapport
from .opslag import Opslag


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="python3 -m levering")
    sub = p.add_subparsers(dest="opdracht", required=True)
    sub.add_parser("serve")
    nv = sub.add_parser("nieuwe-versie")
    nv.add_argument("--versie", required=True)
    nv.add_argument("--bestand", required=True)
    nv.add_argument("--commit", default="")
    nv.add_argument("--changelog", help="tekstbestand met de wijzigingen (komt in de updatemail)")
    su = sub.add_parser("send-update")
    su.add_argument("--versie", required=True)
    su.add_argument("--dry-run", action="store_true")
    sub.add_parser("wachtrij")
    ex = sub.add_parser("export")
    ex.add_argument("--uit", required=True)
    mr = sub.add_parser("maandrapport")
    mr.add_argument("--bot-repo", required=True)
    sub.add_parser("abonnees")
    a = p.parse_args(argv)
    cfg = Instellingen()

    if a.opdracht == "serve":
        mist = cfg.ontbrekend("serve")
        if mist:
            raise SystemExit(f"ontbrekende instellingen: {', '.join(mist)} (zie levering/instellingen.py)")
        from .dienst import serve
        if not cfg.paddle_geheim:
            logging.warning("stand-by: PADDLE_WEBHOOK_GEHEIM is leeg, elke webhook krijgt 401 tot Paddle is ingericht")
        pathlib.Path(cfg.db).parent.mkdir(parents=True, exist_ok=True)
        serve(Levering(cfg))
    elif a.opdracht == "nieuwe-versie":
        bestand = pathlib.Path(a.bestand).resolve()
        if not bestand.is_file():
            raise SystemExit(f"{bestand} bestaat niet")
        if str(bestand).startswith("/var/www"):
            raise SystemExit(f"weigert {bestand}: het betaalde document hoort buiten de webroot")
        changelog = pathlib.Path(a.changelog).read_text(encoding="utf-8").strip() if a.changelog else ""
        Opslag(cfg.db).versie_bewaar(a.versie, str(bestand), a.commit, changelog)
        print(f"versie {a.versie} geregistreerd: {bestand}")
    elif a.opdracht == "send-update":
        if not a.dry_run:
            mist = cfg.ontbrekend("send-update")
            if mist:
                raise SystemExit(f"ontbrekende instellingen: {', '.join(mist)}")
        levering = Levering(cfg, verzend=None if not a.dry_run else (lambda m: None))
        uitkomst = levering.send_update(a.versie, dry_run=a.dry_run)
        print(f"{len(uitkomst)} actieve abonnees; " + ", ".join(
            f"{sum(1 for _, u in uitkomst if u.startswith(k))} {k}" for k in ("verzonden", "zou", "al eerder", "mislukt")))
    elif a.opdracht == "wachtrij":
        ok, fout = Levering(cfg).wachtrij()
        print(f"{ok} verzonden, {fout} mislukt (blijven in de rij)")
    elif a.opdracht == "export":
        doel, n = export_abonnees(Opslag(cfg.db), a.uit)
        print(f"{n} abonnees naar {doel}")
    elif a.opdracht == "maandrapport":
        sys.stdout.write(maandrapport(Opslag(cfg.db), pathlib.Path(a.bot_repo)))
    elif a.opdracht == "abonnees":
        for r in Opslag(cfg.db).actieve_abonnees():
            print(f"{r['email']}\t{r['taal'] or 'en'}\t{r['status']}\t{r['actief_tot']}")
    return 0
