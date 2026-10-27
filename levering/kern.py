"""De logica, los van HTTP en SMTP (die worden erin gestoken, zodat de tests zonder netwerk draaien).

Robuustheid
  - Herhaalde aflevering: elk event_id één keer (events-tabel); dezelfde transactie onder een ander event_id geeft
    geen tweede aankoop of mail (aankopen + uitgaand zijn uniek op de transactie).
  - Volgorde: Paddle garandeert de volgorde van events niet. Abonnementswijzigingen dragen het occurred_at van het
    event; een ouder event dat na een nieuwer binnenkomt wordt genegeerd (opslag.abonnee_bewaar).
  - Refund / chargeback (adjustment.created / adjustment.updated): een goedgekeurde refund of elke chargeback trekt
    alle downloadlinks van dat e-mailadres in, annuleert wachtende leveringsmails, zet abonnementen op 'revoked' en
    sluit het adres uit van updates. Een gedeeltelijke refund telt ook (voorzichtig: bij twijfel geen updates);
    een chargeback_reverse herstelt niets automatisch (handmatig, zie PR).
  - SMTP-fout: de leveringsmail staat eerst in de wachtrij 'uitgaand' en wordt pas na een gelukte verzending
    afgevinkt; de webhook antwoordt 200 (de aankoop is vastgelegd), de dienst probeert het elke LEVERING_WACHTRIJ_SEC
    opnieuw met oplopende wachttijd, en `python3 -m levering wachtrij` doet het direct. Niets gaat verloren.
    In de dienst verstuurt een achtergronddraad de mail (mail_wekker): de webhook wacht nooit op SMTP, want Paddle
    wil binnen enkele seconden antwoord. Een adres dat nooit te mailen is ('ongeldig_adres') wordt niet herhaald.
  - EU-herroepingsrecht (richtlijn 2011/83/EU art. 16(m)): de kit wordt alleen geleverd als de transactie de
    toestemming uit het afrekenvinkje draagt (custom_data.withdrawal_consent, gezet door de koopknop, zie
    bouw/w2e_kassa.py). Versie en tijdstip van die toestemming staan in aankopen. Zonder: status
    'wacht_op_toestemming', geen mail; `python3 -m levering aankopen` toont ze, `vrijgeven` levert na toestemming.
  - Database op slot of weg: de webhook antwoordt 503 (Paddle probeert het later opnieuw), nooit een half event.
"""
import csv
import datetime
import json
import os
import logging
import pathlib
import re
import sqlite3
import subprocess

from . import links, paddle, post
from .opslag import Opslag, lees_iso, nu

log = logging.getLogger("levering")
ABONNEE_STATUS = {"subscription.created", "subscription.activated", "subscription.updated", "subscription.canceled",
                  "subscription.past_due", "subscription.paused", "subscription.resumed"}
TERUG = {"adjustment.created", "adjustment.updated"}
TOESTEMMING = re.compile(r"[A-Za-z0-9.\-]{1,40}")


def toestemming_uit(data, moment):
    """(versie, tijdstip) van de herroepingstoestemming in custom_data, of (None, None). Een onleesbaar of toekomstig
    tijdstip wordt vervangen door het moment van het event (de toestemming ging aan de betaling vooraf)."""
    cd = data.get("custom_data") or {}
    versie = cd.get("withdrawal_consent") if isinstance(cd, dict) else None
    if not isinstance(versie, str) or not TOESTEMMING.fullmatch(versie):
        return None, None
    try:
        wanneer = lees_iso(cd.get("consent_at"))
    except (TypeError, ValueError):
        wanneer = None
    if not wanneer or wanneer > nu() + datetime.timedelta(minutes=5):
        wanneer = moment
    return versie, wanneer


class Levering:
    def __init__(self, cfg, opslag=None, verzend=None, klant_ophalen=None):
        self.cfg = cfg
        self.opslag = opslag or Opslag(cfg.db)
        self.verzend = verzend or post.SmtpVerzender(cfg)
        self.klant_ophalen = klant_ophalen or (lambda cid: paddle.klant_email_ophalen(cid, cfg.paddle_api_url, cfg.paddle_api_sleutel))
        self.mail_wekker = None  # threading.Event van de wachtrij-draad (dienst.py); None = meteen zelf versturen

    # ------------------------------------------------------------ webhook
    def webhook(self, body, kop, nu_ts=None):
        """Controleert de handtekening en verwerkt het event. Geeft (http_status, tekst)."""
        try:
            paddle.controleer_handtekening(kop, body, self.cfg.paddle_geheim, self.cfg.paddle_tolerantie, nu_ts)
        except paddle.OngeldigeHandtekening as fout:
            log.warning("webhook geweigerd: %s", fout)
            return 401, "ongeldige handtekening"
        try:
            event = json.loads(body)
        except ValueError:
            return 400, "geen JSON"
        event_id, soort, data = event.get("event_id"), event.get("event_type"), event.get("data") or {}
        if not isinstance(event, dict) or not event.get("event_id") or not event.get("event_type"):
            return 400, "event_id of event_type ontbreekt"
        event_id, soort, data = str(event["event_id"]), str(event["event_type"]), event.get("data") or {}
        try:
            if not self.opslag.event_nieuw(event_id, soort):
                return 200, "al verwerkt"
        except sqlite3.Error as fout:
            log.error("database niet beschikbaar voor event %s: %s", event_id, fout)
            return 503, "probeer later opnieuw"
        try:
            self._verwerk(soort, data, lees_iso(event.get("occurred_at")) or nu())
        except Exception as fout:
            try:
                self.opslag.event_vergeet(event_id)  # Paddle probeert het opnieuw
            except sqlite3.Error:
                log.error("event %s kon niet worden vrijgegeven", event_id)
            log.exception("event %s (%s) mislukt", event_id, soort)
            return (503, "probeer later opnieuw") if isinstance(fout, sqlite3.Error) else (500, "verwerking mislukt")
        if self.mail_wekker is not None:
            self.mail_wekker.set()  # de wachtrij-draad verstuurt; Paddle krijgt meteen antwoord
        else:
            self.wachtrij()  # opdrachtregel/tests: meteen; mislukt het, dan blijft hij in de rij
        return 200, "ok"

    def _klant(self, customer_id):
        r = self.opslag.klant(customer_id) if customer_id else None
        if r and r["email"]:
            return r["email"], r["taal"]
        email, taal = self.klant_ophalen(customer_id) if customer_id else (None, None)
        if email:
            self.opslag.klant_bewaar(customer_id, email, taal)
        return email, taal

    def _producten(self, data):
        return [self.cfg.prijzen[p] for p in paddle.prijzen(data) if p in self.cfg.prijzen]

    def _verwerk(self, soort, data, moment):
        if soort in ("customer.created", "customer.updated"):
            if data.get("id") and data.get("email"):
                self.opslag.klant_bewaar(data["id"], data["email"], paddle._taal(data.get("locale")))
            return
        if soort == "transaction.completed":
            producten = self._producten(data)
            email, taal = self._klant(data.get("customer_id"))
            if not email:
                raise RuntimeError(f"geen e-mailadres bij customer {data.get('customer_id')}")
            taal = next((t for p, t in producten), None) or taal or "en"  # de prijs bepaalt de site, dus de taal
            if any(p == "kit" for p, _ in producten) and data.get("origin") != "subscription_recurring":
                versie = self.opslag.versie()
                if not versie:
                    raise RuntimeError("geen documentversie geregistreerd (python3 -m levering nieuwe-versie)")
                toestemming, wanneer = toestemming_uit(data, moment)
                self.opslag.aankoop_bewaar(data["id"], data.get("customer_id"), email, taal, "kit", versie["versie"],
                                           data.get("subscription_id"), toestemming, wanneer,
                                           "betaald" if toestemming else "wacht_op_toestemming")
                if not toestemming:
                    log.warning("transactie %s zonder herroepingstoestemming: niet geleverd (zie `aankopen`)", data["id"])
                aankoop = self.opslag.aankoop(data["id"])
                if aankoop["status"] == "betaald":
                    self.opslag.uitgaand_toevoegen(data["id"], "kit", email, taal, aankoop["versie"])
            if data.get("subscription_id"):  # eerste betaling of verlenging: einde periode bijwerken
                self.opslag.abonnee_bewaar(data["subscription_id"], data.get("customer_id"), email, taal, "active",
                                           paddle.periode_einde(data), moment)
            return
        if soort in ABONNEE_STATUS:
            if not any(p == "updates" for p, _ in self._producten(data)) and self.cfg.prijzen:
                return  # een abonnement op iets anders dan updates
            email, taal = self._klant(data.get("customer_id"))
            producten = self._producten(data)
            taal = next((t for p, t in producten), None) or taal or "en"
            einde = paddle.periode_einde(data)
            status = data.get("status") or soort.split(".")[1]
            if soort == "subscription.canceled":
                # Paddle stuurt dit pas als de opzegging ingaat (bij opzeggen per periode-einde: op dat einde), dus
                # vanaf het event geen updates meer. Een opzegging die nog moet ingaan komt als subscription.updated
                # met scheduled_change binnen en laat de abonnee actief tot het einde van de betaalde periode.
                status, einde = "canceled", min(moment, nu())
            self.opslag.abonnee_bewaar(data["id"], data.get("customer_id"), email, taal, status, einde, moment)
            return
        if soort in TERUG:
            self._terugdraaien(data)

    def _terugdraaien(self, data):
        actie, status = data.get("action"), data.get("status")
        if not ((actie == "refund" and status == "approved") or actie == "chargeback"):
            log.info("adjustment %s/%s voor %s: geen actie", actie, status, data.get("transaction_id"))
            return
        txn = data.get("transaction_id")
        aankoop = self.opslag.aankoop(txn) if txn else None
        email = aankoop["email"] if aankoop else self._klant(data.get("customer_id"))[0]
        if txn:
            self.opslag.aankoop_terugdraaien(txn, email, data.get("customer_id"))
        if email:
            n = self.opslag.links_intrekken(email)
            self.opslag.uitgaand_annuleren(email)
            self.opslag.abonnee_intrekken(email=email)
            log.warning("%s op %s: %s links ingetrokken, updates gestopt voor %s", actie, txn, n, email)
        if data.get("subscription_id"):
            self.opslag.abonnee_intrekken(abonnement_id=data["subscription_id"])

    def vrijgeven(self, transactie_id, toestemming):
        """Levert een aankoop die op toestemming wachtte, nadat de koper die alsnog gaf (bv. per mail). Geeft True als
        er iets in de wachtrij kwam."""
        if not self.opslag.aankoop_vrijgeven(transactie_id, toestemming):
            return False
        a = self.opslag.aankoop(transactie_id)
        return self.opslag.uitgaand_toevoegen(transactie_id, "kit", a["email"], a["taal"] or "en", a["versie"])

    # ------------------------------------------------------------ mails
    def _link(self, email, taal, versie, uren):
        link_id, token = links.maak(self.opslag, self.cfg.geheim, email, versie, uren, self.cfg.max_downloads, taal=taal)
        return link_id, f"{self.cfg.basis_url(taal)}/download/{token}"

    def wachtrij(self):
        """Verstuurt elke leveringsmail die aan de beurt is. Geeft (verzonden, mislukt)."""
        ok = fout = 0
        for r in self.opslag.uitgaand_klaar():
            if not post.adres_geldig(r["email"]):
                self.opslag.uitgaand_ongeldig(r["id"])
                log.error("leveringsmail %s: ongeldig e-mailadres, niet verstuurd (handmatig oplossen)", r["sleutel"])
                fout += 1
                continue
            try:
                taal = r["taal"] if r["taal"] in post.TEKSTEN else "en"
                link_id, url = self._link(r["email"], taal, r["versie"], self.cfg.link_uur)
                t = post.TEKSTEN[taal]
                tekst = t["kit"].format(uur=self.cfg.link_uur, max=self.cfg.max_downloads, versie=r["versie"], link=url)
                self.verzend(post.bericht(self.cfg, r["email"], t["kit_onderwerp"], tekst))
            except Exception as e:
                self.opslag.uitgaand_mislukt(r["id"], e)
                log.warning("leveringsmail %s naar %s mislukt (blijft in de rij): %s", r["sleutel"], r["email"], e)
                fout += 1
                continue
            self.opslag.uitgaand_verzonden(r["id"])
            log.info("kit verzonden: %s versie %s link %s", r["email"], r["versie"], link_id)
            ok += 1
        return ok, fout

    def send_update(self, versie, dry_run=False, uit=print):
        """Mailt elke actieve abonnee die deze versie nog niet kreeg. Idempotent: een verzonden (e-mail, versie) wordt
        overgeslagen; 'bezig' of 'mislukt' wordt opnieuw geprobeerd. Geeft een lijst (e-mail, uitkomst)."""
        v = self.opslag.versie(versie)
        if not v:
            raise SystemExit(f"versie {versie} is niet geregistreerd (python3 -m levering nieuwe-versie)")
        for b in (v["bestand"], v["bestand_nl"]):
            if b and not pathlib.Path(b).is_file():
                raise SystemExit(f"bestand van versie {versie} ontbreekt: {b}")
        resultaat = []
        for a in self.opslag.actieve_abonnees():
            email = a["email"]
            if not post.adres_geldig(email):
                resultaat.append((email, "mislukt: ongeldig e-mailadres"))
                continue
            eerder = self.opslag.verzending(email, versie)
            if eerder and eerder["status"] == "verzonden":
                resultaat.append((email, "al eerder verzonden"))
                continue
            if dry_run:
                resultaat.append((email, "zou verzonden worden"))
                uit(f"[dry-run] {email} ({a['taal'] or 'en'}) krijgt versie {versie}")
                continue
            self.opslag.verzending_bewaar(email, versie, "bezig")
            try:
                taal = a["taal"] if a["taal"] in post.TEKSTEN else "en"
                link_id, url = self._link(email, taal, versie, self.cfg.update_link_uur)
                t = post.TEKSTEN[taal]
                tekst = t["update"].format(versie=versie, changelog=v["changelog"] or "-", uur=self.cfg.update_link_uur,
                                           max=self.cfg.max_downloads, tot=a["actief_tot"][:10], link=url)
                self.verzend(post.bericht(self.cfg, email, t["update_onderwerp"].format(versie=versie), tekst))
            except Exception as fout:
                self.opslag.verzending_bewaar(email, versie, "mislukt")
                resultaat.append((email, f"mislukt: {fout}"))
                uit(f"MISLUKT {email} versie {versie}: {fout}")
                continue
            self.opslag.verzending_bewaar(email, versie, "verzonden", link_id)
            resultaat.append((email, "verzonden"))
            uit(f"verzonden: {email} versie {versie} (link {link_id})")
            log.info("update verzonden: %s versie %s link %s", email, versie, link_id)
        return resultaat

    # ------------------------------------------------------------ download
    def download(self, token):
        """(pad, bestandsnaam) of (None, reden)."""
        link_id, reden = links.controleer(token, self.cfg.geheim)
        if not link_id:
            return None, reden
        rij, reden = self.opslag.link_gebruik(link_id)
        if not rij:
            return None, reden
        v = self.opslag.versie(rij["versie"])
        nl = bool(v and rij["taal"] == "nl" and v["bestand_nl"])  # zonder Nederlandse editie: de Engelse
        pad = pathlib.Path(v["bestand_nl"] if nl else v["bestand"]) if v else None
        if not pad or not pad.is_file():
            return None, "bestand ontbreekt"
        return pad, f"{'bouwpakket' if nl else 'build-kit'}-v{rij['versie']}{pad.suffix}"


VERBODEN_EXPORT = ("/var/www", "/srv/www", "/usr/share/nginx")


def export_abonnees(opslag, doel, rijen=None):
    """Schrijft alle abonnees (ook beëindigde) naar CSV voor de boekhouding, met bestandsrechten 600. Weigert een pad
    in een webroot of in deze repo: het bestand bevat e-mailadressen en mag nooit geserveerd worden."""
    doel = pathlib.Path(doel).expanduser().resolve()
    repo = pathlib.Path(__file__).resolve().parent.parent
    if any(str(doel).startswith(p) for p in VERBODEN_EXPORT) or repo in doel.parents:
        raise SystemExit(f"weigert {doel}: dat is (mogelijk) publiek. Kies bv. /root/boekhouding/abonnees.csv")
    doel.parent.mkdir(parents=True, exist_ok=True)
    rijen = opslag.alle_abonnees() if rijen is None else rijen
    with open(doel, "w", newline="", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as f:
        w = csv.writer(f)
        w.writerow(["abonnement_id", "customer_id", "email", "taal", "status", "actief_tot", "bijgewerkt"])
        for r in rijen:
            w.writerow([r["abonnement_id"], r["customer_id"], r["email"], r["taal"], r["status"], r["actief_tot"],
                        r["bijgewerkt"]])
    return doel, len(rijen)


def maandrapport(opslag, bot_repo, git="git", versie=None):
    """Commits in de bot-repo sinds de laatste documentversie, zodat Claude kan beslissen of het document een update
    nodig heeft. Geeft markdown-tekst (naar stdout; niets wordt verstuurd of gewijzigd). Zonder opslag: de meegegeven
    versie-rij (de opdrachtregel leest die als dienstgebruiker en draait git als root)."""
    v = opslag.versie() if opslag is not None else versie
    if v and v["bot_commit"]:
        bereik, sinds = [f"{v['bot_commit']}..HEAD"], f"commit {v['bot_commit'][:10]} (versie {v['versie']}, {v['datum'][:10]})"
    elif v:
        bereik, sinds = [f"--since={v['datum']}"], f"{v['datum'][:10]} (versie {v['versie']})"
    else:
        bereik, sinds = ["--since=31 days ago"], "de laatste 31 dagen (nog geen documentversie geregistreerd)"
    uitvoer = subprocess.run([git, "-C", str(bot_repo), "log", "--no-merges", "--date=short",
                              "--format=%h%x09%ad%x09%s", "--name-only", *bereik],
                             capture_output=True, text=True, check=True).stdout
    commits, huidig = [], None
    for regel in uitvoer.splitlines():
        if "\t" in regel:
            h, d, s = regel.split("\t", 2)
            huidig = {"hash": h, "datum": d, "onderwerp": s, "bestanden": []}
            commits.append(huidig)
        elif regel.strip() and huidig:
            huidig["bestanden"].append(regel.strip())
    echt = [c for c in commits if not c["onderwerp"].startswith("Published your App")]
    geld = [c for c in echt if any(b.startswith(("src/", ".replit", "requirements")) for b in c["bestanden"])]
    regels = ["# Maandrapport bouwpakket", "", f"Bot-repo: {bot_repo}", f"Sinds: {sinds}", "",
              f"- {len(echt)} commits (zonder 'Published your App'), waarvan {len(geld)} in src/, .replit of requirements",
              "- Vraag voor Claude: verandert een van deze commits iets dat het bouwplan beschrijft (strategie, ladder,",
              "  verkoopregels, veiligheid, infrastructuur)? Zo ja: nieuwe versie schrijven, `nieuwe-versie`, dan `send-update`.",
              ""]
    for c in echt:
        merk = " **(src/config)**" if c in geld else ""
        regels.append(f"- {c['datum']} `{c['hash']}` {c['onderwerp']}{merk}")
    return "\n".join(regels) + "\n"
