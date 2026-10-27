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
  dienst.py        de HTTP-dienst: POST /paddle/webhook, GET /download/<token>, GET /gezond
  opdrachten.py    opdrachtregel: serve, nieuwe-versie, send-update (met --dry-run), maandrapport, abonnees
  test_levering.py tests: handtekening, verlopen link, idempotente updates, webhookstroom

Gebruik (op de VPS)
  python3 -m levering serve                                  # luistert op 127.0.0.1:$LEVERING_POORT
  python3 -m levering nieuwe-versie --versie 1.0 --bestand /srv/bouwpakket/v1.0.pdf --commit <volledige sha in de bot-repo> --changelog wijzigingen.txt
  python3 -m levering send-update --versie 1.1 --dry-run     # wie zou wat krijgen; verstuurt en schrijft niets
  python3 -m levering send-update --versie 1.1               # verstuurt; nogmaals draaien slaat wie al kreeg over
  python3 -m levering maandrapport --bot-repo ~/Bitcoin-Cycle-Bot   # commits sinds de laatste documentversie
  python3 -m unittest levering.test_levering                 # tests

Omgevingsvariabelen: zie instellingen.py.

Caddy (voorbeeld; pad en poort zijn aannames):
  theweekly2pctedge.com {
      handle /kit/* { reverse_proxy 127.0.0.1:8740 }   # /kit/paddle/webhook en /kit/download/<token>
      ...
  }
  (de dienst haalt het voorvoegsel LEVERING_VOORVOEGSEL, standaard /kit, zelf van het pad af)
"""
