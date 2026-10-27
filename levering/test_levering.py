"""Tests: python3 -m unittest levering.test_levering (vanaf de repo-root). Geen netwerk, geen SMTP: een nep-verzender
vangt de berichten op, en een tijdelijke SQLite-database per test."""
import csv
import datetime
import http.client
import json
import pathlib
import sys
import tempfile
import threading
import time
import unittest

sys.dont_write_bytecode = True

from levering import links, paddle  # noqa: E402
from levering.dienst import maak_server  # noqa: E402
from levering.instellingen import Instellingen  # noqa: E402
from levering.kern import Levering, export_abonnees  # noqa: E402
from levering.opslag import Opslag, iso  # noqa: E402

GEHEIM = "whsec_test"
UTC = datetime.timezone.utc


def moment(dagen):
    return iso(datetime.datetime.now(UTC) + datetime.timedelta(days=dagen))


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.doc = d / "build-kit-v1.0.pdf"
        self.doc.write_bytes(b"%PDF-1.4 test")
        self.cfg = Instellingen(db=str(d / "t.db"), documenten=str(d), geheim="linkgeheim-test",
                                basis_url_en="https://en.test", basis_url_nl="https://nl.test",
                                paddle_geheim=GEHEIM, smtp_host="x", mail_van="Daan <kit@voorbeeld.test>",
                                prijzen={"pri_kit_usd": ("kit", "en"), "pri_kit_eur": ("kit", "nl"),
                                         "pri_upd_usd": ("updates", "en"), "pri_upd_eur": ("updates", "nl")})
        self.opslag = Opslag(self.cfg.db)
        self.opslag.versie_bewaar("1.0", str(self.doc), "abc123", "Eerste versie")
        self.post = []
        self.lev = Levering(self.cfg, self.opslag, verzend=self.post.append, klant_ophalen=lambda cid: (None, None))

    def tearDown(self):
        self.tmp.cleanup()

    def stuur(self, event):
        body = json.dumps(event).encode()
        return self.lev.webhook(body, paddle.teken(body, GEHEIM))

    def transactie(self, event_id="evt_t1", txn="txn_1", prijzen=("pri_kit_usd",), origin="web", sub=None,
                   toestemming=True):
        return {"event_id": event_id, "event_type": "transaction.completed", "occurred_at": moment(0),
                "data": {"id": txn, "customer_id": "ctm_1", "origin": origin, "subscription_id": sub,
                         "items": [{"price": {"id": p}} for p in prijzen],
                         "custom_data": {"withdrawal_consent": "en-2026-10-27", "consent_at": moment(0)}
                         if toestemming else None,
                         "billing_period": {"ends_at": moment(365)} if sub else None}}

    def abonnement(self, event_id, soort, status, wanneer, ends_at=None):
        return {"event_id": event_id, "event_type": soort, "occurred_at": wanneer,
                "data": {"id": "sub_1", "customer_id": "ctm_1", "status": status,
                         "items": [{"price": {"id": "pri_upd_usd"}}],
                         "current_billing_period": {"ends_at": ends_at} if ends_at else None}}

    def token_uit(self, m):
        return m.get_content().split("/download/")[1].split()[0]


class Handtekening(unittest.TestCase):
    body = b'{"event_id":"evt_1","event_type":"transaction.completed"}'

    def test_geldig(self):
        ts = int(time.time())
        self.assertEqual(paddle.controleer_handtekening(paddle.teken(self.body, GEHEIM, ts), self.body, GEHEIM), ts)

    def test_aangepaste_body(self):
        kop = paddle.teken(self.body, GEHEIM)
        with self.assertRaises(paddle.OngeldigeHandtekening):
            paddle.controleer_handtekening(kop, self.body.replace(b"evt_1", b"evt_2"), GEHEIM)

    def test_verkeerd_geheim(self):
        with self.assertRaises(paddle.OngeldigeHandtekening):
            paddle.controleer_handtekening(paddle.teken(self.body, "ander"), self.body, GEHEIM)

    def test_te_oud(self):
        kop = paddle.teken(self.body, GEHEIM, time.time() - 3600)
        with self.assertRaises(paddle.OngeldigeHandtekening):
            paddle.controleer_handtekening(kop, self.body, GEHEIM, tolerantie=300)

    def test_rotatie_twee_h1(self):
        ts = int(time.time())
        goed = paddle.teken(self.body, GEHEIM, ts).split("h1=")[1]
        kop = f"ts={ts};h1={'0' * 64};h1={goed}"
        self.assertEqual(paddle.controleer_handtekening(kop, self.body, GEHEIM), ts)

    def test_ontbrekende_of_kapotte_kop(self):
        for kop in (None, "", "ts=abc;h1=00", "h1=00"):
            with self.assertRaises(paddle.OngeldigeHandtekening):
                paddle.controleer_handtekening(kop, self.body, GEHEIM)


class Links(Basis):
    def test_link_werkt_en_verloopt(self):
        start = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
        link_id, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5, nu=start)
        self.assertEqual(links.controleer(token, self.cfg.geheim, nu=start + datetime.timedelta(hours=71))[0], link_id)
        self.assertEqual(links.controleer(token, self.cfg.geheim, nu=start + datetime.timedelta(hours=72, seconds=1)),
                         (None, "verlopen"))
        rij, reden = self.opslag.link_gebruik(link_id, moment=start + datetime.timedelta(hours=73))
        self.assertIsNone(rij)
        self.assertEqual(reden, "verlopen")

    def test_aangepast_token_geweigerd(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        link_id, verloopt, sig = token.split(".")
        self.assertEqual(links.controleer(f"{link_id}.{int(verloopt) + 86400}.{sig}", self.cfg.geheim), (None, "handtekening"))
        self.assertEqual(links.controleer("onzin", self.cfg.geheim), (None, "onleesbaar"))

    def test_maximaal_vijf_downloads(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        for _ in range(5):
            self.assertEqual(self.lev.download(token), (self.doc, "build-kit-v1.0.pdf"))
        self.assertEqual(self.lev.download(token), (None, "op"))

    def test_maximaal_vijf_bij_gelijktijdige_verzoeken(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        uitkomsten, slot = [], threading.Lock()
        start = threading.Barrier(24)

        def haal():
            start.wait()
            uit = self.lev.download(token)
            with slot:
                uitkomsten.append(uit[1])

        draden = [threading.Thread(target=haal) for _ in range(24)]
        for d in draden:
            d.start()
        for d in draden:
            d.join()
        self.assertEqual(uitkomsten.count("build-kit-v1.0.pdf"), 5)
        self.assertEqual(uitkomsten.count("op"), 19)
        with self.opslag.verbind() as c:
            self.assertEqual(c.execute("SELECT aantal FROM links").fetchone()[0], 5)


class Webhook(Basis):
    def test_aankoop_stuurt_een_mail_met_link_op_het_eigen_domein(self):
        self.stuur({"event_id": "evt_c1", "event_type": "customer.created",
                    "data": {"id": "ctm_1", "email": "koper@voorbeeld.test", "locale": "en"}})
        self.assertEqual(self.stuur(self.transactie()), (200, "ok"))
        self.assertEqual(len(self.post), 1)
        m = self.post[0]
        self.assertEqual(m["To"], "koper@voorbeeld.test")
        self.assertIn("https://en.test/download/", m.get_content())
        self.assertIn("14-day right of withdrawal", m.get_content())
        self.assertEqual(self.lev.download(self.token_uit(m))[0], self.doc)

    def test_nl_prijs_geeft_nederlandse_mail_en_nl_domein(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", None)
        self.stuur(self.transactie(prijzen=("pri_kit_eur",)))
        self.assertIn("herroepingsrecht", self.post[0].get_content())
        self.assertIn("https://nl.test/download/", self.post[0].get_content())

    def test_replay_zelfde_event_twee_keer(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        body = json.dumps(self.transactie()).encode()
        kop = paddle.teken(body, GEHEIM)
        self.assertEqual(self.lev.webhook(body, kop), (200, "ok"))
        self.assertEqual(self.lev.webhook(body, kop), (200, "al verwerkt"))  # exact dezelfde aflevering
        self.assertEqual(self.stuur(self.transactie(event_id="evt_t2")), (200, "ok"))  # zelfde transactie, ander event
        self.assertEqual(len(self.post), 1)
        self.assertEqual(len(self.opslag.uitgaand_alle()), 1)

    def test_ongeldige_handtekening(self):
        body = json.dumps(self.transactie()).encode()
        self.assertEqual(self.lev.webhook(body, paddle.teken(body, "fout"))[0], 401)
        self.assertEqual(self.post, [])

    def test_zonder_email_wordt_opnieuw_geprobeerd(self):
        self.assertEqual(self.stuur(self.transactie())[0], 500)
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        self.assertEqual(self.stuur(self.transactie()), (200, "ok"))  # zelfde event_id mag opnieuw
        self.assertEqual(len(self.post), 1)


class Volgorde(Basis):
    def setUp(self):
        super().setUp()
        self.opslag.klant_bewaar("ctm_1", "abo@voorbeeld.test", "en")

    def test_opzegging_voor_aanmaak_binnen(self):
        # Paddle levert de opzegging (nieuwer) eerder af dan de aanmaak (ouder): de aanmaak mag niets terugzetten
        self.stuur(self.abonnement("evt_2", "subscription.canceled", "canceled", moment(-1)))
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-30), ends_at=moment(335)))
        self.assertEqual(self.opslag.actieve_abonnees(), [])
        self.assertEqual(self.opslag.alle_abonnees()[0]["status"], "canceled")

    def test_ouder_update_na_nieuwer_wordt_genegeerd(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-10), ends_at=moment(355)))
        self.stuur(self.abonnement("evt_3", "subscription.updated", "past_due", moment(-1), ends_at=moment(355)))
        self.stuur(self.abonnement("evt_2", "subscription.updated", "active", moment(-5), ends_at=moment(355)))
        self.assertEqual(self.opslag.alle_abonnees()[0]["status"], "past_due")

    def test_normale_volgorde(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-10), ends_at=moment(355)))
        self.assertEqual([r["email"] for r in self.opslag.actieve_abonnees()], ["abo@voorbeeld.test"])
        self.stuur(self.abonnement("evt_2", "subscription.canceled", "canceled", moment(-1)))
        self.assertEqual(self.opslag.actieve_abonnees(), [])


class Terugdraaien(Basis):
    def setUp(self):
        super().setUp()
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        self.stuur(self.transactie())
        self.stuur(self.abonnement("evt_s1", "subscription.created", "active", moment(-1), ends_at=moment(364)))
        self.token = self.token_uit(self.post[0])

    def adjustment(self, actie, status, event_id="evt_adj"):
        return {"event_id": event_id, "event_type": "adjustment.created", "occurred_at": moment(0),
                "data": {"id": "adj_1", "transaction_id": "txn_1", "customer_id": "ctm_1", "action": actie,
                         "status": status, "type": "full"}}

    def test_refund_trekt_links_in_en_stopt_updates(self):
        self.assertEqual(self.stuur(self.adjustment("refund", "approved")), (200, "ok"))
        self.assertEqual(self.lev.download(self.token), (None, "ingetrokken"))
        self.assertEqual(self.opslag.actieve_abonnees(), [])
        doc2 = pathlib.Path(self.tmp.name) / "v1.1.pdf"
        doc2.write_bytes(b"%PDF")
        self.opslag.versie_bewaar("1.1", str(doc2), "def", "x")
        self.assertEqual(self.lev.send_update("1.1", uit=lambda *_: None), [])
        # een latere abonnementsupdate maakt het niet weer actief
        self.stuur(self.abonnement("evt_s2", "subscription.updated", "active", moment(0), ends_at=moment(364)))
        self.assertEqual(self.opslag.actieve_abonnees(), [])

    def test_chargeback_trekt_ook_in(self):
        self.stuur(self.adjustment("chargeback", "approved"))
        self.assertEqual(self.lev.download(self.token), (None, "ingetrokken"))
        self.assertEqual(self.opslag.actieve_abonnees(), [])

    def test_refund_in_afwachting_doet_nog_niets(self):
        self.stuur(self.adjustment("refund", "pending_approval"))
        self.assertEqual(self.lev.download(self.token)[0], self.doc)
        self.stuur(self.adjustment("refund", "approved", event_id="evt_adj2"))
        self.assertEqual(self.lev.download(self.token), (None, "ingetrokken"))

    def test_refund_voor_de_betaling_binnen_levert_niets(self):
        self.post.clear()
        self.stuur({"event_id": "evt_adjx", "event_type": "adjustment.created", "occurred_at": moment(0),
                    "data": {"transaction_id": "txn_9", "customer_id": "ctm_1", "action": "refund", "status": "approved"}})
        self.stuur(self.transactie(event_id="evt_t9", txn="txn_9"))
        self.assertEqual(self.post, [])


class SmtpWachtrij(Basis):
    def test_mislukte_levering_blijft_staan_en_gaat_later_alsnog(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")

        def stuk(m):
            raise OSError("smtp weg")
        self.lev.verzend = stuk
        self.assertEqual(self.stuur(self.transactie()), (200, "ok"))  # aankoop vastgelegd, ook al faalde de mail
        rij = self.opslag.uitgaand_alle()[0]
        self.assertEqual((rij["status"], rij["pogingen"]), ("wacht", 1))
        self.assertIn("smtp weg", rij["laatste_fout"])
        self.assertEqual(self.lev.wachtrij(), (0, 0))  # nog niet aan de beurt (wachttijd)
        with self.opslag.verbind() as c:  # de wachttijd voorbij laten gaan
            c.execute("UPDATE uitgaand SET volgende = ?", (moment(-1),))
        self.lev.verzend = self.post.append
        self.assertEqual(self.lev.wachtrij(), (1, 0))
        self.assertEqual(self.opslag.uitgaand_alle()[0]["status"], "verzonden")
        self.assertEqual(len(self.post), 1)
        self.assertEqual(self.lev.download(self.token_uit(self.post[0]))[0], self.doc)
        self.assertEqual(self.lev.wachtrij(), (0, 0))  # niet nog een keer
        self.assertEqual(len(self.post), 1)

    def test_wachttijd_loopt_op_tot_zes_uur(self):
        self.opslag.uitgaand_toevoegen("txn_x", "kit", "a@b.test", "en", "1.0")
        rij_id = self.opslag.uitgaand_alle()[0]["id"]
        for _ in range(12):
            self.opslag.uitgaand_mislukt(rij_id, "fout")
        rij = self.opslag.uitgaand_alle()[0]
        volgende = datetime.datetime.fromisoformat(rij["volgende"].replace("Z", "+00:00"))
        self.assertLessEqual(volgende - datetime.datetime.now(UTC), datetime.timedelta(hours=6, minutes=1))
        self.assertEqual(rij["status"], "wacht")


class SendUpdate(Basis):
    def setUp(self):
        super().setUp()
        tot = datetime.datetime(2099, 1, 1, tzinfo=UTC)
        self.opslag.abonnee_bewaar("sub_1", "ctm_1", "een@voorbeeld.test", "en", "active", tot)
        self.opslag.abonnee_bewaar("sub_2", "ctm_2", "twee@voorbeeld.test", "nl", "active", tot)
        self.opslag.abonnee_bewaar("sub_3", "ctm_3", "oud@voorbeeld.test", "en", "active",
                                   datetime.datetime(2020, 1, 1, tzinfo=UTC))
        doc2 = pathlib.Path(self.tmp.name) / "build-kit-v1.1.pdf"
        doc2.write_bytes(b"%PDF v1.1")
        self.opslag.versie_bewaar("1.1", str(doc2), "def456", "Ladder: 15 fijne treden")

    def test_dry_run_verstuurt_en_schrijft_niets(self):
        uit = self.lev.send_update("1.1", dry_run=True, uit=lambda *_: None)
        self.assertEqual(sorted(e for e, _ in uit), ["een@voorbeeld.test", "twee@voorbeeld.test"])
        self.assertEqual(self.post, [])
        self.assertIsNone(self.opslag.verzending("een@voorbeeld.test", "1.1"))

    def test_idempotent_per_versie(self):
        eerste = self.lev.send_update("1.1", uit=lambda *_: None)
        self.assertEqual(sorted(u for _, u in eerste), ["verzonden", "verzonden"])
        self.assertEqual(self.lev.send_update("1.1", uit=lambda *_: None),
                         [("een@voorbeeld.test", "al eerder verzonden"), ("twee@voorbeeld.test", "al eerder verzonden")])
        self.assertEqual(len(self.post), 2)
        nl = [m for m in self.post if m["To"] == "twee@voorbeeld.test"][0].get_content()
        self.assertIn("Ladder: 15 fijne treden", nl)
        self.assertIn("https://nl.test/download/", nl)

    def test_mislukte_mail_wordt_later_opnieuw_geprobeerd(self):
        def stuk(m):
            if m["To"] == "twee@voorbeeld.test":
                raise OSError("smtp weg")
            self.post.append(m)
        self.lev.verzend = stuk
        uit = dict(self.lev.send_update("1.1", uit=lambda *_: None))
        self.assertTrue(uit["twee@voorbeeld.test"].startswith("mislukt"))
        self.lev.verzend = self.post.append
        uit = dict(self.lev.send_update("1.1", uit=lambda *_: None))
        self.assertEqual(uit, {"een@voorbeeld.test": "al eerder verzonden", "twee@voorbeeld.test": "verzonden"})

    def test_export_csv(self):
        doel, n = export_abonnees(self.opslag, pathlib.Path(self.tmp.name) / "boek" / "abonnees.csv")
        self.assertEqual(n, 3)
        rijen = list(csv.DictReader(open(doel, encoding="utf-8")))
        self.assertEqual({r["email"] for r in rijen}, {"een@voorbeeld.test", "twee@voorbeeld.test", "oud@voorbeeld.test"})
        self.assertEqual(doel.stat().st_mode & 0o777, 0o600)
        for verboden in ("/var/www/theweekly2pctedge.com/abonnees.csv", pathlib.Path(__file__).parent / "x.csv"):
            with self.assertRaises(SystemExit):
                export_abonnees(self.opslag, verboden)


class Http(Basis):
    def setUp(self):
        super().setUp()
        self.server = maak_server(self.lev, poort=0)
        self.poort = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def vraag(self, methode, pad, body=None, koppen=None):
        c = http.client.HTTPConnection("127.0.0.1", self.poort, timeout=10)
        c.request(methode, pad, body=body, headers=koppen or {})
        r = c.getresponse()
        uit = (r.status, r.read())
        c.close()
        return uit

    def test_healthz_lekt_niets(self):
        self.assertEqual(self.vraag("GET", "/healthz"), (200, b"ok"))

    def test_webhook_met_foute_handtekening(self):
        body = json.dumps(self.transactie()).encode()
        self.assertEqual(self.vraag("POST", "/webhook/paddle", body, {"Paddle-Signature": "ts=1;h1=00"})[0], 401)

    def test_download_routes(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        status, inhoud = self.vraag("GET", f"/download/{token}")
        self.assertEqual((status, inhoud), (200, b"%PDF-1.4 test"))
        self.assertEqual(self.vraag("GET", "/download/abc.1.def")[0], 404)
        verlopen = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 1, 5,
                              nu=datetime.datetime.now(UTC) - datetime.timedelta(hours=2))[1]
        self.assertEqual(self.vraag("GET", f"/download/{verlopen}")[0], 410)
        self.assertEqual(self.vraag("GET", "/levering.db")[0], 404)


# ----------------------------------------------------------------------------------------------- review 27 okt 2026
class AuditHandtekening(unittest.TestCase):
    body = b'{"event_id":"evt_1","event_type":"transaction.completed"}'

    def test_niet_ascii_in_de_kop_geeft_ongeldig_en_geen_crash(self):
        ts = int(time.time())
        for kop in ("ts=\u00b2;h1=00", f"ts={ts};h1=\u00e9\u00e9", f"ts={ts};h1=" + "z" * 64, f"ts={ts}"):
            with self.assertRaises(paddle.OngeldigeHandtekening):
                paddle.controleer_handtekening(kop, self.body, GEHEIM)

    def test_herserialiseerde_json_klopt_niet(self):
        ruw = b'{"event_id": "evt_1",  "event_type":"transaction.completed"}'
        kop = paddle.teken(ruw, GEHEIM)
        with self.assertRaises(paddle.OngeldigeHandtekening):
            paddle.controleer_handtekening(kop, json.dumps(json.loads(ruw)).encode(), GEHEIM)

    def test_uit_de_toekomst_geweigerd(self):
        kop = paddle.teken(self.body, GEHEIM, time.time() + 3600)
        with self.assertRaises(paddle.OngeldigeHandtekening):
            paddle.controleer_handtekening(kop, self.body, GEHEIM, tolerantie=300)


class AuditToestemming(Basis):
    """EU-herroepingsrecht: zonder vastgelegde toestemming geen levering."""
    def setUp(self):
        super().setUp()
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")

    def test_zonder_toestemming_geen_levering(self):
        ev = self.transactie(toestemming=False)
        self.assertEqual(self.stuur(ev), (200, "ok"))
        self.assertEqual(self.post, [])
        self.assertEqual(self.opslag.aankoop("txn_1")["status"], "wacht_op_toestemming")

    def test_met_toestemming_levering_en_tijdstip_vastgelegd(self):
        ev = self.transactie()
        ev["data"]["custom_data"] = {"withdrawal_consent": "en-2026-10-27", "consent_at": "2026-10-01T10:00:00.000Z"}
        self.assertEqual(self.stuur(ev), (200, "ok"))
        self.assertEqual(len(self.post), 1)
        a = self.opslag.aankoop("txn_1")
        self.assertEqual(a["toestemming"], "en-2026-10-27")
        self.assertEqual(a["toestemming_moment"], "2026-10-01T10:00:00Z")

    def test_handmatig_vrijgeven_na_toestemming_per_mail(self):
        self.stuur(self.transactie(toestemming=False))
        self.assertTrue(self.lev.vrijgeven("txn_1", "per mail 2026-11-02"))
        self.lev.wachtrij()
        self.assertEqual(len(self.post), 1)
        self.assertEqual(self.opslag.aankoop("txn_1")["toestemming"], "per mail 2026-11-02")


class AuditGeldstroom(Basis):
    """Elk Paddle-event waarop de dienst geabonneerd is: wat krijgt de klant, wat zegt de database."""
    def setUp(self):
        super().setUp()
        self.opslag.klant_bewaar("ctm_1", "abo@voorbeeld.test", "en")

    def test_verlenging_schuift_einde_op(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-360), ends_at=moment(5)))
        ev = self.transactie(event_id="evt_r", txn="txn_r", prijzen=("pri_upd_usd",), origin="subscription_recurring",
                             sub="sub_1")
        self.assertEqual(self.stuur(ev), (200, "ok"))
        self.assertEqual(self.post, [])  # een verlenging levert geen kit opnieuw
        tot = self.opslag.alle_abonnees()[0]["actief_tot"]
        self.assertGreater(tot, moment(300))

    def test_past_due_krijgt_geen_nieuwe_updates(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-10), ends_at=moment(355)))
        self.stuur(self.abonnement("evt_2", "subscription.past_due", "past_due", moment(-1), ends_at=moment(355)))
        self.assertEqual(self.opslag.alle_abonnees()[0]["status"], "past_due")
        self.assertEqual(self.opslag.actieve_abonnees(), [])
        # betaalt alsnog -> weer actief
        self.stuur(self.abonnement("evt_3", "subscription.updated", "active", moment(0), ends_at=moment(365)))
        self.assertEqual(len(self.opslag.actieve_abonnees()), 1)

    def test_gepauzeerd_en_hervat(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-10), ends_at=moment(355)))
        self.stuur(self.abonnement("evt_2", "subscription.paused", "paused", moment(-5)))
        self.assertEqual(self.opslag.actieve_abonnees(), [])
        self.stuur(self.abonnement("evt_3", "subscription.resumed", "active", moment(-1), ends_at=moment(364)))
        self.assertEqual(len(self.opslag.actieve_abonnees()), 1)

    def test_opzegging_per_periode_einde_blijft_actief_tot_dat_einde(self):
        self.stuur(self.abonnement("evt_1", "subscription.created", "active", moment(-10), ends_at=moment(355)))
        ev = self.abonnement("evt_2", "subscription.updated", "active", moment(-1), ends_at=moment(355))
        ev["data"]["scheduled_change"] = {"action": "cancel", "effective_at": moment(355)}
        self.stuur(ev)
        self.assertEqual(len(self.opslag.actieve_abonnees()), 1)

    def test_chargeback_waarschuwing_doet_niets(self):
        ev = self.transactie()
        ev["data"]["custom_data"] = {"withdrawal_consent": "en-2026-10-27"}
        self.stuur(ev)
        token = self.token_uit(self.post[0])
        self.stuur({"event_id": "evt_w", "event_type": "adjustment.created", "occurred_at": moment(0),
                    "data": {"transaction_id": "txn_1", "customer_id": "ctm_1", "action": "chargeback_warning",
                             "status": "approved"}})
        self.assertEqual(self.lev.download(token)[0], self.doc)


class AuditEmail(Basis):
    def test_meerdere_ontvangers_worden_niet_gemaild(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test, buit@aanvaller.test", "en")
        self.stuur(self.transactie())
        self.assertEqual(self.post, [])
        self.assertEqual(self.opslag.uitgaand_alle()[0]["status"], "ongeldig_adres")

    def test_regeleinde_in_adres_niet_gemaild_en_niet_eindeloos_opnieuw(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test\r\nBcc: buit@aanvaller.test", "en")
        self.stuur(self.transactie())
        self.assertEqual(self.post, [])
        self.assertEqual(self.opslag.uitgaand_alle()[0]["status"], "ongeldig_adres")

    def test_adrescontrole(self):
        from levering import post
        for goed in ("a@b.nl", "Jan.de-Vries+kit@sub.voorbeeld.co.uk"):
            self.assertTrue(post.adres_geldig(goed), goed)
        for fout in ("", "a", "a@b", "a@b.nl, c@d.nl", "<a@b.nl>", "a@b.nl\n", "Jan <a@b.nl>", "a b@c.nl", None,
                     "x" * 250 + "@b.nl"):
            self.assertFalse(post.adres_geldig(fout), repr(fout))

    def test_versie_met_vreemde_tekens_geweigerd(self):
        with self.assertRaises(ValueError):
            self.opslag.versie_bewaar('1.2"\r\nX-Kop: y', str(self.doc), "", "")


class AuditOpslag(Basis):
    def test_vergrendelde_database_geeft_503_niet_crash(self):
        import sqlite3

        def op_slot(*a, **k):
            raise sqlite3.OperationalError("database is locked")
        self.opslag.event_nieuw = op_slot
        self.assertEqual(self.stuur(self.transactie())[0], 503)

    def test_ontbrekende_database_map(self):
        weg = Opslag.__new__(Opslag)
        weg.pad = str(pathlib.Path(self.tmp.name) / "bestaat-niet" / "x.db")
        self.assertFalse(weg.gezond())

    def test_databasebestand_alleen_voor_eigenaar(self):
        import os
        d = pathlib.Path(self.tmp.name) / "vers"
        d.mkdir()
        oud = os.umask(0o022)
        try:
            Opslag(str(d / "n.db"))
        finally:
            os.umask(oud)
        self.assertEqual((d / "n.db").stat().st_mode & 0o077, 0)

    def test_geheimen_niet_in_repr(self):
        cfg = Instellingen(geheim="LINKGEHEIM", paddle_geheim="PDLGEHEIM", paddle_api_sleutel="APISLEUTEL",
                           smtp_wachtwoord="SMTPWW")
        tekst = repr(cfg)
        for g in ("LINKGEHEIM", "PDLGEHEIM", "APISLEUTEL", "SMTPWW"):
            self.assertNotIn(g, tekst)


class AuditHttp(Http):
    def test_trage_client_wordt_afgekapt(self):
        import socket
        import levering.dienst as dienst
        oud = dienst.TIMEOUT
        dienst.TIMEOUT = 1
        try:
            s = socket.create_connection(("127.0.0.1", self.poort), timeout=10)
            s.sendall(b"POST /webhook/paddle HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n\r\n{")
            start = time.time()
            data = s.recv(1024)  # de dienst sluit (b'' of een fout) in plaats van eeuwig te wachten
            self.assertLess(time.time() - start, 5)
            s.close()
        finally:
            dienst.TIMEOUT = oud

    def test_te_grote_body(self):
        self.assertEqual(self.vraag("POST", "/webhook/paddle", b"x", {"Content-Length": "2000000"})[0], 413)

    def test_kapot_verzoek_geeft_geen_fout_in_de_dienst(self):
        import socket
        fouten = []
        self.server.handle_error = lambda req, adres: fouten.append(sys.exc_info()[1])
        s = socket.create_connection(("127.0.0.1", self.poort), timeout=5)
        s.sendall(b"\x16\x03\x01 rommel\r\n\r\n")
        s.recv(1024)
        s.close()
        s = socket.create_connection(("127.0.0.1", self.poort), timeout=5)
        s.sendall(b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n")
        s.recv(1024)
        s.close()
        time.sleep(0.2)
        self.assertEqual(fouten, [])

    def test_foutpagina_lekt_geen_paden_of_stacktrace(self):
        status, inhoud = self.vraag("PUT", "/download/x")
        self.assertIn(status, (404, 405, 501))
        for lek in (b"Traceback", b"/home", b"/root", b".py", b"Python"):
            self.assertNotIn(lek, inhoud)

    def test_download_padtraversal(self):
        for pad in ("/download/../levering.db", "/download/..%2F..%2Fetc%2Fpasswd", "/download/%2e%2e/x.y.z",
                    "/download/" + "a." * 3):
            self.assertIn(self.vraag("GET", pad)[0], (404, 410))

    def test_token_niet_in_het_log(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        with self.assertLogs("levering", level="INFO") as log:
            self.vraag("GET", f"/download/{token}")
            self.vraag("GET", f"/download/{token}x")
        self.assertFalse(any(token in r or token.split(".")[2] in r for r in log.output), log.output)

    def test_webhook_wacht_niet_op_smtp(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        klaar = threading.Event()

        def traag(m):
            time.sleep(3)
            self.post.append(m)
            klaar.set()
        self.lev.verzend = traag
        import levering.dienst as dienst
        stop = threading.Event()
        dienst.start_wachtrij(self.lev, stop)
        try:
            body = json.dumps(self.transactie()).encode()
            start = time.time()
            status, _ = self.vraag("POST", "/webhook/paddle", body, {"Paddle-Signature": paddle.teken(body, GEHEIM)})
            self.assertEqual(status, 200)
            self.assertLess(time.time() - start, 2)  # Paddle wil binnen 5 s antwoord
            self.assertTrue(klaar.wait(10))
        finally:
            stop.set()


class AuditOpdrachtregel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_bestand_zoals_systemd(self):
        import os
        from levering.opdrachten import lees_env
        env = self.d / "levering.env"
        env.write_text('# commentaar\nW2E_T_A=Daan <kit@voorbeeld.test>\nW2E_T_B="met spaties"\nW2E_T_C=\n\n', encoding="utf-8")
        try:
            lees_env(env)
            self.assertEqual(os.environ["W2E_T_A"], "Daan <kit@voorbeeld.test>")
            self.assertEqual(os.environ["W2E_T_B"], "met spaties")
            self.assertEqual(os.environ["W2E_T_C"], "")
        finally:
            for k in ("W2E_T_A", "W2E_T_B", "W2E_T_C"):
                os.environ.pop(k, None)

    @unittest.skipUnless(hasattr(__import__("os"), "geteuid") and __import__("os").geteuid() == 0, "alleen als root")
    def test_als_root_geen_rootbestanden_in_de_databasemap(self):
        import os
        import subprocess
        dbmap = self.d / "lib"
        dbmap.mkdir()
        os.chown(dbmap, 65534, 65534)
        os.chmod(dbmap, 0o700)
        os.chmod(self.d, 0o755)
        doc = self.d / "kit.pdf"
        doc.write_bytes(b"%PDF")
        os.chmod(doc, 0o644)
        geheim = self.d / "geheim.txt"  # alleen voor root leesbaar, zoals een changelog in /root
        geheim.write_text("Wijziging", encoding="utf-8")
        os.chmod(geheim, 0o600)
        env = dict(os.environ, LEVERING_DB=str(dbmap / "levering.db"))
        repo = pathlib.Path(__file__).resolve().parent.parent
        uit = subprocess.run([sys.executable, "-m", "levering", "nieuwe-versie", "--versie", "1.0", "--bestand", str(doc),
                              "--changelog", str(geheim)], cwd=repo, env=env, capture_output=True, text=True)
        self.assertEqual(uit.returncode, 0, uit.stderr)
        for f in dbmap.iterdir():
            self.assertEqual(f.stat().st_uid, 65534, f)
        self.assertEqual(Opslag(str(dbmap / "levering.db")).versie("1.0")["changelog"], "Wijziging")
        os.chmod(doc, 0o600)  # niet leesbaar voor de dienst -> weigeren
        uit = subprocess.run([sys.executable, "-m", "levering", "nieuwe-versie", "--versie", "1.1", "--bestand", str(doc)],
                             cwd=repo, env=env, capture_output=True, text=True)
        self.assertNotEqual(uit.returncode, 0)
        self.assertIn("kan", uit.stderr)


if __name__ == "__main__":
    unittest.main()
