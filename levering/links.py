"""Getekende, verlopende downloadlinks.

Token = "<id>.<verloopt-unix>.<handtekening>", handtekening = HMAC-SHA256(LEVERING_GEHEIM, "<id>.<verloopt>"),
base64url zonder opvulling. De handtekening laat geraden of aangepaste tokens vallen zonder databasewerk; de database
bewaakt daarnaast verloop en het aantal downloads (standaard 72 uur, 5 keer), zodat een link ook in te trekken is.
"""
import base64
import datetime
import hashlib
import hmac
import secrets


def _sig(geheim, inhoud):
    ruw = hmac.new(geheim.encode(), inhoud.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(ruw).rstrip(b"=").decode()


def maak(opslag, geheim, email, versie, uren, maximum, nu=None):
    if not geheim:
        raise RuntimeError("LEVERING_GEHEIM ontbreekt")
    nu = nu or datetime.datetime.now(datetime.timezone.utc)
    link_id = secrets.token_urlsafe(18)
    verloopt = (nu + datetime.timedelta(hours=uren)).replace(microsecond=0)
    opslag.link_bewaar(link_id, email, versie, verloopt, maximum)
    inhoud = f"{link_id}.{int(verloopt.timestamp())}"
    return link_id, f"{inhoud}.{_sig(geheim, inhoud)}"


def controleer(token, geheim, nu=None):
    """Geeft (link_id, None) of (None, reden). Raakt de database niet."""
    nu = nu or datetime.datetime.now(datetime.timezone.utc)
    delen = (token or "").split(".")
    if len(delen) != 3 or not delen[1].isdigit():
        return None, "onleesbaar"
    link_id, verloopt, sig = delen
    if not hmac.compare_digest(_sig(geheim, f"{link_id}.{verloopt}"), sig):
        return None, "handtekening"
    if int(verloopt) <= nu.timestamp():
        return None, "verlopen"
    return link_id, None
