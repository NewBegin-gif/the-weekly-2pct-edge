"""SQLite-opslag. Eén bestand, één verbinding per handeling (de dienst is klein en het verkeer laag).

Tabellen
  events          verwerkte Paddle-events (event_id uniek: een tweede aflevering doet niets)
  klanten         customer_id -> e-mail, taal (uit customer.*-events of opgehaald via de Paddle-API)
  aankopen        één rij per betaalde transactie met de kit; status 'betaald', 'wacht_op_toestemming' (geen
                  vastgelegde EU-toestemming voor directe levering: niets geleverd tot `vrijgeven`) of 'teruggedraaid'
                  (refund/chargeback); 'toestemming' + 'toestemming_moment' leggen die toestemming vast
  abonnees        één rij per Paddle-abonnement: status, 'actief_tot' (einde lopende periode) en 'event_moment'
                  (occurred_at van het laatst toegepaste event: een ouder event dat later binnenkomt wordt genegeerd)
  versies         documentversies: versie, bestand (Engelse editie, buiten de webroot), bestand_nl (Nederlandse
                  editie; leeg = de Engelse voor iedereen), datum, bot-commit, changelog
  links           downloadlinks: id, e-mail, versie, taal (welke editie), verloopt, max, aantal, ingetrokken
  verzendingen    wie welke updateversie kreeg (e-mail + versie uniek): maakt send-update idempotent
  uitgaand        wachtrij voor de leveringsmail: een mislukte SMTP-poging blijft staan en wordt later opnieuw
                  geprobeerd (oplopende wachttijd, max. 6 uur), zodat een betaalde levering nooit verloren gaat
Een bestaande database krijgt nieuwe kolommen bij het openen (ALTER TABLE, alleen als ze ontbreken). Een nieuw
databasebestand krijgt rechten 600 (e-mailadressen); alle query's zijn geparametriseerd.
"""
import contextlib
import datetime
import os
import re
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, soort TEXT, ontvangen TEXT);
CREATE TABLE IF NOT EXISTS klanten (customer_id TEXT PRIMARY KEY, email TEXT, taal TEXT);
CREATE TABLE IF NOT EXISTS aankopen (transactie_id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, taal TEXT,
    product TEXT, versie TEXT, moment TEXT);
CREATE TABLE IF NOT EXISTS abonnees (abonnement_id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, taal TEXT,
    status TEXT, actief_tot TEXT, bijgewerkt TEXT);
CREATE TABLE IF NOT EXISTS versies (versie TEXT PRIMARY KEY, bestand TEXT, datum TEXT, bot_commit TEXT, changelog TEXT);
CREATE TABLE IF NOT EXISTS links (id TEXT PRIMARY KEY, email TEXT, versie TEXT, verloopt TEXT, max INTEGER,
    aantal INTEGER DEFAULT 0, gemaakt TEXT);
CREATE TABLE IF NOT EXISTS verzendingen (email TEXT, versie TEXT, status TEXT, link_id TEXT, moment TEXT,
    PRIMARY KEY (email, versie));
CREATE TABLE IF NOT EXISTS uitgaand (id INTEGER PRIMARY KEY AUTOINCREMENT, sleutel TEXT UNIQUE, soort TEXT,
    email TEXT, taal TEXT, versie TEXT, status TEXT, pogingen INTEGER DEFAULT 0, volgende TEXT, laatste_fout TEXT,
    gemaakt TEXT, verzonden TEXT);
"""
NIEUWE_KOLOMMEN = [("aankopen", "status", "TEXT DEFAULT 'betaald'"), ("aankopen", "subscription_id", "TEXT"),
                   ("abonnees", "event_moment", "TEXT"), ("links", "ingetrokken", "INTEGER DEFAULT 0"),
                   ("aankopen", "toestemming", "TEXT"), ("aankopen", "toestemming_moment", "TEXT"),
                   ("versies", "bestand_nl", "TEXT"), ("links", "taal", "TEXT")]
MAX_WACHT = datetime.timedelta(hours=6)
# Paddle wacht ~5 s op een antwoord; langer op een slot wachten heeft geen zin (Paddle probeert het later opnieuw).
SLOT_WACHT_SEC = 4
VERSIE = re.compile(r"[0-9A-Za-z][0-9A-Za-z.\-]{0,19}")  # komt in een bestandsnaam en een Content-Disposition-kop
ACTIEF = ("active", "trialing", "canceled")  # past_due = verlenging niet betaald: geen nieuwe updates tot betaling


def nu():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lees_iso(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00")
    if "." in s:  # Paddle geeft microseconden: 2026-11-01T12:00:00.123456Z
        hoofd, _, rest = s.partition(".")
        zone = rest[next((i for i, ch in enumerate(rest) if ch in "+-"), len(rest)):]
        s = hoofd + zone
    return datetime.datetime.fromisoformat(s).astimezone(datetime.timezone.utc)


class Opslag:
    def __init__(self, pad):
        self.pad = pad
        if pad != ":memory:" and not os.path.exists(pad):
            os.close(os.open(pad, os.O_CREAT | os.O_WRONLY, 0o600))
        with self.verbind() as c:
            c.executescript(SCHEMA)
            for tabel, kolom, soort in NIEUWE_KOLOMMEN:
                bestaand = {r["name"] for r in c.execute(f"PRAGMA table_info({tabel})")}
                if kolom not in bestaand:
                    c.execute(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {soort}")

    @contextlib.contextmanager
    def verbind(self):
        c = sqlite3.connect(self.pad, timeout=SLOT_WACHT_SEC, isolation_level=None)  # autocommit; transacties expliciet
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(f"PRAGMA busy_timeout={SLOT_WACHT_SEC * 1000}")
            yield c
        finally:
            c.close()

    def gezond(self):
        try:
            with self.verbind() as c:
                return c.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    # --- events
    def event_nieuw(self, event_id, soort):
        """True als dit event nog niet verwerkt is (en markeert het als verwerkt)."""
        with self.verbind() as c:
            try:
                c.execute("INSERT INTO events VALUES (?,?,?)", (event_id, soort, iso(nu())))
                return True
            except sqlite3.IntegrityError:
                return False

    def event_vergeet(self, event_id):
        """Bij een fout tijdens verwerking: Paddle probeert opnieuw, dus het event mag dan weer binnenkomen."""
        with self.verbind() as c:
            c.execute("DELETE FROM events WHERE event_id = ?", (event_id,))

    # --- klanten
    def klant_bewaar(self, customer_id, email, taal=None):
        with self.verbind() as c:
            c.execute("INSERT INTO klanten VALUES (?,?,?) ON CONFLICT(customer_id) DO UPDATE SET email=excluded.email, "
                      "taal=COALESCE(excluded.taal, klanten.taal)", (customer_id, email, taal))

    def klant(self, customer_id):
        with self.verbind() as c:
            return c.execute("SELECT * FROM klanten WHERE customer_id = ?", (customer_id,)).fetchone()

    # --- aankopen
    def aankoop_bewaar(self, transactie_id, customer_id, email, taal, product, versie, subscription_id=None,
                       toestemming=None, toestemming_moment=None, status="betaald"):
        with self.verbind() as c:
            try:
                c.execute("INSERT INTO aankopen (transactie_id, customer_id, email, taal, product, versie, moment, status, "
                          "subscription_id, toestemming, toestemming_moment) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (transactie_id, customer_id, email, taal, product, versie, iso(nu()), status, subscription_id,
                           toestemming, iso(toestemming_moment) if toestemming_moment else None))
                return True
            except sqlite3.IntegrityError:
                return False

    def aankoop_vrijgeven(self, transactie_id, toestemming, moment=None):
        """Een aankoop die op toestemming wachtte alsnog op 'betaald' zetten (toestemming kwam later, bv. per mail).
        Geeft True als dat gebeurde; een teruggedraaide aankoop blijft teruggedraaid."""
        with self.verbind() as c:
            return bool(c.execute("UPDATE aankopen SET status='betaald', toestemming=?, toestemming_moment=? "
                                  "WHERE transactie_id=? AND status='wacht_op_toestemming'",
                                  (toestemming, iso(moment or nu()), transactie_id)).rowcount)

    def aankopen_zonder_toestemming(self):
        with self.verbind() as c:
            return c.execute("SELECT * FROM aankopen WHERE status='wacht_op_toestemming' ORDER BY moment").fetchall()

    def aankoop(self, transactie_id):
        with self.verbind() as c:
            return c.execute("SELECT * FROM aankopen WHERE transactie_id = ?", (transactie_id,)).fetchone()

    def aankoop_terugdraaien(self, transactie_id, email=None, customer_id=None):
        """Zet de aankoop op 'teruggedraaid'. Bestaat hij nog niet (de refund kwam vóór transaction.completed binnen),
        dan komt er een rij met die status, zodat de latere transaction.completed niets meer levert."""
        with self.verbind() as c:
            if not c.execute("UPDATE aankopen SET status = 'teruggedraaid' WHERE transactie_id = ?", (transactie_id,)).rowcount:
                c.execute("INSERT INTO aankopen (transactie_id, customer_id, email, product, moment, status) "
                          "VALUES (?,?,?, 'kit', ?, 'teruggedraaid')", (transactie_id, customer_id, email, iso(nu())))

    def teruggedraaide_emails(self):
        with self.verbind() as c:
            return {r["email"].lower() for r in c.execute("SELECT email FROM aankopen WHERE status = 'teruggedraaid'")
                    if r["email"]}

    # --- abonnees
    def abonnee_bewaar(self, abonnement_id, customer_id, email, taal, status, actief_tot, moment=None):
        """Past een abonnementsevent toe, tenzij er al een nieuwer event is toegepast (Paddle garandeert de volgorde
        niet). 'revoked' (na refund/chargeback) blijft staan. Geeft True als er iets veranderde."""
        moment = moment or nu()
        with self.verbind() as c:
            c.execute("BEGIN IMMEDIATE")
            oud = c.execute("SELECT * FROM abonnees WHERE abonnement_id = ?", (abonnement_id,)).fetchone()
            if oud is not None:
                vorige = lees_iso(oud["event_moment"])
                if (vorige and moment < vorige) or oud["status"] == "revoked":
                    c.execute("ROLLBACK")
                    return False
                c.execute("UPDATE abonnees SET customer_id=COALESCE(?, customer_id), email=COALESCE(?, email), "
                          "taal=COALESCE(?, taal), status=?, actief_tot=COALESCE(?, actief_tot), bijgewerkt=?, "
                          "event_moment=? WHERE abonnement_id=?",
                          (customer_id, email, taal, status, iso(actief_tot) if actief_tot else None, iso(nu()),
                           iso(moment), abonnement_id))
            else:
                c.execute("INSERT INTO abonnees (abonnement_id, customer_id, email, taal, status, actief_tot, bijgewerkt, "
                          "event_moment) VALUES (?,?,?,?,?,?,?,?)",
                          (abonnement_id, customer_id, email, taal, status, iso(actief_tot) if actief_tot else None,
                           iso(nu()), iso(moment)))
            c.execute("COMMIT")
            return True

    def abonnee_intrekken(self, abonnement_id=None, email=None):
        with self.verbind() as c:
            if abonnement_id:
                c.execute("UPDATE abonnees SET status='revoked', bijgewerkt=? WHERE abonnement_id=?", (iso(nu()), abonnement_id))
            if email:
                c.execute("UPDATE abonnees SET status='revoked', bijgewerkt=? WHERE lower(email)=lower(?)", (iso(nu()), email))

    def actieve_abonnees(self, moment=None):
        """Status active/trialing óf opgezegd maar nog binnen de betaalde periode (niet past_due), actief_tot in de toekomst,
        niet ingetrokken en zonder teruggedraaide aankoop op hetzelfde e-mailadres."""
        moment = moment or nu()
        geblokkeerd = self.teruggedraaide_emails()
        with self.verbind() as c:
            rijen = c.execute("SELECT * FROM abonnees WHERE email IS NOT NULL").fetchall()
        uit, gezien = [], set()
        for r in rijen:
            tot = lees_iso(r["actief_tot"])
            mail = r["email"].lower()
            if (tot and tot > moment and r["status"] in ACTIEF
                    and mail not in geblokkeerd and mail not in gezien):
                gezien.add(mail)
                uit.append(r)
        return uit

    def alle_abonnees(self):
        with self.verbind() as c:
            return c.execute("SELECT * FROM abonnees ORDER BY bijgewerkt").fetchall()

    # --- versies
    def versie_bewaar(self, versie, bestand, bot_commit, changelog, bestand_nl=None):
        if not VERSIE.fullmatch(versie or ""):
            raise ValueError("versie: alleen letters, cijfers, punt en streepje (max. 20), bv. 1.1")
        with self.verbind() as c:
            c.execute("INSERT INTO versies (versie, bestand, datum, bot_commit, changelog, bestand_nl) VALUES (?,?,?,?,?,?) "
                      "ON CONFLICT(versie) DO UPDATE SET bestand=excluded.bestand, bot_commit=excluded.bot_commit, "
                      "changelog=excluded.changelog, bestand_nl=excluded.bestand_nl",
                      (versie, bestand, iso(nu()), bot_commit, changelog, bestand_nl))

    def versie(self, versie=None):
        with self.verbind() as c:
            if versie:
                return c.execute("SELECT * FROM versies WHERE versie = ?", (versie,)).fetchone()
            return c.execute("SELECT * FROM versies ORDER BY datum DESC, rowid DESC LIMIT 1").fetchone()

    # --- links
    def link_bewaar(self, link_id, email, versie, verloopt, maximum, taal=None):
        with self.verbind() as c:
            c.execute("INSERT INTO links (id, email, versie, verloopt, max, aantal, gemaakt, ingetrokken, taal) "
                      "VALUES (?,?,?,?,?,0,?,0,?)", (link_id, email, versie, iso(verloopt), maximum, iso(nu()), taal))

    def links_intrekken(self, email):
        with self.verbind() as c:
            return c.execute("UPDATE links SET ingetrokken = 1 WHERE lower(email) = lower(?)", (email,)).rowcount

    def link_gebruik(self, link_id, moment=None):
        """Telt één download op als de link bestaat, niet ingetrokken of verlopen is en onder het maximum zit.
        Atomair (BEGIN IMMEDIATE): gelijktijdige verzoeken kunnen samen nooit boven het maximum komen.
        Geeft (rij, None) of (None, reden)."""
        moment = moment or nu()
        with self.verbind() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
            reden = ("onbekend" if not r else "ingetrokken" if r["ingetrokken"] else
                     "verlopen" if lees_iso(r["verloopt"]) <= moment else "op" if r["aantal"] >= r["max"] else None)
            if reden:
                c.execute("ROLLBACK")
                return None, reden
            c.execute("UPDATE links SET aantal = aantal + 1 WHERE id = ?", (link_id,))
            c.execute("COMMIT")
            return r, None

    # --- verzendingen (idempotentie van send-update)
    def verzending(self, email, versie):
        with self.verbind() as c:
            return c.execute("SELECT * FROM verzendingen WHERE email = ? AND versie = ?", (email.lower(), versie)).fetchone()

    def verzending_bewaar(self, email, versie, status, link_id=None):
        with self.verbind() as c:
            c.execute("INSERT INTO verzendingen VALUES (?,?,?,?,?) ON CONFLICT(email, versie) DO UPDATE SET "
                      "status=excluded.status, link_id=COALESCE(excluded.link_id, verzendingen.link_id), moment=excluded.moment",
                      (email.lower(), versie, status, link_id, iso(nu())))

    # --- uitgaand (wachtrij leveringsmail)
    def uitgaand_toevoegen(self, sleutel, soort, email, taal, versie):
        """Idempotent op sleutel (de transactie): een tweede aflevering zet niets dubbel in de rij."""
        with self.verbind() as c:
            try:
                c.execute("INSERT INTO uitgaand (sleutel, soort, email, taal, versie, status, pogingen, volgende, gemaakt) "
                          "VALUES (?,?,?,?,?, 'wacht', 0, ?, ?)", (sleutel, soort, email, taal, versie, iso(nu()), iso(nu())))
                return True
            except sqlite3.IntegrityError:
                return False

    def uitgaand_klaar(self, moment=None):
        with self.verbind() as c:
            return c.execute("SELECT * FROM uitgaand WHERE status = 'wacht' AND volgende <= ? ORDER BY id",
                             (iso(moment or nu()),)).fetchall()

    def uitgaand_alle(self):
        with self.verbind() as c:
            return c.execute("SELECT * FROM uitgaand ORDER BY id").fetchall()

    def uitgaand_verzonden(self, rij_id):
        with self.verbind() as c:
            c.execute("UPDATE uitgaand SET status='verzonden', verzonden=?, laatste_fout=NULL WHERE id=?", (iso(nu()), rij_id))

    def uitgaand_mislukt(self, rij_id, fout):
        """Volgende poging na 5, 10, 20, ... minuten, hooguit 6 uur; de rij blijft altijd 'wacht'."""
        with self.verbind() as c:
            r = c.execute("SELECT pogingen FROM uitgaand WHERE id=?", (rij_id,)).fetchone()
            pogingen = (r["pogingen"] if r else 0) + 1
            wacht = min(datetime.timedelta(minutes=5 * 2 ** (pogingen - 1)), MAX_WACHT)
            c.execute("UPDATE uitgaand SET pogingen=?, volgende=?, laatste_fout=? WHERE id=?",
                      (pogingen, iso(nu() + wacht), str(fout)[:300], rij_id))

    def uitgaand_ongeldig(self, rij_id):
        """Een adres dat nooit te mailen is: niet eindeloos opnieuw proberen (handmatig oplossen, zie `aankopen`)."""
        with self.verbind() as c:
            c.execute("UPDATE uitgaand SET status='ongeldig_adres', laatste_fout='ongeldig e-mailadres' WHERE id=?", (rij_id,))

    def uitgaand_annuleren(self, email):
        with self.verbind() as c:
            c.execute("UPDATE uitgaand SET status='geannuleerd' WHERE status='wacht' AND lower(email)=lower(?)", (email,))
