"""SQLite-opslag. Eén bestand, één verbinding per handeling (de dienst is klein en het verkeer laag).

Tabellen
  events          verwerkte Paddle-events (event_id uniek: een tweede aflevering doet niets)
  klanten         customer_id -> e-mail, taal (uit customer.*-events of opgehaald via de Paddle-API)
  aankopen        één rij per betaalde transactie met de kit
  abonnees        één rij per Paddle-abonnement: status en 'actief_tot' (einde lopende periode)
  versies         documentversies: versie, bestand (buiten de webroot), datum, bot-commit, changelog
  links           downloadlinks: id, e-mail, versie, verloopt, max, aantal
  verzendingen    wie welke versie kreeg (e-mail + versie uniek): maakt send-update idempotent
"""
import contextlib
import datetime
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
"""


def nu():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lees_iso(s):
    if not s:
        return None
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)


class Opslag:
    def __init__(self, pad):
        self.pad = pad
        with self.verbind() as c:
            c.executescript(SCHEMA)

    @contextlib.contextmanager
    def verbind(self):
        c = sqlite3.connect(self.pad, timeout=30, isolation_level=None)  # autocommit; transacties expliciet
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            yield c
        finally:
            c.close()

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

    # --- aankopen en abonnees
    def aankoop_bewaar(self, transactie_id, customer_id, email, taal, product, versie):
        with self.verbind() as c:
            try:
                c.execute("INSERT INTO aankopen VALUES (?,?,?,?,?,?,?)",
                          (transactie_id, customer_id, email, taal, product, versie, iso(nu())))
                return True
            except sqlite3.IntegrityError:
                return False

    def abonnee_bewaar(self, abonnement_id, customer_id, email, taal, status, actief_tot):
        with self.verbind() as c:
            c.execute("INSERT INTO abonnees VALUES (?,?,?,?,?,?,?) ON CONFLICT(abonnement_id) DO UPDATE SET "
                      "customer_id=excluded.customer_id, email=COALESCE(excluded.email, abonnees.email), "
                      "taal=COALESCE(excluded.taal, abonnees.taal), status=excluded.status, "
                      "actief_tot=COALESCE(excluded.actief_tot, abonnees.actief_tot), bijgewerkt=excluded.bijgewerkt",
                      (abonnement_id, customer_id, email, taal, status, iso(actief_tot) if actief_tot else None, iso(nu())))

    def actieve_abonnees(self, moment=None):
        """Status active/past_due/trialing óf opgezegd maar nog binnen de betaalde periode, en actief_tot in de toekomst."""
        moment = moment or nu()
        with self.verbind() as c:
            rijen = c.execute("SELECT * FROM abonnees WHERE email IS NOT NULL").fetchall()
        uit, gezien = [], set()
        for r in rijen:
            tot = lees_iso(r["actief_tot"])
            if tot and tot > moment and r["status"] in ("active", "past_due", "trialing", "canceled", "paused"):
                if r["status"] == "paused":
                    continue
                if r["email"].lower() not in gezien:
                    gezien.add(r["email"].lower())
                    uit.append(r)
        return uit

    # --- versies
    def versie_bewaar(self, versie, bestand, bot_commit, changelog):
        with self.verbind() as c:
            c.execute("INSERT INTO versies VALUES (?,?,?,?,?) ON CONFLICT(versie) DO UPDATE SET bestand=excluded.bestand, "
                      "bot_commit=excluded.bot_commit, changelog=excluded.changelog", (versie, bestand, iso(nu()), bot_commit, changelog))

    def versie(self, versie=None):
        with self.verbind() as c:
            if versie:
                return c.execute("SELECT * FROM versies WHERE versie = ?", (versie,)).fetchone()
            return c.execute("SELECT * FROM versies ORDER BY datum DESC, rowid DESC LIMIT 1").fetchone()

    # --- links
    def link_bewaar(self, link_id, email, versie, verloopt, maximum):
        with self.verbind() as c:
            c.execute("INSERT INTO links (id, email, versie, verloopt, max, aantal, gemaakt) VALUES (?,?,?,?,?,0,?)",
                      (link_id, email, versie, iso(verloopt), maximum, iso(nu())))

    def link_gebruik(self, link_id, moment=None):
        """Telt één download op als de link bestaat, niet verlopen is en onder het maximum zit. Atomair.
        Geeft de rij terug, of (None, reden)."""
        moment = moment or nu()
        with self.verbind() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
            if not r:
                c.execute("ROLLBACK")
                return None, "onbekend"
            if lees_iso(r["verloopt"]) <= moment:
                c.execute("ROLLBACK")
                return None, "verlopen"
            if r["aantal"] >= r["max"]:
                c.execute("ROLLBACK")
                return None, "op"
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
