"""De HTTP-dienst (stdlib http.server), achter Caddy op 127.0.0.1.

  POST <voorvoegsel>/paddle/webhook   Paddle Billing-notificaties (handtekening verplicht)
  GET  <voorvoegsel>/download/<token> het document, als de link geldig is (verloop + aantal)
  GET  <voorvoegsel>/gezond           200 "ok" voor monitoring
Alles anders: 404. Antwoorden zijn kort en lekken niets over de reden aan een vreemde (behalve 'verlopen').
"""
import http.server
import logging
import shutil

from .kern import Levering

log = logging.getLogger("levering")
MAX_BODY = 1_000_000


def maak_handler(levering: Levering):
    voorvoegsel = levering.cfg.voorvoegsel.rstrip("/")

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "levering"
        sys_version = ""

        def _pad(self):
            pad = self.path.split("?", 1)[0]
            return pad[len(voorvoegsel):] if voorvoegsel and pad.startswith(voorvoegsel) else pad

        def _antwoord(self, status, tekst):
            data = tekst.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self._pad() != "/paddle/webhook":
                return self._antwoord(404, "niet gevonden")
            lengte = int(self.headers.get("Content-Length") or 0)
            if lengte <= 0 or lengte > MAX_BODY:
                return self._antwoord(413 if lengte > MAX_BODY else 400, "ongeldige body")
            body = self.rfile.read(lengte)
            status, tekst = levering.webhook(body, self.headers.get("Paddle-Signature"))
            self._antwoord(status, tekst)

        def do_GET(self):
            pad = self._pad()
            if pad == "/gezond":
                return self._antwoord(200, "ok")
            if not pad.startswith("/download/"):
                return self._antwoord(404, "niet gevonden")
            bestand, naam = levering.download(pad[len("/download/"):])
            if not bestand:
                reden = naam
                log.info("download geweigerd: %s", reden)
                tekst = {"verlopen": "This link has expired. Reply to your delivery email for a new one.",
                         "op": "This link has reached its download limit. Reply to your delivery email for a new one."}
                return self._antwoord(410 if reden in ("verlopen", "op") else 404, tekst.get(reden, "not found"))
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf" if bestand.suffix == ".pdf" else "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{naam}"')
            self.send_header("Content-Length", str(bestand.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Robots-Tag", "noindex")
            self.end_headers()
            with bestand.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)

        def log_message(self, fmt, *args):  # tokens niet in het log
            log.info("%s %s", self.command, self._pad().split("/download/")[0] + ("/download/…" if "/download/" in self.path else ""))

    return Handler


def serve(levering: Levering):
    adres = ("127.0.0.1", levering.cfg.poort)
    server = http.server.ThreadingHTTPServer(adres, maak_handler(levering))
    log.info("levering luistert op %s:%s (voorvoegsel %s)", *adres, levering.cfg.voorvoegsel)
    server.serve_forever()
