"""De logica, los van HTTP en SMTP (die worden erin gestoken, zodat de tests zonder netwerk draaien)."""
import json
import logging
import pathlib
import subprocess

from . import links, paddle, post
from .opslag import Opslag, nu

log = logging.getLogger("levering")
ABONNEE_STATUS = {"subscription.created", "subscription.activated", "subscription.updated", "subscription.canceled",
                  "subscription.past_due", "subscription.paused", "subscription.resumed"}


class Levering:
    def __init__(self, cfg, opslag=None, verzend=None, klant_ophalen=None):
        self.cfg = cfg
        self.opslag = opslag or Opslag(cfg.db)
        self.verzend = verzend or post.SmtpVerzender(cfg)
        self.klant_ophalen = klant_ophalen or (lambda cid: paddle.klant_email_ophalen(cid, cfg.paddle_api_url, cfg.paddle_api_sleutel))

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
        if not event_id or not soort:
            return 400, "event_id of event_type ontbreekt"
        if not self.opslag.event_nieuw(event_id, soort):
            return 200, "al verwerkt"
        try:
            self._verwerk(soort, data)
        except Exception:
            self.opslag.event_vergeet(event_id)  # Paddle probeert het opnieuw
            log.exception("event %s (%s) mislukt", event_id, soort)
            return 500, "verwerking mislukt"
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

    def _verwerk(self, soort, data):
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
                if self.opslag.aankoop_bewaar(data["id"], data.get("customer_id"), email, taal, "kit", versie["versie"]):
                    self.stuur_kit(email, taal, versie["versie"])
            if data.get("subscription_id"):  # eerste betaling of verlenging: einde periode bijwerken
                self.opslag.abonnee_bewaar(data["subscription_id"], data.get("customer_id"), email, taal, "active",
                                           paddle.periode_einde(data))
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
                # vanaf nu geen updates meer. Een opzegging die nog moet ingaan komt als subscription.updated met
                # scheduled_change binnen en laat de abonnee actief tot het einde van de betaalde periode.
                status, einde = "canceled", nu()
            self.opslag.abonnee_bewaar(data["id"], data.get("customer_id"), email, taal, status, einde)

    # ------------------------------------------------------------ mails
    def _link(self, email, versie, uren):
        return links.maak(self.opslag, self.cfg.geheim, email, versie, uren, self.cfg.max_downloads)

    def stuur_kit(self, email, taal, versie):
        link_id, token = self._link(email, versie, self.cfg.link_uur)
        t = post.TEKSTEN[taal]
        tekst = t["kit"].format(uur=self.cfg.link_uur, max=self.cfg.max_downloads, versie=versie,
                                link=f"{self.cfg.basis_url.rstrip('/')}/download/{token}")
        self.verzend(post.bericht(self.cfg, email, t["kit_onderwerp"], tekst))
        log.info("kit verzonden: %s versie %s link %s", email, versie, link_id)

    def send_update(self, versie, dry_run=False, uit=print):
        """Mailt elke actieve abonnee die deze versie nog niet kreeg. Idempotent: een verzonden (e-mail, versie) wordt
        overgeslagen; 'bezig' of 'mislukt' wordt opnieuw geprobeerd. Geeft een lijst (e-mail, uitkomst)."""
        v = self.opslag.versie(versie)
        if not v:
            raise SystemExit(f"versie {versie} is niet geregistreerd (python3 -m levering nieuwe-versie)")
        if not pathlib.Path(v["bestand"]).is_file():
            raise SystemExit(f"bestand van versie {versie} ontbreekt: {v['bestand']}")
        resultaat = []
        for a in self.opslag.actieve_abonnees():
            email = a["email"]
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
                link_id, token = self._link(email, versie, self.cfg.update_link_uur)
                t = post.TEKSTEN[a["taal"] or "en"]
                tekst = t["update"].format(versie=versie, changelog=v["changelog"] or "-", uur=self.cfg.update_link_uur,
                                           max=self.cfg.max_downloads, tot=a["actief_tot"][:10],
                                           link=f"{self.cfg.basis_url.rstrip('/')}/download/{token}")
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
        pad = pathlib.Path(v["bestand"]) if v else None
        if not pad or not pad.is_file():
            return None, "bestand ontbreekt"
        return pad, f"build-kit-v{rij['versie']}{pad.suffix}"


def maandrapport(opslag, bot_repo, git="git"):
    """Commits in de bot-repo sinds de laatste documentversie, zodat Claude kan beslissen of het document een update
    nodig heeft. Geeft markdown-tekst (naar stdout; niets wordt verstuurd of gewijzigd)."""
    v = opslag.versie()
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
    regels = [f"# Maandrapport bouwpakket", "", f"Bot-repo: {bot_repo}", f"Sinds: {sinds}", "",
              f"- {len(echt)} commits (zonder 'Published your App'), waarvan {len(geld)} in src/, .replit of requirements",
              "- Vraag voor Claude: verandert een van deze commits iets dat het bouwplan beschrijft (strategie, ladder,",
              "  verkoopregels, veiligheid, infrastructuur)? Zo ja: nieuwe versie schrijven, `nieuwe-versie`, dan `send-update`.",
              ""]
    for c in echt:
        merk = " **(src/config)**" if c in geld else ""
        regels.append(f"- {c['datum']} `{c['hash']}` {c['onderwerp']}{merk}")
    return "\n".join(regels) + "\n"
