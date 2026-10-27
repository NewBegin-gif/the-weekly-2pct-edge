"""Tests voor de deploy-kit: python3 -m unittest discover -s deploy -p "test_*.py" (vanaf de repo-root)."""
import pathlib
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER.parent))

import bestanden  # noqa: E402
import publiceer_nl  # noqa: E402
from levering.instellingen import Instellingen  # noqa: E402

VOORBEELD = """{
	email x@y.z
}

theweekly2pctedge.com, www.theweekly2pctedge.com {
	root * /var/www/theweekly2pctedge.com
	import beveiliging
	header {
		Strict-Transport-Security "max-age=63072000"
		X-Content-Type-Options nosniff
	}
	header -Server
	file_server
}

ander.example {
	header X-Ander "nee"
}
"""


class Bestanden(unittest.TestCase):
    def test_env_sjabloon_kent_elke_variabele_en_heeft_geen_waarden(self):
        bron = (HIER.parent / "levering" / "instellingen.py").read_text(encoding="utf-8")
        gelezen = set(re.findall(r'_(?:s|int)\("([A-Z_]+)"', bron))
        self.assertTrue(gelezen)
        self.assertEqual(gelezen, {n for n, _ in bestanden.ENV_VARIABELEN})
        for regel in bestanden.env_sjabloon().splitlines():
            if regel and not regel.startswith("#"):
                self.assertRegex(regel, r"^[A-Z_]+=$")

    def test_unit_en_caddy_kloppen_met_de_dienst(self):
        bestand, _ = bestanden.alle()
        unit = bestand["levering.service"]
        for regel in ("EnvironmentFile=/etc/levering.env", "Restart=on-failure", "ExecStart=/usr/bin/python3 -m levering serve",
                      "WorkingDirectory=/opt/levering", "ProtectSystem=strict"):
            self.assertIn(regel, unit)
        nl = bestand["mijnbitcoinstrategie.nl.caddy"]
        poort = Instellingen().poort
        for pad in ("/webhook/*", "/download/*", "/healthz"):
            self.assertIn(f"handle {pad} {{\n\t\treverse_proxy 127.0.0.1:{poort}", nl)
            self.assertIn(f"handle {pad} {{\n\t\treverse_proxy 127.0.0.1:{poort}", bestand["theweekly2pctedge.com.proxy.caddy"])
        self.assertIn("www.mijnbitcoinstrategie.nl {\n\tredir https://mijnbitcoinstrategie.nl{uri} permanent", nl)
        self.assertIn("root * /var/www/mijnbitcoinstrategie.nl", nl)
        self.assertIn("rewrite * /404.html", nl)
        self.assertEqual(nl.count("{"), nl.count("}"))  # accolades in balans (ook {uri} en {err.status_code})

    def test_headers_worden_van_het_en_blok_overgenomen(self):
        with tempfile.TemporaryDirectory() as d:
            cf = pathlib.Path(d) / "Caddyfile"
            cf.write_text(VOORBEELD, encoding="utf-8")
            kop = bestanden.headers_uit_caddyfile(cf)
            self.assertIn("import beveiliging", kop)
            self.assertIn('Strict-Transport-Security "max-age=63072000"', kop)
            self.assertIn("header -Server", kop)
            self.assertNotIn("X-Ander", kop)
            bestand, bron = bestanden.alle(cf)
            self.assertIn("overgenomen", bron)
            self.assertIn('Strict-Transport-Security "max-age=63072000"', bestand["mijnbitcoinstrategie.nl.caddy"])
            bestanden.main(["--uit", d, "--caddyfile", str(cf)])
            self.assertEqual(sorted(p.name for p in pathlib.Path(d).iterdir() if p.name != "Caddyfile"),
                             ["levering.env.voorbeeld", "levering.service", "mijnbitcoinstrategie.nl.caddy",
                              "theweekly2pctedge.com.proxy.caddy"])

    def test_zonder_caddyfile_vaste_headers(self):
        bestand, bron = bestanden.alle()
        self.assertIn("standaardset", bron)
        self.assertIn("Strict-Transport-Security", bestand["mijnbitcoinstrategie.nl.caddy"])


class NieuweCaddyfile(unittest.TestCase):
    def setUp(self):
        self.nl = bestanden.alle()[0]["mijnbitcoinstrategie.nl.caddy"]

    def test_proxyregels_in_het_en_blok_en_nl_blok_achteraan(self):
        nieuw = bestanden.nieuwe_caddyfile(VOORBEELD, self.nl, 8740)
        en = bestanden.site_blok(nieuw, "theweekly2pctedge.com")
        self.assertIn(bestanden.MERK, en)
        self.assertIn("handle /webhook/* {\n\t\treverse_proxy 127.0.0.1:8740", en)
        self.assertIn("file_server", en)
        self.assertNotIn(bestanden.MERK, bestanden.site_blok(nieuw, "ander.example"))
        self.assertTrue(nieuw.rstrip().endswith(self.nl.rstrip()))
        self.assertEqual(nieuw.count("{"), nieuw.count("}"))
        self.assertIn("email x@y.z", nieuw)

    def test_idempotent(self):
        een = bestanden.nieuwe_caddyfile(VOORBEELD, self.nl)
        self.assertEqual(bestanden.nieuwe_caddyfile(een, self.nl), een)

    def test_zonder_en_blok_niets(self):
        with self.assertRaises(SystemExit):
            bestanden.nieuwe_caddyfile("ander.example {\n\tfile_server\n}\n", self.nl)

    def test_main_raakt_het_origineel_niet(self):
        with tempfile.TemporaryDirectory() as d:
            cf, uit = pathlib.Path(d) / "Caddyfile", pathlib.Path(d) / "nieuw" / "Caddyfile"
            cf.write_text(VOORBEELD, encoding="utf-8")
            bestanden.main(["--caddyfile", str(cf), "--nieuwe-caddyfile", str(uit), "--uit", str(pathlib.Path(d) / "x")])
            self.assertEqual(cf.read_text(encoding="utf-8"), VOORBEELD)
            self.assertIn(bestanden.MERK, uit.read_text(encoding="utf-8"))
            with self.assertRaises(SystemExit):
                bestanden.main(["--nieuwe-caddyfile", str(uit)])


class StandBy(unittest.TestCase):
    def test_zonder_paddle_geheim_alleen_linkgeheim_nodig(self):
        self.assertEqual(Instellingen(geheim="", paddle_geheim="").ontbrekend("serve"), ["geheim"])
        self.assertEqual(Instellingen(geheim="g", paddle_geheim="").ontbrekend("serve"), [])
        self.assertEqual(Instellingen(geheim="g", paddle_geheim="p", prijzen={}, smtp_host="", mail_van="").ontbrekend("serve"),
                         ["prijzen", "smtp_host", "mail_van"])


class Publiceren(unittest.TestCase):
    def test_echte_nl_site_is_publiceerbaar(self):
        self.assertEqual(publiceer_nl.controleer_bron(publiceer_nl.BRON), [])

    def test_verboden_bestanden_houden_publicatie_tegen(self):
        with tempfile.TemporaryDirectory() as d:
            bron = pathlib.Path(d)
            for v in publiceer_nl.VERPLICHT:
                (bron / v).parent.mkdir(parents=True, exist_ok=True)
                (bron / v).write_text("x")
            self.assertEqual(publiceer_nl.controleer_bron(bron), [])
            for slecht in ("LEESMIJ.md", "levering.db", ".env", "bouwpakket/kit.pdf"):
                (bron / slecht).write_text("x")
            fouten = publiceer_nl.controleer_bron(bron)
            self.assertEqual(len(fouten), 4)

    def test_rsync_opdracht(self):
        cmd = publiceer_nl.rsync_opdracht(pathlib.Path("/a/b"), "/var/www/x", True)
        self.assertEqual(cmd[:5], ["rsync", "-a", "--delete", "--itemize-changes", "--dry-run"])
        self.assertEqual(cmd[-2:], ["/a/b/", "/var/www/x/"])
        for x in (".git", "*.bak*", "*.tmp-*", "*.orig", "*.py"):
            self.assertIn(x, cmd)
        self.assertEqual(publiceer_nl.en_exclude_regel().count("--exclude"), 6)


class AuditDeploy(unittest.TestCase):
    """Review 27 okt 2026: de unit draait niet als root en is afgeschermd; geen geheimen in gegenereerde bestanden;
    wat nooit publiek mag geeft in beide site-blokken 404."""

    def unit(self):
        tekst = bestanden.alle()[0]["levering.service"]
        return {r.split("=", 1)[0]: r.split("=", 1)[1] for r in tekst.splitlines() if "=" in r and not r.startswith("#")}, tekst

    def test_unit_niet_als_root_en_afgeschermd(self):
        u, tekst = self.unit()
        self.assertEqual(u.get("User"), "levering")
        self.assertEqual(u.get("Group"), "levering")
        for sleutel, waarde in (("NoNewPrivileges", "true"), ("ProtectSystem", "strict"), ("PrivateTmp", "true"),
                                ("ReadWritePaths", "/var/lib/levering"), ("ProtectHome", "true"),
                                ("CapabilityBoundingSet", ""), ("UMask", "0077")):
            self.assertEqual(u.get(sleutel), waarde, sleutel)
        self.assertEqual(tekst.count("ReadWritePaths="), 1)
        self.assertNotIn("/root", u["ExecStart"] + u["WorkingDirectory"])

    def test_geen_geheimen_in_gegenereerde_bestanden(self):
        import os
        geheimen = {"LEVERING_GEHEIM": "s3cr3t-link", "PADDLE_WEBHOOK_GEHEIM": "pdl_ntfset_s3cr3t",
                    "PADDLE_API_SLEUTEL": "pdl_apikey_s3cr3t", "SMTP_WACHTWOORD": "smtp-s3cr3t"}
        oud = {k: os.environ.get(k) for k in geheimen}
        os.environ.update(geheimen)
        try:
            alles = "".join(bestanden.alle()[0].values())
        finally:
            for k, v in oud.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        for g in geheimen.values():
            self.assertNotIn(g, alles)

    def test_verborgen_paden_in_beide_blokken(self):
        b = bestanden.alle()[0]
        nieuw = bestanden.nieuwe_caddyfile(VOORBEELD, b["mijnbitcoinstrategie.nl.caddy"])
        en = bestanden.site_blok(nieuw, "theweekly2pctedge.com")
        nl = bestanden.site_blok(nieuw, "mijnbitcoinstrategie.nl")
        for blok in (en, nl, b["theweekly2pctedge.com.proxy.caddy"]):
            self.assertIn("respond @levering_verborgen 404", blok)
            for patroon in ("*.py", "*.md", "*.db", "*.pdf", "/levering/*", "/deploy/*", "/.git/*"):
                self.assertIn(patroon, blok)
        self.assertEqual(nieuw.count("{"), nieuw.count("}"))

    def test_caddy_proxyt_alleen_de_drie_paden(self):
        b = bestanden.alle()[0]
        for blok in (b["mijnbitcoinstrategie.nl.caddy"], b["theweekly2pctedge.com.proxy.caddy"]):
            proxied = re.findall(r"handle (\S+) \{\n\t*reverse_proxy", blok)
            self.assertEqual(sorted(proxied), ["/download/*", "/healthz", "/webhook/*"])
            self.assertEqual(blok.count("reverse_proxy"), 3)


if __name__ == "__main__":
    unittest.main()
