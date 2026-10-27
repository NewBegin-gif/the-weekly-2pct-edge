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

    def transactie(self, event_id="evt_t1", txn="txn_1", prijzen=("pri_kit_usd",), origin="web", sub=None):
        return {"event_id": event_id, "event_type": "transaction.completed", "occurred_at": moment(0),
                "data": {"id": txn, "customer_id": "ctm_1", "origin": origin, "subscription_id": sub,
                         "items": [{"price": {"id": p}} for p in prijzen],
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


if __name__ == "__main__":
    unittest.main()
