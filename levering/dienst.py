"""De HTTP-dienst (stdlib http.server), alleen op 127.0.0.1 achter Caddy (ufw laat alleen 22/80/443 door).

Caddy stuurt op beide domeinen deze paden door (deploy/bestanden.py schrijft de regels):
  POST /webhook/paddle        Paddle Billing-notificaties (handtekening verplicht; fout = 401)
  GET  /download/<token>      het document, als de link geldig is (handtekening, verloop, aantal, niet ingetrokken)
  GET  /healthz               200 "ok" of 503 "unavailable" (alleen: database bereikbaar). Geen tellingen, geen
                              versie, geen paden: niets wat een buitenstaander iets vertelt.
Alles anders: 404. De dienst draait een achtergronddraad die elke LEVERING_WACHTRIJ_SEC de wachtrij met
leveringsmails afwerkt (mislukte SMTP-pogingen).
"""
import http.server
import logging
import shutil
import threading

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
            self.send_header("X-Robots-Tag", "noindex")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self._pad() != "/webhook/paddle":
                return self._antwoord(404, "not found")
            try:
                lengte = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                lengte = 0
            if lengte <= 0 or lengte > MAX_BODY:
                return self._antwoord(413 if lengte > MAX_BODY else 400, "bad request")
            body = self.rfile.read(lengte)
            status, tekst = levering.webhook(body, self.headers.get("Paddle-Signature"))
            self._antwoord(status, tekst)

        def do_GET(self):
            pad = self._pad()
            if pad == "/healthz":
                return self._antwoord(200, "ok") if levering.opslag.gezond() else self._antwoord(503, "unavailable")
            if not pad.startswith("/download/"):
                return self._antwoord(404, "not found")
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
            pad = self._pad()
            log.info("%s %s", self.command, "/download/…" if pad.startswith("/download/") else pad)

    return Handler


def wachtrij_draad(levering: Levering, stop: threading.Event):
    while not stop.wait(levering.cfg.wachtrij_sec):
        try:
            ok, fout = levering.wachtrij()
            if ok or fout:
                log.info("wachtrij: %s verzonden, %s opnieuw later", ok, fout)
        except Exception:
            log.exception("wachtrij mislukt")


def maak_server(levering: Levering, poort=None):
    return http.server.ThreadingHTTPServer(("127.0.0.1", levering.cfg.poort if poort is None else poort),
                                           maak_handler(levering))


def serve(levering: Levering):
    server = maak_server(levering)
    stop = threading.Event()
    threading.Thread(target=wachtrij_draad, args=(levering, stop), daemon=True).start()
    log.info("levering luistert op 127.0.0.1:%s", server.server_address[1])
    try:
        server.serve_forever()
    finally:
        stop.set()
