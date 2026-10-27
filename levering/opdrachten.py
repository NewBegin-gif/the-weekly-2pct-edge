"""Opdrachtregel van de levering (python3 -m levering <opdracht>).

  serve                                         HTTP-dienst op 127.0.0.1 (+ wachtrij-draad). Zonder
                                                PADDLE_WEBHOOK_GEHEIM draait hij in stand-by: /healthz werkt, elke
                                                webhook krijgt 401 (zo kan alles live vóór de goedkeuring van Paddle).
  nieuwe-versie --versie V --bestand PAD [--bestand-nl PAD] [--commit SHA] [--changelog BESTAND]
                                                een documentversie registreren: --bestand is de Engelse editie,
                                                --bestand-nl de Nederlandse (NL-kopers krijgen die); buiten de webroot
  send-update --versie V [--dry-run]            actieve abonnees mailen; --dry-run verstuurt en schrijft niets
  wachtrij                                      wachtende leveringsmails nu versturen (anders doet serve het zelf)
  export --uit PAD.csv                          alle abonnees naar CSV voor de boekhouding (rechten 600; weigert een
                                                pad in een webroot of in de repo: dit bestand wordt nooit geserveerd)
  maandrapport --bot-repo PAD                   commits sinds de laatste documentversie (voor Claude, maandelijks)
  abonnees                                      actieve abonnees tonen (e-mail, taal, status, actief tot)
  aankopen                                      betaalde aankopen zonder herroepingstoestemming (niet geleverd)
  vrijgeven --transactie TXN --toestemming TEKST
                                                zo'n aankoop alsnog leveren nadat de koper toestemming gaf (bv. per
                                                mail: TEKST = "per mail 2026-11-02"); anders: refund in Paddle

Op de VPS (zie de PR): `--env /etc/levering.env` leest de instellingen zoals systemd ze aan de dienst geeft. Als root
gestart, werkt de opdracht op de database als de eigenaar van de databasemap (de dienstgebruiker 'levering'), zodat
er nooit bestanden van root in /var/lib/levering komen; alleen wat root nodig heeft (het env-bestand, de changelog,
git in de bot-repo, het exportbestand) gebeurt als root.
"""
import argparse
import contextlib
import logging
import os
import pathlib
import sys

from .instellingen import Instellingen
from .kern import Levering, export_abonnees, maandrapport
from .opslag import Opslag


def lees_env(pad):
    """KEY=waarde-regels zoals systemd EnvironmentFile ze leest (commentaar, lege regels, aanhalingstekens om de
    hele waarde). Zet alleen wat nog niet in de omgeving staat."""
    for regel in pathlib.Path(pad).read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith(("#", ";")) or "=" not in regel:
            continue
        sleutel, _, waarde = regel.partition("=")
        waarde = waarde.strip()
        if len(waarde) >= 2 and waarde[0] == waarde[-1] and waarde[0] in "'\"":
            waarde = waarde[1:-1]
        os.environ.setdefault(sleutel.strip(), waarde)


def als_eigenaar_van(map_):
    """Als root: effectief de eigenaar van de databasemap worden (alleen effectieve ids, terug via als_root)."""
    if os.geteuid() != 0 or not os.path.isdir(map_):
        return
    st = os.stat(map_)
    if st.st_uid != 0:
        os.setegid(st.st_gid)
        os.seteuid(st.st_uid)


@contextlib.contextmanager
def als_root():
    terug = (os.geteuid(), os.getegid())
    if os.getuid() == 0 and terug[0] != 0:
        os.seteuid(0)
        os.setegid(0)
        try:
            yield
        finally:
            os.setegid(terug[1])
            os.seteuid(terug[0])
    else:
        yield


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="python3 -m levering")
    p.add_argument("--env", help="env-bestand inlezen (bv. /etc/levering.env), zoals systemd dat voor de dienst doet")
    sub = p.add_subparsers(dest="opdracht", required=True)
    sub.add_parser("serve")
    nv = sub.add_parser("nieuwe-versie")
    nv.add_argument("--versie", required=True)
    nv.add_argument("--bestand", required=True, help="Engelse editie (pdf)")
    nv.add_argument("--bestand-nl", help="Nederlandse editie (pdf); NL-kopers krijgen deze")
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
    sub.add_parser("aankopen")
    vg = sub.add_parser("vrijgeven")
    vg.add_argument("--transactie", required=True)
    vg.add_argument("--toestemming", required=True)
    a = p.parse_args(argv)
    if a.env:
        lees_env(a.env)
    cfg = Instellingen()
    if a.opdracht != "serve":
        als_eigenaar_van(str(pathlib.Path(cfg.db).parent))

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
        bestanden = []
        for ruw in (a.bestand, a.bestand_nl):
            if not ruw:
                bestanden.append(None)
                continue
            bestand = pathlib.Path(ruw).resolve()
            if not bestand.is_file():
                raise SystemExit(f"{bestand} bestaat niet")
            if str(bestand).startswith("/var/www"):
                raise SystemExit(f"weigert {bestand}: het betaalde document hoort buiten de webroot")
            try:
                bestand.open("rb").close()  # met de rechten van de dienst: anders zou elke download 'bestand ontbreekt' geven
            except PermissionError:
                raise SystemExit(f"de dienst kan {bestand} niet lezen: chgrp levering + chmod 640 (map: 750)")
            bestanden.append(str(bestand))
        with als_root():
            changelog = pathlib.Path(a.changelog).read_text(encoding="utf-8").strip() if a.changelog else ""
        try:
            Opslag(cfg.db).versie_bewaar(a.versie, bestanden[0], a.commit, changelog, bestand_nl=bestanden[1])
        except ValueError as fout:
            raise SystemExit(str(fout))
        print(f"versie {a.versie} geregistreerd: {' + '.join(b for b in bestanden if b)}")
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
        rijen = Opslag(cfg.db).alle_abonnees()
        with als_root():
            doel, n = export_abonnees(None, a.uit, rijen=rijen)
        print(f"{n} abonnees naar {doel}")
    elif a.opdracht == "maandrapport":
        versie = Opslag(cfg.db).versie()
        with als_root():
            sys.stdout.write(maandrapport(None, pathlib.Path(a.bot_repo), versie=versie))
    elif a.opdracht == "abonnees":
        for r in Opslag(cfg.db).actieve_abonnees():
            print(f"{r['email']}\t{r['taal'] or 'en'}\t{r['status']}\t{r['actief_tot']}")
    elif a.opdracht == "aankopen":
        for r in Opslag(cfg.db).aankopen_zonder_toestemming():
            print(f"{r['transactie_id']}\t{r['email']}\t{r['taal'] or 'en'}\t{r['moment']}\tgeen toestemming, niet geleverd")
    elif a.opdracht == "vrijgeven":
        levering = Levering(cfg)
        if not levering.vrijgeven(a.transactie, a.toestemming):
            raise SystemExit(f"{a.transactie}: geen aankoop die op toestemming wacht")
        ok, fout = levering.wachtrij()
        print(f"{a.transactie} vrijgegeven; {ok} verzonden, {fout} mislukt (blijven in de rij)")
    return 0
