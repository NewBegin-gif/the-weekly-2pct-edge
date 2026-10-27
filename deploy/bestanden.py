"""Schrijft (of print) de serverbestanden voor de bouwpakket-levering en mijnbitcoinstrategie.nl. Alleen stdlib.

    python3 deploy/bestanden.py                                   # alles naar stdout
    python3 deploy/bestanden.py --uit /tmp/x                      # als losse bestanden in /tmp/x
    python3 deploy/bestanden.py --uit /tmp/x --caddyfile /etc/caddy/Caddyfile
                                                                  # neemt de security-headers van het EN-blok over
    python3 deploy/bestanden.py --uit /tmp/x --caddyfile /etc/caddy/Caddyfile --nieuwe-caddyfile /tmp/x/Caddyfile
                                                                  # + de hele nieuwe Caddyfile, klaar om te valideren

Bestanden
  levering.service                       systemd-unit -> /etc/systemd/system/levering.service
  mijnbitcoinstrategie.nl.caddy          site-blok (apex + www -> apex 301) -> plakken in /etc/caddy/Caddyfile
  theweekly2pctedge.com.proxy.caddy      drie regels voor IN het bestaande theweekly2pctedge.com-blok
  levering.env.voorbeeld                 elke variabele, GEEN waarden -> /etc/levering.env (chmod 600)

Vaste feiten (VPS): Ubuntu, Caddy, webroots /var/www/<domein>, repos in /root/felix_hq/repos/, venv
/root/felix_hq/venv, ufw alleen 22/80/443 -> de dienst luistert op 127.0.0.1 en Caddy proxyt /webhook/*,
/download/* en /healthz. Security-headers: met --caddyfile worden de header- en import-regels van het
theweekly2pctedge.com-blok letterlijk overgenomen (gelijk aan de EN-site); zonder valt het terug op een vaste set en
zegt het dat. Altijd eerst `caddy validate --config /etc/caddy/Caddyfile` en pas dan `systemctl reload caddy`.
"""
import argparse
import pathlib
import re
import sys

sys.dont_write_bytecode = True

REPO = "/root/felix_hq/repos/the-weekly-2pct-edge"
VENV = "/root/felix_hq/venv"
POORT = 8740
NL, EN = "mijnbitcoinstrategie.nl", "theweekly2pctedge.com"
PADEN = ("/webhook/*", "/download/*", "/healthz")

STANDAARD_HEADERS = """	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		X-Frame-Options "DENY"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		-Server
	}"""

# Elke variabele die levering/instellingen.py leest (test_deploy controleert dat de lijst compleet is).
ENV_VARIABELEN = [
    ("LEVERING_GEHEIM", "lang willekeurig geheim voor de downloadlinks: python3 -c \"import secrets;print(secrets.token_urlsafe(48))\""),
    ("PADDLE_WEBHOOK_GEHEIM", "Paddle > Developer tools > Notifications > (bestemming) > secret"),
    ("PADDLE_API_SLEUTEL", "Paddle API-sleutel met alleen 'customers: read'"),
    ("PADDLE_API_URL", "https://api.paddle.com (sandbox: https://sandbox-api.paddle.com)"),
    ("PADDLE_TOLERANTIE_SEC", "leeg = 300"),
    ("LEVERING_PRIJZEN", "regel uit: python3 bouw/w2e_kassa.py  (env_levering_prijzen)"),
    ("LEVERING_DB", "leeg = /var/lib/levering/levering.db"),
    ("LEVERING_DOCUMENTEN", "leeg = /srv/bouwpakket (buiten de webroot)"),
    ("LEVERING_BASIS_URL_EN", "leeg = https://theweekly2pctedge.com"),
    ("LEVERING_BASIS_URL_NL", "leeg = https://mijnbitcoinstrategie.nl"),
    ("LEVERING_VOORVOEGSEL", "leeg laten"),
    ("LEVERING_POORT", f"leeg = {POORT} (moet gelijk zijn aan de Caddy-regels)"),
    ("LEVERING_LINK_UUR", "leeg = 72"),
    ("LEVERING_UPDATE_LINK_UUR", "leeg = 168"),
    ("LEVERING_MAX_DOWNLOADS", "leeg = 5"),
    ("LEVERING_WACHTRIJ_SEC", "leeg = 300"),
    ("SMTP_HOST", "smtp.hostinger.com"),
    ("SMTP_POORT", "465 (SSL) of 587 (STARTTLS)"),
    ("SMTP_GEBRUIKER", "het volledige mailadres"),
    ("SMTP_WACHTWOORD", "wachtwoord van dat mailadres"),
    ("MAIL_VAN", "bv. Daan <kit@theweekly2pctedge.com> (moet bij het SMTP-account horen)"),
    ("MAIL_ANTWOORD", "reply-to, optioneel"),
]


def systemd(repo=REPO, venv=VENV):
    return f"""[Unit]
Description=Bouwpakket-levering: Paddle-webhook en downloads (theweekly2pctedge.com, mijnbitcoinstrategie.nl)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={repo}
EnvironmentFile=/etc/levering.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={venv}/bin/python -m levering serve
Restart=on-failure
RestartSec=5
# database in /var/lib/levering (systemd maakt de map aan, alleen root)
StateDirectory=levering
StateDirectoryMode=0700
UMask=0077
# afscherming: alleen-lezen systeem, geen nieuwe rechten, eigen /tmp
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/levering
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=true

[Install]
WantedBy=multi-user.target
"""


def proxy_regels(poort=POORT, inspring="\t"):
    return "\n".join(f"{inspring}handle {pad} {{\n{inspring}\treverse_proxy 127.0.0.1:{poort}\n{inspring}}}" for pad in PADEN)


def site_blok(tekst, domein):
    """De inhoud van het site-blok voor dit domein (zonder de buitenste accolades), of None."""
    for m in re.finditer(r"(?m)^([^\s#{][^{\n]*)\{\s*$", tekst):
        adressen = [a.split("://")[-1].split(":")[0] for a in re.split(r"[\s,]+", m.group(1).strip()) if a]
        if domein in adressen:
            diepte, i = 1, m.end()
            while i < len(tekst) and diepte:
                diepte += {"{": 1, "}": -1}.get(tekst[i], 0)
                i += 1
            return tekst[m.end():i - 1]
    return None


def headers_uit_caddyfile(pad, domein=EN):
    """De header- en import-regels (op het hoogste niveau) uit het blok van domein, letterlijk; of None."""
    blok = site_blok(pathlib.Path(pad).read_text(encoding="utf-8"), domein)
    if blok is None:
        return None
    regels, i, uit = blok.splitlines(), 0, []
    while i < len(regels):
        r = regels[i]
        kaal = r.strip()
        if kaal.startswith("import "):
            uit.append("\t" + kaal)
        elif kaal.startswith("header") and not kaal.startswith("header_"):
            if kaal.endswith("{"):
                diepte, stuk = 0, []
                while i < len(regels):
                    diepte += regels[i].count("{") - regels[i].count("}")
                    stuk.append(regels[i])
                    if diepte <= 0:
                        break
                    i += 1
                minst = min(len(x) - len(x.lstrip()) for x in stuk if x.strip())
                uit += ["\t" + x[minst:] for x in stuk]
            else:
                uit.append("\t" + kaal)
        i += 1
    return "\n".join(uit) if uit else None


def nl_caddy(headers, poort=POORT):
    return f"""# mijnbitcoinstrategie.nl: statische site + bouwpakket-levering (deploy/bestanden.py)
www.{NL} {{
	redir https://{NL}{{uri}} permanent
}}

{NL} {{
	root * /var/www/{NL}
	encode zstd gzip
{headers}

	# bouwpakket-levering op 127.0.0.1 (systemd: levering.service)
{proxy_regels(poort)}

	# nooit serveren, ook niet als het per ongeluk in de webroot belandt
	@verborgen path *.py *.pyc *.md *.db *.sqlite *.sqlite3 *.env *.bak* *.orig /.git/* /.env
	respond @verborgen 404

	file_server
	handle_errors {{
		@niet_gevonden expression {{err.status_code}} == 404
		handle @niet_gevonden {{
			rewrite * /404.html
			file_server
		}}
	}}
}}
"""


def en_regels(poort=POORT):
    return f"""	{MERK}: deze regels horen IN het bestaande {EN}-blok,
	# (--nieuwe-caddyfile zet ze er zelf in). handle-blokken met een pad gaan vóór een algemeen handle-blok
	# en vóór file_server, dus de rest van de site verandert niet.
{proxy_regels(poort)}
"""


MERK = "# bouwpakket-levering (deploy/bestanden.py)"


def nieuwe_caddyfile(tekst, nl_blok, poort=POORT):
    """De hele Caddyfile met (1) de proxyregels bovenaan in het theweekly2pctedge.com-blok en (2) het NL-blok
    achteraan. Idempotent: wat er al staat (herkend aan MERK of een bestaand mijnbitcoinstrategie.nl-blok) wordt niet
    nog eens toegevoegd. Plaats binnen het blok maakt niet uit: handle-blokken met een pad gaan in Caddy altijd vóór
    file_server en vóór een algemeen handle-blok."""
    if site_blok(tekst, EN) is None:
        raise SystemExit(f"geen {EN}-blok gevonden in de Caddyfile: niets gewijzigd")
    if MERK not in tekst:
        for m in re.finditer(r"(?m)^([^\s#{][^{\n]*)\{\s*$", tekst):
            adressen = [a.split("://")[-1].split(":")[0] for a in re.split(r"[\s,]+", m.group(1).strip()) if a]
            if EN in adressen:
                invoeg = f"\t{MERK}\n{proxy_regels(poort)}\n\n"
                tekst = tekst[:m.end()] + "\n" + invoeg + tekst[m.end():].lstrip("\n")
                break
    if site_blok(tekst, NL) is None:
        tekst = tekst.rstrip("\n") + "\n\n" + nl_blok
    return tekst


def env_sjabloon():
    regels = ["# /etc/levering.env voor levering.service. Rechten: chown root:root /etc/levering.env && chmod 600 /etc/levering.env",
              "# Vul de waarden op de server in; dit bestand komt NOOIT in git. Een lege waarde = de standaard uit",
              "# levering/instellingen.py.", ""]
    for naam, uitleg in ENV_VARIABELEN:
        regels += [f"# {uitleg}", f"{naam}=", ""]
    return "\n".join(regels)


def alle(caddyfile=None, repo=REPO, venv=VENV, poort=POORT):
    headers, bron = None, "vaste standaardset"
    if caddyfile:
        headers = headers_uit_caddyfile(caddyfile)
        bron = f"overgenomen uit het {EN}-blok in {caddyfile}" if headers else f"niet gevonden in {caddyfile}: vaste standaardset"
    return {
        "levering.service": systemd(repo, venv),
        f"{NL}.caddy": nl_caddy(headers or STANDAARD_HEADERS, poort),
        f"{EN}.proxy.caddy": en_regels(poort),
        "levering.env.voorbeeld": env_sjabloon(),
    }, bron


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--uit", help="map om de bestanden in te schrijven (anders stdout)")
    p.add_argument("--caddyfile", help="bestaande Caddyfile om de security-headers van het EN-blok uit te lezen")
    p.add_argument("--repo", default=REPO)
    p.add_argument("--venv", default=VENV)
    p.add_argument("--poort", type=int, default=POORT)
    p.add_argument("--nieuwe-caddyfile", help="schrijf de hele Caddyfile (met EN-regels en NL-blok) naar dit pad; "
                                              "vereist --caddyfile; het origineel wordt niet aangeraakt")
    a = p.parse_args(argv)
    bestanden, bron = alle(a.caddyfile, a.repo, a.venv, a.poort)
    if a.nieuwe_caddyfile:
        if not a.caddyfile:
            raise SystemExit("--nieuwe-caddyfile vereist --caddyfile")
        nieuw = nieuwe_caddyfile(pathlib.Path(a.caddyfile).read_text(encoding="utf-8"), bestanden[f"{NL}.caddy"], a.poort)
        pathlib.Path(a.nieuwe_caddyfile).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.nieuwe_caddyfile).write_text(nieuw, encoding="utf-8")
        print(f"geschreven: {a.nieuwe_caddyfile} (eerst: caddy validate --config {a.nieuwe_caddyfile} --adapter caddyfile)")
    if a.uit:
        doel = pathlib.Path(a.uit)
        doel.mkdir(parents=True, exist_ok=True)
        for naam, inhoud in bestanden.items():
            (doel / naam).write_text(inhoud, encoding="utf-8")
            print(f"geschreven: {doel / naam}")
    else:
        for naam, inhoud in bestanden.items():
            print(f"===== {naam} =====\n{inhoud}")
    print(f"security-headers: {bron}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
