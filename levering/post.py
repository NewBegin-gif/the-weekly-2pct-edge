"""E-mails (Engels/Nederlands) en verzenden via SMTP.

Hostinger: SMTP_HOST=smtp.hostinger.com, SMTP_POORT=465 (SSL) of 587 (STARTTLS), gebruiker = het volledige
mailadres. Geen geheimen in code. Elke mail is platte tekst, met het leverings- en risicobericht erin.
"""
import email.message
import email.utils
import re
import smtplib
import ssl

# Eén kaal adres (geen naam, geen komma, geen regeleinde): wat Paddle als klant-e-mail heeft. Strenger dan RFC 5322
# met opzet; een afgewezen adres wordt niet gemaild en staat als 'ongeldig_adres' in de wachtrij (zie kern.wachtrij).
_ADRES = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}")


def adres_geldig(adres):
    return isinstance(adres, str) and len(adres) <= 254 and _ADRES.fullmatch(adres) is not None

TEKSTEN = {
    "en": {
        "kit_onderwerp": "Your build kit download",
        "kit": ("Thanks for buying the build kit.\n\nDownload it here (valid for {uur} hours, up to {max} downloads):\n{link}\n\n"
                "Version: {versie}\n\nAt checkout you asked for immediate delivery and acknowledged that you lose the "
                "14-day right of withdrawal once delivery has started.\n\nHow to use it: upload the document into your AI "
                "assistant and let it walk you through every step. Start small. The bot trades with real money; past "
                "weeks say nothing about future weeks, and you can lose your entire stake.\n\nThis is engineering "
                "documentation, not financial advice and not a signal service.\n\nDaan\n"),
        "update_onderwerp": "Build kit update: version {versie}",
        "update": ("The bot changed, so the build plan did too. Version {versie} is ready.\n\nWhat changed:\n{changelog}\n\n"
                   "Download (valid for {uur} hours, up to {max} downloads):\n{link}\n\nYou get this because you "
                   "subscribed to build kit updates. Your subscription runs until {tot}; you can cancel any time via the link in "
                   "your Paddle receipt.\n\nPast weeks say nothing about future weeks, and you can lose your entire stake. "
                   "This is engineering documentation, not financial advice and not a signal service.\n\nDaan\n"),
    },
    "nl": {
        "kit_onderwerp": "Je bouwpakket staat klaar",
        "kit": ("Bedankt voor je aankoop van het bouwpakket.\n\nDownload het hier ({uur} uur geldig, maximaal {max} "
                "downloads):\n{link}\n\nVersie: {versie}\n\nBij het afrekenen vroeg je om directe levering en erkende je "
                "dat je herroepingsrecht van 14 dagen vervalt zodra de levering begint.\n\nZo gebruik je het: upload het "
                "document in je AI-assistent en laat die je door elke stap leiden. Begin klein. De bot handelt met echt "
                "geld; afgelopen weken zeggen niets over komende weken, en je kunt je hele inleg verliezen.\n\nDit is "
                "technische documentatie, geen financieel advies en geen signaaldienst.\n\nDaan\n"),
        "update_onderwerp": "Update bouwpakket: versie {versie}",
        "update": ("De bot is veranderd, en het bouwplan dus ook. Versie {versie} staat klaar.\n\nWat er veranderde:\n"
                   "{changelog}\n\nDownload ({uur} uur geldig, maximaal {max} downloads):\n{link}\n\nJe krijgt dit "
                   "omdat je een update-abonnement op het bouwpakket hebt. Het loopt tot {tot}; opzeggen kan altijd via de link in "
                   "je betaalbewijs van Paddle.\n\nAfgelopen weken zeggen niets over komende weken, en je kunt je hele inleg "
                   "verliezen. Dit is technische documentatie, geen financieel advies en geen signaaldienst.\n\nDaan\n"),
    },
}


def bericht(cfg, aan, onderwerp, tekst):
    if not adres_geldig(aan):
        raise ValueError("ongeldig e-mailadres")
    m = email.message.EmailMessage()
    m["From"] = cfg.mail_van
    m["To"] = aan
    m["Subject"] = onderwerp
    m["Date"] = email.utils.formatdate(localtime=False)
    m["Message-ID"] = email.utils.make_msgid(domain=(cfg.mail_van.rsplit("@", 1)[-1].strip(">") or None))
    if cfg.mail_antwoord:
        m["Reply-To"] = cfg.mail_antwoord
    m.set_content(tekst)
    return m


class SmtpVerzender:
    """Verstuurt één bericht per verbinding (laag volume; een verbroken verbinding raakt zo maar één mail)."""

    def __init__(self, cfg):
        self.cfg = cfg

    def __call__(self, m):
        c = self.cfg
        if c.smtp_poort == 465:
            with smtplib.SMTP_SSL(c.smtp_host, c.smtp_poort, context=ssl.create_default_context(), timeout=30) as s:
                s.login(c.smtp_gebruiker, c.smtp_wachtwoord)
                s.send_message(m)
        else:
            with smtplib.SMTP(c.smtp_host, c.smtp_poort, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(c.smtp_gebruiker, c.smtp_wachtwoord)
                s.send_message(m)
