"""Tests voor de bouw: python3 -m unittest discover -s bouw -p "test_*.py" (vanaf de repo-root).

Releasecontrole: het dashboard mag niets tonen dat jonger is dan 24 uur. Getest op de opschoning en filters
(momentopname met data van vóór én na T) en op de harde controle (controleer_leeftijd) met een te jong tijdstip.
"""
import datetime
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_logboek  # noqa: E402,F401  (registreert de module voor de w2e_*-imports)
import w2e_data as D  # noqa: E402
import w2e_kassa as K  # noqa: E402

NU = datetime.datetime(2026, 11, 2, 12, 0)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def ph(uren=168):
    ts = [NU - datetime.timedelta(hours=h) for h in range(uren, -1, -1)]
    return {"timestamps": [f"{t:%Y-%m-%d %H:%M}" for t in ts], "btc_price": [95000.0 + i for i in range(len(ts))],
            "unrealized_pnl": [-1.0] * len(ts), "total_value": [100.0] * len(ts)}


def rij(soort, t, prijs, trede, pct=None):
    return {"created_at": iso(t), "decision_type": soort, "strategy": "fine", "level": trede, "price": prijs,
            "reason": "€500 @ €95000", "data": {"amount_eur": 500, "profit_pct": pct}}


class Releasecontrole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.oud_cache, D.CACHE = D.CACHE, pathlib.Path(self.tmp.name)
        # een ladderstap van 30 uur geleden en een van nu: alleen de oude mag gebruikt worden
        for t, stap in ((NU - datetime.timedelta(hours=30), 120), (NU, 999)):
            (D.CACHE / f"grid-{t:%Y%m%dT%H%M}.json").write_text(json.dumps(
                {"fine_stap": stap, "coarse_stap": stap * 4, "rsi": 50.0, "modus": "x", "rsi_rem": True,
                 "rsi_taper": True, "rsi_blok": 80, "rsi_drempel": 70}))
        jong, oud = NU - datetime.timedelta(hours=2), NU - datetime.timedelta(hours=40)
        self.bron = {
            "decision-stream?type=BUY_PLACED&limit=500": {"rows": [rij("BUY_PLACED", oud, 94000, 1), rij("BUY_PLACED", jong, 93000, 2)]},
            "decision-stream?type=LIMIT_SELL_PLACED&limit=500": {"rows": [rij("LIMIT_SELL_PLACED", oud, 97000, 1),
                                                                          rij("LIMIT_SELL_PLACED", jong, 96000, 2)]},
            "decision-stream?type=TTP_FIRE&limit=500": {"rows": [rij("TTP_FIRE", oud, 96500, 3, 2.1),
                                                                 rij("TTP_FIRE", jong, 96600, 4, 2.2)]},
            "telegram-feed?limit=100&zoek=Exposure": {"rows": [
                {"created_at": iso(oud) + "Z", "text": "Exposure: <b>41.0%</b> (€1 / €2, cap 50%)"},
                {"created_at": iso(jong) + "Z", "text": "Exposure: <b>44.0%</b> (€1 / €2, cap 50%)"}]},
        }
        self.oud_haal = D._haal
        D._haal = lambda pad, url=None: self.bron.get(pad)

    def tearDown(self):
        D._haal, D.CACHE = self.oud_haal, self.oud_cache
        self.tmp.cleanup()

    def test_momentopname_toont_niets_van_de_laatste_24_uur(self):
        m = D.momentopname(NU, ph())
        D.controleer_leeftijd(m, NU)  # mag niet stoppen
        grens = NU - datetime.timedelta(hours=24)
        self.assertTrue(all(t <= grens for t in D.getoonde_tijden(m)))
        self.assertLessEqual(m["T"], NU - D.ANKER_LEEFTIJD)
        self.assertEqual(m["grid"]["fine_stap"], 120)  # de stap van nu (999) wordt niet gebruikt
        self.assertEqual([r["prijs"] for r in m["kopen_venster"]], [94000])
        self.assertEqual([r["prijs"] for r in m["volgende_verkopen"]], [97000])
        self.assertEqual(m["exposure"]["pct"], 41.0)
        self.assertNotIn("reason", json.dumps(m, default=str))

    def test_te_jong_tijdstip_laat_de_bouw_stoppen(self):
        m = D.momentopname(NU, ph())
        m["verkopen"].append({"t": NU - datetime.timedelta(hours=23, minutes=59), "prijs": 1.0, "strategie": "fine",
                              "trede": 9, "pct": 1.0})
        with self.assertRaises(SystemExit):
            D.controleer_leeftijd(m, NU)

    def test_te_jonge_ladderstap_laat_de_bouw_stoppen(self):
        m = D.momentopname(NU, ph())
        m["grid_t"] = NU - datetime.timedelta(hours=1)
        with self.assertRaises(SystemExit):
            D.controleer_leeftijd(m, NU)

    def test_zonder_oude_stap_geen_ladder(self):
        (D.CACHE / f"grid-{NU - datetime.timedelta(hours=30):%Y%m%dT%H%M}.json").unlink()
        m = D.momentopname(NU, ph())
        self.assertIsNone(m["grid"])
        self.assertEqual((m["fine"], m["coarse"]), ([], []))
        D.controleer_leeftijd(m, NU)

    def test_te_weinig_historie_geen_momentopname(self):
        self.assertIsNone(D.momentopname(NU, ph(uren=20)))


class Kassa(unittest.TestCase):
    def test_zonder_ids_geen_koopknop(self):
        self.assertFalse(K.live("en"))
        self.assertFalse(K.live("nl"))
        self.assertIn("wachtlijst", K.koopblok("en", "wachtlijst"))

    def test_ids_invullen_zet_de_koopknoppen_aan(self):
        """Laadt w2e_kassa opnieuw (los, in een eigen namespace) met ingevulde PADDLE_IDS; het echte bestand blijft leeg."""
        ids = {"hosted_checkout_url": "https://pay.paddle.io/checkout/hsc_01test", "kit_usd": "pri_01a",
               "updates_usd": "pri_01b", "kit_eur": "pri_01c", "updates_eur": "pri_01d"}
        src = pathlib.Path(K.__file__).read_text(encoding="utf-8")
        for sleutel, waarde in ids.items():
            src = src.replace(f'"{sleutel}": "",', f'"{sleutel}": "{waarde}",', 1)
        ns = {"__name__": "w2e_kassa_test", "__file__": K.__file__}
        exec(compile(src, K.__file__, "exec"), ns)
        self.assertTrue(ns["live"]("en") and ns["live"]("nl"))
        self.assertEqual(ns["KASSA"]["nl"]["producten"]["kit_updates"]["url"],
                         "https://pay.paddle.io/checkout/hsc_01test?price_id=pri_01c%2Cpri_01d")
        blok = ns["koopblok"]("en", "wachtlijst")
        self.assertNotIn("wachtlijst", blok)
        self.assertEqual(blok.count('type="checkbox" required'), 2)
        self.assertIn("you can lose your entire stake", blok)
        inr = ns["paddle_inrichting"]()
        self.assertEqual(inr["env_levering_prijzen"],
                         "LEVERING_PRIJZEN=pri_01a=kit:en,pri_01c=kit:nl,pri_01b=updates:en,pri_01d=updates:nl")
        self.assertEqual(inr["ontbrekend"], [])

    def test_inrichting_is_volledig(self):
        inr = K.paddle_inrichting()
        self.assertEqual(len(inr["prijzen"]), 4)
        self.assertIn("transaction.completed", inr["webhook_events"])
        self.assertIn("adjustment.created", inr["webhook_events"])
        for p in inr["producten"].values():
            self.assertNotRegex(p["beschrijving"].lower(), r"signal|advice|profit|return|rendement|winst")


if __name__ == "__main__":
    unittest.main()
