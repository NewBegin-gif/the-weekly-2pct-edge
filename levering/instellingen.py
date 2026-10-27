"""Configuratie uit de omgeving. Geen geheim staat in code; ontbreekt er een, dan zegt de dienst welke.

  LEVERING_DB               pad naar de SQLite-database             (standaard /var/lib/levering/levering.db)
  LEVERING_DOCUMENTEN       map met de documentversies, BUITEN de webroot (standaard /srv/bouwpakket)
  LEVERING_GEHEIM           sleutel voor de downloadlinks (lang, willekeurig; `python3 -c "import secrets;print(secrets.token_urlsafe(48))"`)
  LEVERING_BASIS_URL_EN     basis van de downloadlinks voor Engelse kopers  (standaard https://theweekly2pctedge.com)
  LEVERING_BASIS_URL_NL     basis van de downloadlinks voor Nederlandse kopers (standaard https://mijnbitcoinstrategie.nl)
                            Caddy stuurt /webhook/*, /download/* en /healthz op beide domeinen naar deze dienst.
  LEVERING_VOORVOEGSEL      padvoorvoegsel dat Caddy eventueel doorgeeft (standaard leeg)
  LEVERING_POORT            poort op 127.0.0.1 (standaard 8740)
  LEVERING_LINK_UUR         geldigheid aankooplink in uren (standaard 72)
  LEVERING_UPDATE_LINK_UUR  geldigheid updatelink in uren (standaard 168)
  LEVERING_MAX_DOWNLOADS    downloads per link (standaard 5)
  LEVERING_WACHTRIJ_SEC     hoe vaak de dienst mislukte leveringsmails opnieuw probeert (standaard 300)
  LEVERING_PRIJZEN          Paddle-prijs-id's -> product:taal, bv. "pri_01a=kit:en,pri_01b=kit:nl,pri_01c=updates:en,pri_01d=updates:nl"
  PADDLE_WEBHOOK_GEHEIM     geheim van de Paddle-notificatiebestemming (Developer tools > Notifications)
  PADDLE_API_SLEUTEL        API-sleutel (alleen lezen klanten) om het e-mailadres bij een customer_id op te halen
  PADDLE_API_URL            https://api.paddle.com (of https://sandbox-api.paddle.com)
  PADDLE_TOLERANTIE_SEC     max. leeftijd van een webhook-handtekening (standaard 300)
  SMTP_HOST / SMTP_POORT    Hostinger: smtp.hostinger.com / 465 (SSL) of 587 (STARTTLS)
  SMTP_GEBRUIKER / SMTP_WACHTWOORD
  MAIL_VAN                  afzender, bv. "Daan <kit@theweekly2pctedge.com>"
  MAIL_ANTWOORD             reply-to (optioneel)
"""
import os
from dataclasses import dataclass, field


def _s(naam, standaard=""):
    """Een lege waarde (NAAM= in /etc/levering.env) telt als niet ingesteld: dan de standaard."""
    return os.environ.get(naam) or standaard


def _int(naam, standaard):
    try:
        return int(_s(naam, standaard))
    except ValueError:
        return standaard


def _prijzen(tekst):
    uit = {}
    for deel in (tekst or "").split(","):
        if "=" in deel and ":" in deel:
            prijs, rest = deel.split("=", 1)
            product, taal = rest.split(":", 1)
            uit[prijs.strip()] = (product.strip(), taal.strip())
    return uit


@dataclass
class Instellingen:
    db: str = field(default_factory=lambda: _s("LEVERING_DB", "/var/lib/levering/levering.db"))
    documenten: str = field(default_factory=lambda: _s("LEVERING_DOCUMENTEN", "/srv/bouwpakket"))
    geheim: str = field(default_factory=lambda: _s("LEVERING_GEHEIM", ""))
    basis_url_en: str = field(default_factory=lambda: _s("LEVERING_BASIS_URL_EN", "https://theweekly2pctedge.com"))
    basis_url_nl: str = field(default_factory=lambda: _s("LEVERING_BASIS_URL_NL", "https://mijnbitcoinstrategie.nl"))
    voorvoegsel: str = field(default_factory=lambda: _s("LEVERING_VOORVOEGSEL", ""))
    poort: int = field(default_factory=lambda: _int("LEVERING_POORT", 8740))
    link_uur: int = field(default_factory=lambda: _int("LEVERING_LINK_UUR", 72))
    update_link_uur: int = field(default_factory=lambda: _int("LEVERING_UPDATE_LINK_UUR", 168))
    max_downloads: int = field(default_factory=lambda: _int("LEVERING_MAX_DOWNLOADS", 5))
    wachtrij_sec: int = field(default_factory=lambda: _int("LEVERING_WACHTRIJ_SEC", 300))
    prijzen: dict = field(default_factory=lambda: _prijzen(_s("LEVERING_PRIJZEN")))
    paddle_geheim: str = field(default_factory=lambda: _s("PADDLE_WEBHOOK_GEHEIM", ""))
    paddle_api_sleutel: str = field(default_factory=lambda: _s("PADDLE_API_SLEUTEL", ""))
    paddle_api_url: str = field(default_factory=lambda: _s("PADDLE_API_URL", "https://api.paddle.com"))
    paddle_tolerantie: int = field(default_factory=lambda: _int("PADDLE_TOLERANTIE_SEC", 300))
    smtp_host: str = field(default_factory=lambda: _s("SMTP_HOST", ""))
    smtp_poort: int = field(default_factory=lambda: _int("SMTP_POORT", 465))
    smtp_gebruiker: str = field(default_factory=lambda: _s("SMTP_GEBRUIKER", ""))
    smtp_wachtwoord: str = field(default_factory=lambda: _s("SMTP_WACHTWOORD", ""))
    mail_van: str = field(default_factory=lambda: _s("MAIL_VAN", ""))
    mail_antwoord: str = field(default_factory=lambda: _s("MAIL_ANTWOORD", ""))

    def basis_url(self, taal):
        return (self.basis_url_nl if taal == "nl" else self.basis_url_en).rstrip("/")

    def ontbrekend(self, voor="serve"):
        nodig = {"serve": ["geheim"] + (["prijzen", "smtp_host", "mail_van"] if self.paddle_geheim else []),
                 "send-update": ["geheim", "smtp_host", "mail_van"]}.get(voor, [])
        return [n for n in nodig if not getattr(self, n)]
