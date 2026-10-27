"""Kassa van het bouwpakket: aanbieder, prijzen en checkout-URL's per product en munt (Daan, 27 okt 2026).

Daan wil Paddle. Zolang een checkout-URL leeg is, rendert er GEEN koopknop: dan staat het wachtlijstformulier er
(zelfde Beehiiv-actie, verborgen velden en GA4-event als altijd). Er werkt dus nooit iets half.

Producten
  kit           het bouwplan, eenmalig ($14 op theweekly2pctedge.com, EUR 14 op mijnbitcoinstrategie.nl)
  kit_updates   het bouwplan + een jaar updates (bij elke wijziging aan de bot het nieuwe plan per mail;
                daarna $5 / EUR 5 per jaar, jaarlijks opzegbaar)

Paddle (Billing): maak in Paddle > Checkout > Hosted checkout een hosted checkout en zet hier de launch-URL met de
price_id('s), bijvoorbeeld https://pay.paddle.io/checkout/hsc_...?price_id=pri_... (kit_updates: twee price_id's,
komma als %2C: de eenmalige kit-prijs en de jaarprijs). Het adapter controleert alleen de vorm (https, host van
Paddle) en zet de queryparameters om in verborgen velden, omdat de knop een GET-formulier is: een verplicht vinkje
voor de EU-regels over digitale inhoud werkt zo zonder JavaScript, en een GET-formulier zou de query van de action
anders weggooien.

Een andere aanbieder (zie de PR voor alternatieven) = een adapter met dezelfde twee functies toevoegen aan ADAPTERS.
"""
import urllib.parse

import build_logboek as B

AANBIEDER = "paddle"
KASSA = {
    "en": {"munt": "USD", "teken": "$", "producten": {
        "kit": {"prijs": "14", "url": ""},
        "kit_updates": {"prijs": "14", "jaar": "5", "url": ""},
    }},
    "nl": {"munt": "EUR", "teken": "€", "producten": {
        "kit": {"prijs": "14", "url": ""},
        "kit_updates": {"prijs": "14", "jaar": "5", "url": ""},
    }},
}

# EU-regels digitale inhoud (richtlijn 2011/83/EU art. 16(m)): uitdrukkelijke toestemming voor directe levering én
# erkenning dat het herroepingsrecht van 14 dagen daarmee vervalt. Het vinkje is verplicht; Paddle toont daarnaast
# zijn eigen voorwaarden in de checkout.
TOESTEMMING = {
    "en": ("I want the download to start immediately, and I understand that I lose my 14-day right of withdrawal "
           "once delivery has started."),
    "nl": ("Ik wil dat de download direct begint, en ik begrijp dat ik mijn herroepingsrecht van 14 dagen verlies "
           "zodra de levering is begonnen."),
}
RISICO = {
    "en": "Past weeks say nothing about future weeks; you can lose your entire stake.",
    "nl": "Afgelopen weken zeggen niets over komende weken; je kunt je hele inleg verliezen.",
}


def _paddle_controle(url):
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ""
    if p.scheme != "https" or not (host == "paddle.io" or host.endswith(".paddle.io") or host == "paddle.com"
                                   or host.endswith(".paddle.com")):
        raise SystemExit(f"kassa: {url!r} is geen https-URL van Paddle (pay.paddle.io / buy.paddle.com)")


def _paddle_formulier(url):
    """(action, verborgen velden) voor een GET-formulier dat dezelfde URL opent."""
    p = urllib.parse.urlsplit(url)
    action = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))
    return action, urllib.parse.parse_qsl(p.query, keep_blank_values=True)


ADAPTERS = {"paddle": (_paddle_controle, _paddle_formulier)}


def producten(taal):
    """De producten met een ingevulde, gecontroleerde URL, in vaste volgorde."""
    controle, _ = ADAPTERS[AANBIEDER]
    live = []
    for sleutel in ("kit", "kit_updates"):
        p = KASSA[taal]["producten"][sleutel]
        if p.get("url"):
            controle(p["url"])
            live.append((sleutel, p))
    return live


def live(taal):
    """De kit zelf moet te koop zijn; alleen het abonnement zonder kit telt niet."""
    return any(s == "kit" for s, _ in producten(taal))


def prijs_tekst(taal, sleutel="kit"):
    k = KASSA[taal]
    p = k["producten"][sleutel]
    return f'{k["teken"]}{p["prijs"]}'


def jaar_tekst(taal):
    k = KASSA[taal]
    return f'{k["teken"]}{k["producten"]["kit_updates"]["jaar"]}'


def koopblok(taal, wachtlijst_html, ga_label="bouwpakket"):
    """De koopknoppen (met verplicht toestemmingsvinkje en risicoregel), of de wachtlijst als niets live is."""
    if not live(taal):
        return wachtlijst_html
    _, formulier = ADAPTERS[AANBIEDER]
    knoppen = []
    teksten = {
        "en": {"kit": ("The build kit", f"{prijs_tekst('en')} one-off", "Buy the build kit"),
               "kit_updates": ("Build kit + updates", f"{prijs_tekst('en')} + {jaar_tekst('en')} a year for updates",
                               "Buy kit with updates")},
        "nl": {"kit": ("Het bouwpakket", f"{prijs_tekst('nl')} eenmalig", "Koop het bouwpakket"),
               "kit_updates": ("Bouwpakket + updates", f"{prijs_tekst('nl')} + {jaar_tekst('nl')} per jaar voor updates",
                               "Koop met updates")},
    }[taal]
    for i, (sleutel, p) in enumerate(producten(taal)):
        naam, prijs, knop = teksten[sleutel]
        action, velden = formulier(p["url"])
        verborgen = "".join(f'<input type="hidden" name="{B.e(k)}" value="{B.e(v)}">' for k, v in velden)
        knoppen.append(f"""<form class="koop" action="{B.e(action)}" method="get" onsubmit="if(window.gtag)gtag('event','{ga_label}_checkout',{{product:'{sleutel}'}})">
{verborgen}<p class="koop-naam">{naam}</p><p class="koop-prijs">{prijs}</p>
<label class="toestemming"><input type="checkbox" required> <span>{B.e(TOESTEMMING[taal])}</span></label>
<button type="submit">{knop}</button>
</form>""")
    return f"""<div class="koopknoppen">{''.join(knoppen)}</div>
<p class="risico">{B.e(RISICO[taal])}</p>"""


def aanbiedingen_ld(taal, url):
    """schema.org Offer's; availability alleen als de kassa live is."""
    k = KASSA[taal]
    is_live = live(taal)
    kit = {"@type": "Offer", "name": "Build kit" if taal == "en" else "Bouwpakket", "price": f'{k["producten"]["kit"]["prijs"]}.00',
           "priceCurrency": k["munt"], "url": url, "category": "one-off"}
    upd = {"@type": "Offer", "name": "Update subscription" if taal == "en" else "Update-abonnement",
           "price": f'{k["producten"]["kit_updates"]["jaar"]}.00', "priceCurrency": k["munt"], "url": url,
           "priceSpecification": {"@type": "UnitPriceSpecification", "price": f'{k["producten"]["kit_updates"]["jaar"]}.00',
                                  "priceCurrency": k["munt"],
                                  "referenceQuantity": {"@type": "QuantitativeValue", "value": 1, "unitCode": "ANN"}}}
    if is_live:
        for o in (kit, upd):
            o["availability"] = "https://schema.org/InStock"
    return [kit, upd]
