"""Tests: python3 -m unittest levering.test_levering (vanaf de repo-root). Geen netwerk, geen SMTP: een nep-verzender
vangt de berichten op, en een tijdelijke SQLite-database per test."""
import datetime
import json
import pathlib
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True

from levering import links, paddle  # noqa: E402
from levering.instellingen import Instellingen  # noqa: E402
from levering.kern import Levering  # noqa: E402
from levering.opslag import Opslag  # noqa: E402

GEHEIM = "whsec_test"
UTC = datetime.timezone.utc


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.doc = d / "build-kit-v1.0.pdf"
        self.doc.write_bytes(b"%PDF-1.4 test")
        self.cfg = Instellingen(db=str(d / "t.db"), documenten=str(d), geheim="linkgeheim-test",
                                basis_url="https://voorbeeld.test/kit", paddle_geheim=GEHEIM, smtp_host="x",
                                mail_van="Daan <kit@voorbeeld.test>",
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
        # ook de database weigert na het verloop, los van de handtekening
        rij, reden = self.opslag.link_gebruik(link_id, moment=start + datetime.timedelta(hours=73))
        self.assertIsNone(rij)
        self.assertEqual(reden, "verlopen")

    def test_aangepast_token_geweigerd(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        link_id, verloopt, sig = token.split(".")
        langer = f"{link_id}.{int(verloopt) + 86400}.{sig}"
        self.assertEqual(links.controleer(langer, self.cfg.geheim), (None, "handtekening"))
        self.assertEqual(links.controleer("onzin", self.cfg.geheim), (None, "onleesbaar"))

    def test_maximaal_vijf_downloads(self):
        _, token = links.maak(self.opslag, self.cfg.geheim, "a@b.test", "1.0", 72, 5)
        for _ in range(5):
            pad, naam = self.lev.download(token)
            self.assertEqual(pad, self.doc)
            self.assertEqual(naam, "build-kit-v1.0.pdf")
        self.assertEqual(self.lev.download(token), (None, "op"))


class Webhook(Basis):
    def transactie(self, event_id="evt_t1", prijzen=("pri_kit_usd",), origin="web", sub=None):
        return {"event_id": event_id, "event_type": "transaction.completed",
                "data": {"id": "txn_1", "customer_id": "ctm_1", "origin": origin, "subscription_id": sub,
                         "items": [{"price": {"id": p}} for p in prijzen],
                         "billing_period": {"ends_at": "2027-11-01T00:00:00Z"} if sub else None}}

    def test_aankoop_stuurt_een_mail_met_link(self):
        self.stuur({"event_id": "evt_c1", "event_type": "customer.created",
                    "data": {"id": "ctm_1", "email": "koper@voorbeeld.test", "locale": "en"}})
        self.assertEqual(self.stuur(self.transactie()), (200, "ok"))
        self.assertEqual(len(self.post), 1)
        m = self.post[0]
        self.assertEqual(m["To"], "koper@voorbeeld.test")
        tekst = m.get_content()
        self.assertIn("https://voorbeeld.test/kit/download/", tekst)
        self.assertIn("14-day right of withdrawal", tekst)
        token = tekst.split("/kit/download/")[1].split()[0]
        self.assertEqual(self.lev.download(token)[0], self.doc)

    def test_dubbel_event_en_dubbele_transactie_doen_niets(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        self.stuur(self.transactie())
        self.assertEqual(self.stuur(self.transactie()), (200, "al verwerkt"))
        self.stuur(self.transactie(event_id="evt_t2"))  # zelfde transactie, ander event
        self.assertEqual(len(self.post), 1)

    def test_nl_prijs_geeft_nederlandse_mail(self):
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", None)
        self.stuur(self.transactie(prijzen=("pri_kit_eur",)))
        self.assertIn("herroepingsrecht", self.post[0].get_content())

    def test_ongeldige_handtekening(self):
        body = json.dumps(self.transactie()).encode()
        self.assertEqual(self.lev.webhook(body, paddle.teken(body, "fout"))[0], 401)
        self.assertEqual(self.post, [])

    def test_zonder_email_wordt_opnieuw_geprobeerd(self):
        self.assertEqual(self.stuur(self.transactie())[0], 500)
        self.opslag.klant_bewaar("ctm_1", "koper@voorbeeld.test", "en")
        self.assertEqual(self.stuur(self.transactie()), (200, "ok"))  # zelfde event_id mag opnieuw
        self.assertEqual(len(self.post), 1)

    def test_abonnement_en_opzegging(self):
        self.opslag.klant_bewaar("ctm_1", "abo@voorbeeld.test", "en")
        self.stuur({"event_id": "evt_s1", "event_type": "subscription.created",
                    "data": {"id": "sub_1", "customer_id": "ctm_1", "status": "active",
                             "items": [{"price": {"id": "pri_upd_usd"}}],
                             "current_billing_period": {"ends_at": "2099-01-01T00:00:00Z"}}})
        self.assertEqual([r["email"] for r in self.opslag.actieve_abonnees()], ["abo@voorbeeld.test"])
        self.stuur({"event_id": "evt_s2", "event_type": "subscription.canceled",
                    "data": {"id": "sub_1", "customer_id": "ctm_1", "status": "canceled",
                             "canceled_at": "2026-11-02T00:00:00Z", "items": [{"price": {"id": "pri_upd_usd"}}],
                             "current_billing_period": None}})
        self.assertEqual(self.opslag.actieve_abonnees(), [])


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
        self.assertEqual(len(self.post), 2)
        tweede = self.lev.send_update("1.1", uit=lambda *_: None)
        self.assertEqual([u for _, u in tweede], ["al eerder verzonden"] * 2)
        self.assertEqual(len(self.post), 2)
        nl = [m for m in self.post if m["To"] == "twee@voorbeeld.test"][0].get_content()
        self.assertIn("Ladder: 15 fijne treden", nl)
        self.assertIn("Versie 1.1 staat klaar", nl)

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
        self.assertEqual(sorted(m["To"] for m in self.post), ["een@voorbeeld.test", "twee@voorbeeld.test"])


if __name__ == "__main__":
    unittest.main()
