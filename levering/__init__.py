"""Levering van het bouwpakket: Paddle-webhook -> e-mail met getekende downloadlink; abonnees krijgen updates.

Alleen stdlib (+ sqlite3). Alle bestanden in deze map zijn .py, omdat de rsync naar de webroot *.py uitsluit; uitleg
staat daarom hier en in de docstrings, niet in een .md die publiek zou worden. Draait op de VPS als eigen dienst achter
Caddy, NIET in de webroot. Het betaalde document staat nooit in deze (publieke) repo: het ligt in de private bot-repo
en wordt op de VPS buiten de webroot neergezet (LEVERING_DOCUMENTEN).

Onderdelen
  instellingen.py  alle configuratie uit omgevingsvariabelen (geen geheimen in code)
  opslag.py        SQLite: kopers, abonnees, documentversies, downloadlinks, verzendingen, verwerkte events
  paddle.py        handtekening van Paddle Billing controleren, events vertalen naar onze eigen gebeurtenissen
  kern.py          de logica: webhook verwerken, kit en updates mailen, download, maandrapport (los van HTTP/SMTP)
  links.py         getekende, verlopende downloadlinks (standaard 72 uur, 5 downloads)
  post.py          e-mails (EN/NL) en verzenden via SMTP (Hostinger)
  dienst.py        de HTTP-dienst: POST /webhook/paddle, GET /download/<token>, GET /healthz (+ wachtrij-draad)
  opdrachten.py    opdrachtregel: serve, nieuwe-versie, send-update (--dry-run), wachtrij, export, maandrapport, abonnees
  test_levering.py tests: handtekening, replay, volgorde, refund/chargeback, SMTP-wachtrij, gelijktijdige
                   downloads, verlopen link, idempotente updates, export, HTTP-routes

Gebruik (op de VPS; de dienst draait als gebruiker 'levering' vanuit /opt/levering, opdrachten als root met
`cd /opt/levering && python3 -m levering --env /etc/levering.env <opdracht>`: de database wordt dan als 'levering'
geopend, zie opdrachten.py)
  python3 -m levering serve                                  # luistert op 127.0.0.1:$LEVERING_POORT
  python3 -m levering aankopen                               # betaald maar zonder herroepingstoestemming: niet geleverd
  python3 -m levering vrijgeven --transactie txn_... --toestemming "per mail 2026-11-02"
  python3 -m levering wachtrij                               # wachtende leveringsmails nu versturen
  python3 -m levering export --uit /root/boekhouding/abonnees.csv   # nooit in een webroot
  python3 -m levering nieuwe-versie --versie 1.1 --bestand /srv/bouwpakket/BOUWPAKKET_EN-v1.1.pdf --bestand-nl /srv/bouwpakket/BOUWPAKKET_NL-v1.1.pdf --commit <volledige sha in de bot-repo> --changelog wijzigingen.txt
  python3 -m levering send-update --versie 1.1 --dry-run     # wie zou wat krijgen; verstuurt en schrijft niets
  python3 -m levering send-update --versie 1.1               # verstuurt; nogmaals draaien slaat wie al kreeg over
  python3 -m levering maandrapport --bot-repo ~/Bitcoin-Cycle-Bot   # commits sinds de laatste documentversie
  python3 -m unittest levering.test_levering                 # tests

Omgevingsvariabelen: zie instellingen.py.

Caddy en systemd: deploy/bestanden.py schrijft de unit, de Caddy-blokken (beide domeinen sturen /webhook/*,
/download/* en /healthz naar 127.0.0.1:8740) en een leeg /etc/levering.env-sjabloon; het runbook staat in de PR.
"""
