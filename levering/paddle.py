"""Paddle Billing: handtekening controleren en events vertalen.

Handtekening (developer.paddle.com/webhooks/signature-verification): header `Paddle-Signature: ts=<unix>;h1=<hex>`,
tijdens het roteren van het geheim soms meerdere h1. Getekend wordt "<ts>:<ruwe body>" met HMAC-SHA256 en het geheim
van de notificatiebestemming. Altijd op de ruwe bytes controleren, nooit op opnieuw geserialiseerde JSON. Een te oude
ts wordt geweigerd (replay); dubbele afleveringen vangt de events-tabel op event_id.

Events die we gebruiken
  customer.created / customer.updated   e-mail en taal bij een customer_id onthouden
  transaction.completed                 betaling rond: kit -> leveringsmail; met subscription_id -> abonnement verlengd
  subscription.created / .activated / .updated / .canceled / .past_due / .paused / .resumed
                                         abonneestatus en einde van de lopende periode bijwerken
De webhook bevat bij een transactie alleen customer_id; staat het e-mailadres nog niet in de klanten-tabel, dan
halen we het op met GET /customers/{id} (PADDLE_API_SLEUTEL).
"""
import hashlib
import hmac
import json
import re
import time
import urllib.request

from .opslag import lees_iso


class OngeldigeHandtekening(Exception):
    pass


_TS = re.compile(r"[0-9]{1,12}")
_H1 = re.compile(r"[0-9a-f]{64}")


def controleer_handtekening(kop, body, geheim, tolerantie=300, nu=None):
    """Gooit OngeldigeHandtekening, of geeft de tijdstempel terug."""
    if not geheim:
        raise OngeldigeHandtekening("geen webhookgeheim ingesteld")
    if not kop:
        raise OngeldigeHandtekening("Paddle-Signature ontbreekt")
    ts, h1s = None, []
    for deel in kop.split(";"):
        sleutel, _, waarde = deel.strip().partition("=")
        if sleutel == "ts":
            ts = waarde
        elif sleutel == "h1":
            h1s.append(waarde)
    h1s = [h for h in h1s if _H1.fullmatch(h)]  # alleen ASCII-hex: compare_digest gooit anders TypeError
    if not ts or not _TS.fullmatch(ts) or not h1s:
        raise OngeldigeHandtekening("Paddle-Signature onleesbaar")
    nu = time.time() if nu is None else nu
    if abs(nu - int(ts)) > tolerantie:
        raise OngeldigeHandtekening("handtekening te oud of uit de toekomst")
    if isinstance(body, str):
        body = body.encode()
    verwacht = hmac.new(geheim.encode(), ts.encode() + b":" + body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(verwacht, h) for h in h1s):
        raise OngeldigeHandtekening("handtekening klopt niet")
    return int(ts)


def teken(body, geheim, ts=None):
    """Voor tests en handmatig proberen: maak een geldige Paddle-Signature-header."""
    ts = str(int(time.time() if ts is None else ts))
    if isinstance(body, str):
        body = body.encode()
    return f"ts={ts};h1=" + hmac.new(geheim.encode(), ts.encode() + b":" + body, hashlib.sha256).hexdigest()


def klant_email_ophalen(customer_id, api_url, sleutel):
    if not sleutel:
        return None, None
    verzoek = urllib.request.Request(f"{api_url.rstrip('/')}/customers/{customer_id}",
                                     headers={"Authorization": f"Bearer {sleutel}"})
    with urllib.request.urlopen(verzoek, timeout=20) as r:
        data = json.load(r).get("data") or {}
    return data.get("email"), _taal(data.get("locale"))


def _taal(locale):
    return "nl" if (locale or "").lower().startswith("nl") else ("en" if locale else None)


def prijzen(data):
    """Alle price-id's in een transactie of abonnement."""
    uit = []
    for item in data.get("items") or []:
        prijs = item.get("price") or {}
        pid = prijs.get("id") or item.get("price_id")
        if pid:
            uit.append(pid)
    return uit


def periode_einde(data):
    for sleutel in ("current_billing_period", "billing_period"):
        per = data.get(sleutel) or {}
        if per.get("ends_at"):
            return lees_iso(per["ends_at"])
    return None
