"""Rooktest van een gepubliceerd domein (live of een lokale kopie). Alleen stdlib.

    python3 deploy/rooktest.py --domein mijnbitcoinstrategie.nl
    python3 deploy/rooktest.py --domein theweekly2pctedge.com
    python3 deploy/rooktest.py --domein theweekly2pctedge.com --checkout-live      # nadat PADDLE_IDS zijn ingevuld
    # lokaal (zie de PR): beide sites via python3 -m http.server, de dienst op 127.0.0.1:8740
    python3 deploy/rooktest.py --domein mijnbitcoinstrategie.nl \
        --map mijnbitcoinstrategie.nl=http://127.0.0.1:8772 --map theweekly2pctedge.com=http://127.0.0.1:8771 \
        --dienst http://127.0.0.1:8740

Controles
  - elke URL uit sitemap.xml geeft 200 en HTML
  - canonical = de URL zelf; elk hreflang-adres bestaat en verwijst terug (en, nl-NL, nl-BE, x-default)
  - JSON-LD parst op elke pagina
  - robots.txt (met Sitemap-regel), llms.txt, og-image.png (PNG 1200x630) bereikbaar; og:image van elke pagina ook
  - zolang de kassa uit staat: geen koopknop (form.koop), wel de wachtlijst; met --checkout-live andersom
  - webhook met foute handtekening -> 401/403; /download/ met een verlopen token -> geweigerd (4xx, geen bestand)
  - /healthz -> 200 "ok" en niets meer
  - niets wat niet publiek mag: .py, .md, database, .env, .git, de Nederlandse site onder het Engelse domein, ...
  - alleen live (https, geen --map): HTTPS-redirect, HSTS/nosniff-headers, www -> apex 301, eigen 404-pagina
Exitcode 0 = alles goed; 1 = minstens één FOUT. SKIP = kan hier niet gecontroleerd worden (staat erbij waarom).
"""
import argparse
import html.parser
import json
import re
import ssl
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

VERBODEN_PADEN = ["/levering/opslag.py", "/levering/__init__.py", "/bouw/build_logboek.py", "/deploy/rooktest.py",
                  "/.git/HEAD", "/.git/config", "/levering.db", "/var/lib/levering/levering.db", "/.env",
                  "/README.md", "/llms.md", "/.pr-screenshots/en-home-375.png", "/sites/mijnbitcoinstrategie.nl/index.html",
                  "/bouw/og-basis.png", "/test_levering.py", "/build-kit.pdf"]


class GeenRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Rooktest:
    def __init__(self, domein, kaart, dienst, checkout_live, zonder_dienst):
        self.domein, self.kaart, self.dienst = domein, kaart, dienst
        self.checkout_live, self.zonder_dienst = checkout_live, zonder_dienst
        self.live = not kaart
        self.fouten = 0
        self.cache = {}

    # --------------------------------------------------------- hulpmiddelen
    def url(self, absoluut):
        """Live: ongewijzigd. Lokaal: host via --map naar de lokale basis."""
        p = urllib.parse.urlsplit(absoluut)
        basis = self.kaart.get(p.hostname)
        if not basis:
            return absoluut
        return basis.rstrip("/") + (p.path or "/") + (f"?{p.query}" if p.query else "")

    def haal(self, url, methode="GET", body=None, koppen=None, volgen=True):
        sleutel = (url, methode, body)
        if methode == "GET" and volgen and sleutel in self.cache:
            return self.cache[sleutel]
        verzoek = urllib.request.Request(url, data=body, method=methode, headers={"User-Agent": "w2e-rooktest/1", **(koppen or {})})
        opener = urllib.request.build_opener(*( [] if volgen else [GeenRedirect()] ),
                                             urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(verzoek, timeout=30) as r:
                uit = (r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
        except urllib.error.HTTPError as e:
            uit = (e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read() or b"")
        except (urllib.error.URLError, OSError) as e:
            uit = (0, {}, str(e).encode())
        if methode == "GET" and volgen:
            self.cache[sleutel] = uit
        return uit

    def goed(self, tekst):
        print(f"  OK    {tekst}")

    def fout(self, tekst):
        self.fouten += 1
        print(f"  FOUT  {tekst}")

    def skip(self, tekst):
        print(f"  SKIP  {tekst}")

    def check(self, voorwaarde, tekst):
        (self.goed if voorwaarde else self.fout)(tekst)
        return voorwaarde

    # --------------------------------------------------------- controles
    def basis(self, pad=""):
        return self.url(f"https://{self.domein}{pad}")

    def sitemap(self):
        print("sitemap en pagina's")
        status, _, body = self.haal(self.basis("/sitemap.xml"))
        if not self.check(status == 200, f"sitemap.xml {status}"):
            return []
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [e.text.strip() for e in ET.fromstring(body).findall("s:url/s:loc", ns)]
        self.check(bool(locs) and all(urllib.parse.urlsplit(l).hostname == self.domein for l in locs),
                   f"{len(locs)} URL's, allemaal op {self.domein}")
        return locs

    def pagina(self, loc):
        status, koppen, body = self.haal(self.url(loc))
        tekst = body.decode("utf-8", "replace")
        if not self.check(status == 200 and "text/html" in koppen.get("content-type", ""),
                          f"{loc} -> {status}"):
            return
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', tekst)
        self.check(canon and canon.group(1) == loc, f"  canonical = {loc}")
        for blok in re.findall(r'<script type="application/ld\+json">(.*?)</script>', tekst, re.S):
            try:
                json.loads(blok)
            except ValueError as e:
                self.fout(f"  JSON-LD parst niet: {e}")
                break
        else:
            self.goed(f"  JSON-LD parst ({len(re.findall('application/ld+json', tekst))} blok(ken))")
        hreflang = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', tekst)
        if hreflang:
            talen = {t for t, _ in hreflang}
            self.check({"en", "nl-NL", "nl-BE", "x-default"} <= talen, f"  hreflang {sorted(talen)}")
            for taal, href in hreflang:
                s2, _, b2 = self.haal(self.url(href))
                terug = loc in re.findall(r'<link rel="alternate" hreflang="[^"]+" href="([^"]+)"', b2.decode("utf-8", "replace"))
                self.check(s2 == 200 and terug, f"  hreflang {taal} -> {href} ({s2}, verwijst terug: {terug})")
        og = re.search(r'<meta property="og:image" content="([^"]+)"', tekst)
        if og:
            self.check(self.haal(self.url(og.group(1)))[0] == 200, f"  og:image bereikbaar ({og.group(1)})")
        return tekst

    def vaste_bestanden(self):
        print("robots, llms.txt, OG")
        status, _, body = self.haal(self.basis("/robots.txt"))
        self.check(status == 200 and f"Sitemap: https://{self.domein}/sitemap.xml" in body.decode(), "robots.txt met Sitemap-regel")
        status, _, body = self.haal(self.basis("/llms.txt"))
        self.check(status == 200 and body.startswith(b"# "), f"llms.txt ({len(body)} bytes)")
        status, _, body = self.haal(self.basis("/og-image.png"))
        maat = struct.unpack(">II", body[16:24]) if body[:8] == b"\x89PNG\r\n\x1a\n" else None
        self.check(status == 200 and maat == (1200, 630), f"og-image.png {status} {maat}")

    def koopknop(self, paginas):
        print("koopknop" + (" (kassa live)" if self.checkout_live else " (kassa uit: alleen wachtlijst)"))
        for loc, tekst in paginas.items():
            if not tekst or "#buy" not in tekst:
                continue
            knop = '<form class="koop"' in tekst
            wachtlijst = "bouwnotities_aanmelding" in tekst
            risico = "you can lose your entire stake" in tekst or "je hele inleg verliezen" in tekst
            if self.checkout_live:
                if 'id="buy"' in tekst:
                    self.check(knop and 'type="checkbox" required' in tekst and risico,
                               f"{loc}: koopknop met verplicht vinkje en risicoregel")
            else:
                self.check(not knop, f"{loc}: geen koopknop")
                if 'id="buy"' in tekst:
                    self.check(wachtlijst, f"{loc}: wachtlijst staat er")

    def dienst_checks(self):
        print("levering (webhook, download, healthz)")
        if self.zonder_dienst:
            self.skip("--zonder-dienst: webhook/download/healthz niet gecontroleerd")
            return
        basis = (self.dienst or self.basis()).rstrip("/")
        body = json.dumps({"event_id": f"evt_rooktest_{uuid.uuid4().hex}", "event_type": "transaction.completed",
                           "data": {}}).encode()
        status, _, _ = self.haal(f"{basis}/webhook/paddle", "POST", body,
                                 {"Content-Type": "application/json", "Paddle-Signature": "ts=1;h1=" + "0" * 64})
        self.check(status in (401, 403), f"webhook met foute handtekening -> {status}")
        token = f"rooktest.1.{'A' * 43}"  # verlopen (1970) en niet geldig getekend
        status, koppen, body = self.haal(f"{basis}/download/{token}")
        self.check(400 <= status < 500 and not body.startswith(b"%PDF"), f"/download/ met verlopen token -> {status}")
        status, koppen, body = self.haal(f"{basis}/healthz")
        self.check(status == 200 and body.strip() == b"ok", f"/healthz -> {status} {body[:20]!r}")

    def verboden(self):
        print("niets wat niet publiek mag")
        for pad in VERBODEN_PADEN + [f"/rooktest-{uuid.uuid4().hex[:8]}.md"]:
            if pad.startswith("/sites/") and self.domein != "theweekly2pctedge.com":
                continue
            status, _, body = self.haal(self.basis(pad))
            self.check(status != 200, f"{pad} -> {status}")

    def niet_gevonden(self):
        status, _, body = self.haal(self.basis(f"/bestaat-niet-{uuid.uuid4().hex[:8]}/"))
        self.check(status == 404, f"onbekende pagina -> {status}")
        if b'content="noindex"' in body:
            self.goed("eigen 404-pagina (noindex)")
        elif self.live:
            self.fout("eigen 404-pagina ontbreekt (Caddy handle_errors)")
        else:
            self.skip("eigen 404-pagina: alleen live (lokaal antwoordt http.server zelf)")

    def alleen_live(self):
        print("alleen live: HTTPS, headers, www")
        if not self.live:
            self.skip("HTTPS-redirect, HSTS/nosniff, www -> apex 301: alleen live (lokaal is er geen TLS of Caddy)")
            return
        status, koppen, _ = self.haal(f"http://{self.domein}/", volgen=False)
        self.check(status in (301, 302, 308) and koppen.get("location", "").startswith("https://"), f"http -> https ({status})")
        status, k, _ = self.haal(f"https://{self.domein}/")
        self.check("strict-transport-security" in k, "HSTS-header")
        self.check(k.get("x-content-type-options", "").lower() == "nosniff", "X-Content-Type-Options: nosniff")
        if self.domein == "mijnbitcoinstrategie.nl":
            status, koppen, _ = self.haal(f"https://www.{self.domein}/bouwpakket/", volgen=False)
            self.check(status == 301 and koppen.get("location") == f"https://{self.domein}/bouwpakket/",
                       f"www -> apex 301 ({status} {koppen.get('location')})")

    def draai(self):
        print(f"Rooktest {self.domein} ({'live' if self.live else 'lokaal via ' + ', '.join(self.kaart.values())})")
        locs = self.sitemap()
        paginas = {loc: self.pagina(loc) for loc in locs}
        self.vaste_bestanden()
        self.koopknop(paginas)
        self.dienst_checks()
        print("fouten en afscherming")
        self.niet_gevonden()
        self.verboden()
        self.alleen_live()
        print(f"\n{'GESLAAGD' if not self.fouten else f'{self.fouten} FOUT(EN)'}")
        return 1 if self.fouten else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--domein", required=True)
    p.add_argument("--map", action="append", default=[], help="host=basis-URL, voor een lokale kopie (herhaalbaar)")
    p.add_argument("--dienst", help="basis-URL van de leveringsdienst als die niet achter --domein zit (lokaal)")
    p.add_argument("--checkout-live", action="store_true")
    p.add_argument("--zonder-dienst", action="store_true")
    a = p.parse_args(argv)
    kaart = dict(m.split("=", 1) for m in a.map)
    return Rooktest(a.domein, kaart, a.dienst, a.checkout_live, a.zonder_dienst).draai()


if __name__ == "__main__":
    sys.exit(main())
