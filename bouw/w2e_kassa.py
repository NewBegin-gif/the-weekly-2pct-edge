"""Kassa van het bouwpakket: aanbieder, prijzen en checkout-URL's per product en munt (Daan, 27 okt 2026).

Daan wil Paddle. Zolang de client-side token of een prijs-id leeg is, rendert er GEEN koopknop: dan staat het
wachtlijstformulier er (zelfde Beehiiv-actie, verborgen velden en GA4-event als altijd). Er werkt nooit iets half.

Producten
  kit           het bouwplan, eenmalig ($14 op theweekly2pctedge.com, EUR 14 op mijnbitcoinstrategie.nl)
  kit_updates   het bouwplan + een jaar updates (bij elke wijziging aan de bot het nieuwe plan per mail;
                daarna $5 / EUR 5 per jaar, jaarlijks opzegbaar)

Paddle (Billing): de knop opent de overlay-checkout van Paddle.js (Paddle.Checkout.open) met de prijs-id('s) en
custom_data {withdrawal_consent: <versie van de vinktekst>, consent_at: <tijdstip van klikken>}. Paddle zet die
custom_data op de transactie (en kopieert hem naar het abonnement); levering/kern.py levert de kit alleen als hij er
staat en legt versie en tijdstip vast (EU-herroepingsrecht, richtlijn 2011/83/EU art. 16(m)). Daarom geen hosted
checkout meer: die neemt geen custom_data via de URL, en Paddle geeft hosted checkouts op live-accounts alleen aan
goedgekeurde mobiele-app-bedrijven (developer.paddle.com/paddlejs/hosted-checkout-url-parameters). Paddle.js wordt pas
geladen bij de eerste klik op een koopknop (geen extern script bij het openen van de pagina). Zonder JavaScript: een
melding, geen checkout. Wie de vinktekst verandert, verhoogt TOESTEMMING_VERSIE.

Een andere aanbieder (zie de PR voor alternatieven) = een adapter met dezelfde twee functies toevoegen aan ADAPTERS.
"""
import json
import re
import sys

sys.dont_write_bytecode = True  # ook als dit bestand los gedraaid wordt: geen .pyc naast de webroot
import build_logboek as B  # noqa: E402

AANBIEDER = "paddle"

# ---- Daan vult alleen dit in (uit het Paddle-dashboard). Leeg = geen koopknop, de wachtlijst blijft staan.
# Wat er in Paddle aangemaakt moet worden en hoe je test: python3 bouw/w2e_kassa.py (zie paddle_inrichting()).
PADDLE_OMGEVING = "production"  # "sandbox" alleen lokaal tijdens het testen, nooit committen
PADDLE_IDS = {
    "client_token": "",         # Developer tools > Authentication > client-side token (live_... / test_...): publiek
    "kit_usd": "",              # pri_01... eenmalig 14.00 USD
    "updates_usd": "",          # pri_01... 5.00 USD per jaar
    "kit_eur": "",              # pri_01... eenmalig 14.00 EUR
    "updates_eur": "",          # pri_01... 5.00 EUR per jaar
}


def _prijzen(*prijs_ids):
    """De prijs-id's van één koopknop, of [] als er een ontbreekt (dan geen knop)."""
    return list(prijs_ids) if PADDLE_IDS["client_token"].strip() and all(prijs_ids) else []


KASSA = {
    "en": {"munt": "USD", "teken": "$", "producten": {
        "kit": {"prijs": "14", "prijzen": _prijzen(PADDLE_IDS["kit_usd"])},
        "kit_updates": {"prijs": "14", "jaar": "5", "prijzen": _prijzen(PADDLE_IDS["kit_usd"], PADDLE_IDS["updates_usd"])},
    }},
    "nl": {"munt": "EUR", "teken": "€", "producten": {
        "kit": {"prijs": "14", "prijzen": _prijzen(PADDLE_IDS["kit_eur"])},
        "kit_updates": {"prijs": "14", "jaar": "5", "prijzen": _prijzen(PADDLE_IDS["kit_eur"], PADDLE_IDS["updates_eur"])},
    }},
}

WEBHOOK_EVENTS = ["transaction.completed", "customer.created", "customer.updated", "subscription.created",
                  "subscription.activated", "subscription.updated", "subscription.canceled", "subscription.past_due",
                  "subscription.paused", "subscription.resumed", "adjustment.created", "adjustment.updated"]


def paddle_inrichting():
    """Alles wat Paddle nodig heeft, op één plek. Daan maakt dit aan in Paddle en vult daarna alleen PADDLE_IDS in.

    Producten (Catalog > Products), elk met tax category "digital-goods" (staat die niet open: aanvragen bij Paddle;
    tot dan "standard"):
      Bitcoin bot build kit          eenmalige download, de documentatie
      Build kit updates (yearly)     jaarabonnement, bijgewerkte documentatie per mail
    Prijzen (per product, Catalog > Prices), tax mode "internal" (prijs inclusief btw, zodat $14 / EUR 14 is wat de
    koper betaalt, zoals de site zegt):
      kit_usd      14.00 USD  eenmalig
      kit_eur      14.00 EUR  eenmalig
      updates_usd   5.00 USD  per jaar (billing cycle: 1 year)
      updates_eur   5.00 EUR  per jaar (billing cycle: 1 year)
    Client-side token (Developer tools > Authentication): in PADDLE_IDS["client_token"] (publiek, mag in git).
    Default payment link (Checkout > Checkout settings): https://theweekly2pctedge.com/build-kit/ ; voeg beide domeinen
    toe aan de goedgekeurde domeinen (Checkout > Website approval), anders opent de overlay niet.
    Notification destination (Developer tools > Notifications): URL https://theweekly2pctedge.com/webhook/paddle,
    events = WEBHOOK_EVENTS, het geheim gaat in /etc/levering.env (PADDLE_WEBHOOK_GEHEIM). API-sleutel met alleen
    "customers: read" in PADDLE_API_SLEUTEL.

    Sandbox-test (eerst, met sandbox-vendors.paddle.com en PADDLE_API_URL=https://sandbox-api.paddle.com):
      1. Maak bovenstaande producten, prijzen, hosted checkout en notification destination aan in de sandbox.
      2. Vul PADDLE_IDS met de sandbox-ID's en zet PADDLE_OMGEVING = "sandbox" (lokaal, niet committen), bouw met
         --forceer en open /build-kit/ via python3 -m http.server: vink aan, klik, de overlay opent.
      3. Betaal met Paddle's sandbox-testkaart (4242 4242 4242 4242, toekomstige datum, CVC 100). Controleer: mail
         met link komt binnen, de link werkt 5 keer, de 6e keer 410.
      4. Koop "kit + updates": `python3 -m levering abonnees` toont het adres.
      5. Stuur in Paddle een event opnieuw (Notifications > event > Replay): de dienst antwoordt "al verwerkt".
      6. Refund de transactie in de sandbox: de link geeft daarna 404 ("ingetrokken"), het adres staat niet meer bij
         `abonnees`.
      6b. Koop zonder vinkje via de browserconsole (Paddle.Checkout.open zonder customData): geen mail;
         `python3 -m levering aankopen` toont de transactie.
      7. Zet SMTP even fout in /etc/levering.env, koop opnieuw: geen mail, wel een rij in de wachtrij; zet SMTP terug
         en draai `python3 -m levering wachtrij`: de mail gaat alsnog.
      8. Daarna productie: dezelfde stappen 1 met de live-ID's, PADDLE_API_URL=https://api.paddle.com, nieuw geheim,
         PADDLE_IDS invullen + committen, build met --forceer, deploy/rooktest.py --checkout-live.
    Geeft een dict met dezelfde gegevens, plus wat er nog ontbreekt en de LEVERING_PRIJZEN-regel voor /etc/levering.env.
    """
    producten = {
        "kit": {"naam": "Bitcoin bot build kit", "tax_category": "digital-goods", "type": "eenmalig",
                "beschrijving": ("Downloadable software documentation: a step-by-step build plan for setting up and "
                                 "running your own instance of an open grid-trading bot with an AI coding assistant. "
                                 "Digital download, delivered by email.")},
        "updates": {"naam": "Build kit updates (yearly)", "tax_category": "digital-goods", "type": "jaarabonnement",
                    "beschrijving": ("Yearly subscription: updated versions of the build kit documentation by email "
                                     "whenever the documented software changes. Cancel any time.")},
    }
    prijzen = [
        {"sleutel": "kit_usd", "product": "kit", "bedrag": "14.00", "munt": "USD", "cyclus": None},
        {"sleutel": "kit_eur", "product": "kit", "bedrag": "14.00", "munt": "EUR", "cyclus": None},
        {"sleutel": "updates_usd", "product": "updates", "bedrag": "5.00", "munt": "USD", "cyclus": "1 year"},
        {"sleutel": "updates_eur", "product": "updates", "bedrag": "5.00", "munt": "EUR", "cyclus": "1 year"},
    ]
    for p in prijzen:
        p["id"] = PADDLE_IDS[p["sleutel"]]
        p["tax_mode"] = "internal"
    taal = {"usd": "en", "eur": "nl"}
    levering_prijzen = ",".join(f'{p["id"]}={p["product"]}:{taal[p["sleutel"].split("_")[1]]}' for p in prijzen if p["id"])
    return {
        "producten": producten, "prijzen": prijzen, "webhook_events": WEBHOOK_EVENTS,
        "webhook_url": "https://theweekly2pctedge.com/webhook/paddle",
        "koopknoppen": {f"{t}/{s}": KASSA[t]["producten"][s]["prijzen"] for t in ("en", "nl") for s in ("kit", "kit_updates")},
        "omgeving": PADDLE_OMGEVING,
        "env_levering_prijzen": f"LEVERING_PRIJZEN={levering_prijzen}",
        "ontbrekend": [k for k, v in PADDLE_IDS.items() if not v],
    }

# EU-regels digitale inhoud (richtlijn 2011/83/EU art. 16(m)): uitdrukkelijke toestemming voor directe levering én
# erkenning dat het herroepingsrecht van 14 dagen daarmee vervalt. Het vinkje is verplicht en gaat als
# custom_data.withdrawal_consent (= de versie hieronder) mee naar Paddle; de dienst levert niet zonder. Paddle toont
# daarnaast zijn eigen voorwaarden in de checkout. Tekst veranderd -> versie ophogen (datum).
TOESTEMMING_VERSIE = {"en": "en-2026-10-27", "nl": "nl-2026-10-27"}
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


def _paddle_controle(prijzen):
    token = PADDLE_IDS["client_token"].strip()
    if not re.fullmatch(r"(live|test)_[A-Za-z0-9]{10,64}", token):
        raise SystemExit(f"kassa: client_token {token!r} is geen client-side token van Paddle (live_... of test_...)")
    if PADDLE_OMGEVING not in ("production", "sandbox") or (PADDLE_OMGEVING == "sandbox") != token.startswith("test_"):
        raise SystemExit("kassa: PADDLE_OMGEVING en client_token horen bij elkaar (sandbox = test_, production = live_)")
    for pid in prijzen:
        if not re.fullmatch(r"pri_[a-z0-9]{10,40}", pid):
            raise SystemExit(f"kassa: {pid!r} is geen Paddle-prijs-id (pri_...)")


# Eén script per pagina: laadt Paddle.js bij de eerste koop-klik en opent de overlay met de toestemming als custom_data.
PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js"


def _paddle_script(taal, ga_label):
    instellingen = json.dumps({"token": PADDLE_IDS["client_token"].strip(), "sandbox": PADDLE_OMGEVING == "sandbox",
                               "taal": taal, "js": PADDLE_JS, "ga": ga_label})
    return """<script>(function(){var K=%s,klaar=null;
function laad(){return klaar||(klaar=new Promise(function(ok,fout){var s=document.createElement('script');s.src=K.js;
s.onload=function(){if(K.sandbox)Paddle.Environment.set('sandbox');Paddle.Initialize({token:K.token});ok();};
s.onerror=fout;document.head.appendChild(s);}));}
document.querySelectorAll('form.koop').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();
if(!f.toestemming.checked)return;var p=f.dataset.prijzen.split(',');if(window.gtag)gtag('event',K.ga+'_checkout',{product:f.dataset.product});
laad().then(function(){Paddle.Checkout.open({items:p.map(function(id){return{priceId:id,quantity:1};}),
customData:{withdrawal_consent:f.dataset.toestemming,consent_at:new Date().toISOString()},settings:{locale:K.taal}});},
function(){f.querySelector('.koop-fout').hidden=false;});});});})();</script>""" % instellingen


ADAPTERS = {"paddle": (_paddle_controle, _paddle_script)}


def producten(taal):
    """De producten met ingevulde, gecontroleerde prijs-id's, in vaste volgorde."""
    controle, _ = ADAPTERS[AANBIEDER]
    live = []
    for sleutel in ("kit", "kit_updates"):
        p = KASSA[taal]["producten"][sleutel]
        if p.get("prijzen"):
            controle(p["prijzen"])
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


def risico_html(taal):
    """De risicoregel die naast elke knop met een prijs staat."""
    return f'<p class="risico">{B.e(RISICO[taal])}</p>'


def koopblok(taal, wachtlijst_html, ga_label="bouwpakket"):
    """De koopknoppen (met verplicht toestemmingsvinkje en risicoregel), of de wachtlijst als niets live is."""
    if not live(taal):
        return f'{wachtlijst_html}\n<p class="risico">{B.e(RISICO[taal])}</p>'
    _, script = ADAPTERS[AANBIEDER]
    fout = {"en": "The checkout could not load. Check your connection or ad blocker and try again.",
            "nl": "De kassa kon niet laden. Controleer je verbinding of adblocker en probeer het opnieuw."}[taal]
    zonder_js = {"en": "The checkout (Paddle) needs JavaScript.", "nl": "De kassa (Paddle) heeft JavaScript nodig."}[taal]
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
        knoppen.append(f"""<form class="koop" action="#" data-product="{sleutel}" data-prijzen="{B.e(','.join(p['prijzen']))}" data-toestemming="{TOESTEMMING_VERSIE[taal]}">
<p class="koop-naam">{naam}</p><p class="koop-prijs">{prijs}</p>
<label class="toestemming"><input type="checkbox" name="toestemming" required> <span>{B.e(TOESTEMMING[taal])}</span></label>
<button type="submit">{knop}</button>
<p class="koop-fout" role="alert" hidden>{fout}</p>
</form>""")
    return f"""<div class="koopknoppen">{''.join(knoppen)}</div>
<noscript><p class="risico">{zonder_js}</p></noscript>
<p class="risico">{B.e(RISICO[taal])}</p>
{script(taal, ga_label)}"""


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


if __name__ == "__main__":
    import json
    import sys
    sys.dont_write_bytecode = True
    print(json.dumps(paddle_inrichting(), indent=2, ensure_ascii=False))
