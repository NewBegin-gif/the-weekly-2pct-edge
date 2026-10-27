"""Paginabouw voor het bouwpakket op twee domeinen (Daan, 27 okt 2026).

theweekly2pctedge.com (Engels, in de repo-root)        mijnbitcoinstrategie.nl (Nederlands, sites/mijnbitcoinstrategie.nl/)
  /                logboek + bouwpakket                  /                 logboek + bouwpakket
  /build-kit/      wat je krijgt, 4 stappen, kopen       /bouwpakket/      idem
  /how-it-works/   dashboard + ontwerpkeuzes             /zo-werkt-het/    idem
  /method/         rekenmethode (alleen Engels)
Elk paar is via hreflang aan elkaar gekoppeld (en, nl-NL, nl-BE; x-default = Engels). Geen andere pagina's, geen reeks.

Eén koopweg op elke pagina: de knop rechtsboven en een koopblok (w2e_kassa.koopblok; zonder checkout-URL de wachtlijst).
Kopteksten en beschrijvingen staan per pagina hieronder en blijven binnen 60 / 155 tekens (de bouw controleert dat).
"""
import datetime
import statistics

import build_logboek as B
import w2e_dash as D
import w2e_inhoud as I
import w2e_kassa as K

SITES = {
    "en": dict(taal="en", url="https://theweekly2pctedge.com", naam="The Weekly 2% Edge", locale="en_US",
               paden=dict(home="/", kit="/build-kit/", werking="/how-it-works/", methode="/method/"),
               nav=[("werking", "How it works"), ("methode", "Method")], cta="Build kit",
               og_alt=B.OG_ALT, bron="theweekly2pctedge"),
    "nl": dict(taal="nl", url="https://mijnbitcoinstrategie.nl", naam="Mijn Bitcoinstrategie", locale="nl_NL",
               paden=dict(home="/", kit="/bouwpakket/", werking="/zo-werkt-het/"),
               nav=[("werking", "Zo werkt het")], cta="Bouwpakket",
               og_alt=("Mijn Bitcoinstrategie: de gerealiseerde weekwinst van een live bitcoinbot in procenten, "
                       "tegen het doel van 0,5% en de 2% uit de naam."),
               bron="mijnbitcoinstrategie"),
}
PAREN = ("home", "kit", "werking")  # pagina's die op beide domeinen bestaan

TITELS = {
    ("en", "kit"): ("Build Your Own Bitcoin Trading Bot with AI: The Build Kit",
                    "A step-by-step plan your AI assistant executes to build your own version of a live BTC-EUR bot. "
                    "$14 one-off, updates $5 a year. No signals, no promises."),
    ("en", "werking"): ("How a Live Bitcoin Grid Bot Works: Dashboard and Decisions",
                        "A live BTC-EUR bot's dashboard, at least 24 hours old: exposure, buy ladder, sell orders, "
                        "every sale, the weekly result, and why each rule exists."),
    ("nl", "home"): ("Bitcoin bot bouwen? Het eerlijke logboek van een echte bot",
                     "Zelf een bitcoin trading bot maken? Zie eerst wat een echte Bitvavo-bot elke week verdiende, in "
                     "procenten na kosten. Plus het bouwpakket voor je AI."),
    ("nl", "kit"): ("Bitcoin trading bot zelf maken met AI: het bouwpakket",
                    "Een stappenplan dat je AI-assistent uitvoert om je eigen versie van een live Bitvavo-bot te "
                    "bouwen. €14 eenmalig, updates €5 per jaar. Geen signalen."),
    ("nl", "werking"): ("Zo werkt een Bitvavo-bot: dashboard en ontwerpkeuzes",
                        "Het dashboard van een live BTC-EUR-bot, minstens 24 uur oud: exposure, koopladder, "
                        "verkooporders, elke verkoop, het weekresultaat en waarom elke regel er is."),
}


def url(S, sleutel):
    return S["url"] + S["paden"][sleutel]


def hreflang(sleutel):
    if sleutel not in PAREN:
        return ""
    en, nl = url(SITES["en"], sleutel), url(SITES["nl"], sleutel)
    return (f'<link rel="alternate" hreflang="en" href="{en}">\n<link rel="alternate" hreflang="nl-NL" href="{nl}">\n'
            f'<link rel="alternate" hreflang="nl-BE" href="{nl}">\n<link rel="alternate" hreflang="x-default" href="{en}">\n')


def social(S, titel, omschr, pagina_url, soort="website"):
    og = S["url"] + "/og-image.png"
    return f"""<meta property="og:type" content="{soort}">
<meta property="og:site_name" content="{B.e(S["naam"])}">
<meta property="og:title" content="{B.e(titel)}">
<meta property="og:description" content="{B.e(omschr)}">
<meta property="og:url" content="{pagina_url}">
<meta property="og:locale" content="{S["locale"]}">
<meta property="og:image" content="{og}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{B.e(S["og_alt"])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{B.e(titel)}">
<meta name="twitter:description" content="{B.e(omschr)}">
<meta name="twitter:image" content="{og}">
<meta name="twitter:image:alt" content="{B.e(S["og_alt"])}">
"""


def hoofd(S, sleutel, graph, soort="website"):
    titel, omschr = TITELS[(S["taal"], sleutel)]
    u = url(S, sleutel)
    return B.kop_html(titel, omschr, u, hreflang(sleutel) + social(S, titel, omschr, u, soort) + B.ld(graph))


def kopbalk(S, actief):
    nl = S["taal"] == "nl"
    links = "".join(
        f'<a href="{S["paden"][k]}"{" aria-current=" + chr(34) + "page" + chr(34) if k == actief else ""}>{t}</a>'
        for k, t in S["nav"])
    cta_attr = ' aria-current="page"' if actief == "kit" else ""
    return f"""<a class="skip" href="#main">{"Naar de inhoud" if nl else "Skip to content"}</a>
<header class="top"><div class="wrap">
<a class="brand" href="/">{B.MERK}<span>{B.e(S["naam"])}</span></a>
<nav class="nav" aria-label="{"Hoofdmenu" if nl else "Main"}">{links}<a class="cta" href="{S["paden"]["kit"]}#buy"{cta_attr}>{S["cta"]}</a></nav>
</div></header>"""


DISCLAIMER_NL = ("Dit is een persoonlijk logboek, geen financieel advies en geen beleggingsdienst; het bouwpakket is "
                 "software-documentatie. Crypto is "
                 "volatiel en je kunt je hele inleg verliezen. Afgelopen weken zeggen niets over komende weken. Ik "
                 "beheer geen geld voor anderen en verkoop geen signalen. &mdash; Daan, Rotterdam")


def voet(S, regel=""):
    if S["taal"] == "en":
        return B.voet(regel)
    return f"""<footer class="foot"><div class="wrap">
<p class="disclaimer">{DISCLAIMER_NL}</p>
{f'<p>{regel}</p>' if regel else ''}<ul class="foot-links">
<li><a href="/">Het logboek</a></li><li><a href="/bouwpakket/">Bouwpakket</a></li><li><a href="/zo-werkt-het/">Zo werkt het</a></li><li><a href="{SITES["en"]["url"]}/" hreflang="en" lang="en">English</a></li><li><a href="{B.LINKEDIN}" rel="me noopener">Daniel Haket op LinkedIn</a></li>
</ul>
</div></footer>"""


def persoon(S):
    p = B.persoon()
    if S["taal"] == "nl":
        p = dict(p, description="Oud-bankier (23 jaar in de internationale financiële wereld) in Rotterdam die de bot bouwde en draait.")
    return p


def kruimel(S, sleutel, naam):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "The logbook" if S["taal"] == "en" else "Het logboek", "item": url(S, "home")},
        {"@type": "ListItem", "position": 2, "name": naam, "item": url(S, sleutel)}]}


# ---------------------------------------------------------------- wachtlijst (zelfde formulier, zelfde event)

def wachtlijst(S):
    """Het bestaande Beehiiv-formulier: action, verborgen velden en GA4-event ongewijzigd; alleen de tekst gaat over
    het bouwpakket. Op het NL-domein is utm_source anders, zodat Beehiiv de herkomst ziet."""
    nl = S["taal"] == "nl"
    tekst = ("Het bouwpakket is nog niet te koop. Laat je e-mailadres achter, dan hoor je het als het zover is."
             if nl else "The build kit isn't on sale yet. Leave your email and you'll hear when it is.")
    knop = "Laat het me weten" if nl else "Tell me when it's out"
    lab = "E-mailadres" if nl else "Email address"
    ph = "jij@voorbeeld.nl" if nl else "you@example.com"
    return f"""<p>{tekst}</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank" onsubmit="if(window.gtag)gtag('event','bouwnotities_aanmelding')"><input type="hidden" name="utm_source" value="{S["bron"]}"><input type="hidden" name="utm_campaign" value="bouwnotities"><label class="sr" for="mail-notes">{lab}</label><input id="mail-notes" type="email" name="email" placeholder="{ph}" autocomplete="email" required><button type="submit">{knop}</button></form>"""


def koopkaart(S, kop_niveau="h2"):
    """De ene koopplek per pagina (id=buy): prijs, wat erin zit, knoppen of wachtlijst."""
    taal = S["taal"]
    nl = taal == "nl"
    prijs, jaar = K.prijs_tekst(taal), K.jaar_tekst(taal)
    return f"""<div class="koopkaart" id="buy">
<{kop_niveau} class="koop-kop">{"Het bouwpakket" if nl else "The build kit"}</{kop_niveau}>
<p class="koop-groot"><span class="prijs">{prijs}</span> <span class="muted">{"eenmalig" if nl else "one-off"}</span></p>
<p class="koop-sub">{"Updates zodra de bot of het plan verandert:" if nl else "Updates whenever the bot or the plan changes:"} <span class="prijs">{jaar}</span> {"per jaar, opzegbaar" if nl else "a year, cancel any time"}.</p>
{K.koopblok(taal, wachtlijst(S))}
</div>"""


def stappen_html(taal):
    return '<ol class="stappen">' + "".join(
        f'<li><span class="stap-nr">{i}</span><h3>{B.e(k)}</h3><p>{B.e(t)}</p></li>'
        for i, (k, t) in enumerate(I.STAPPEN[taal], 1)) + "</ol>"


def kit_teaser(S):
    """Blok op de homepage: wat het bouwpakket is, de 4 stappen, en de weg naar kopen."""
    nl = S["taal"] == "nl"
    if nl:
        kop, tekst = ("Bouw je eigen versie, met je AI",
                      "Het bouwpakket is het stappenplan van deze bot, geschreven zodat een AI-assistent het met je "
                      "uitvoert. Geen signalen, geen copy-trading: je bouwt en draait je eigen software.")
        knop, meer = f"Bekijk het bouwpakket · {K.prijs_tekst('nl')}", "Of zie eerst hoe het werkt"
    else:
        kop, tekst = ("Build your own version, with your AI",
                      "The build kit is this bot's step-by-step plan, written so an AI assistant can carry it out with "
                      "you. No signals, no copy-trading: you build and run your own software.")
        knop, meer = f"See the build kit · {K.prijs_tekst('en')}", "Or first see how it works"
    return f"""<section id="kit" class="kit-teaser"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>★</b> {"Bouwpakket" if nl else "Build kit"}</p>
<h2>{kop}</h2>
<p>{tekst}</p>
</div>
{stappen_html(S["taal"])}
<p class="teaser-knoppen"><a class="btn" href="{S["paden"]["kit"]}">{knop}</a> <a href="{S["paden"]["werking"]}">{meer}</a></p>
{K.risico_html(S["taal"])}
</div></section>"""


def _lijst(paren):
    return '<ul class="kaartlijst">' + "".join(f"<li><h3>{B.e(k)}</h3><p>{B.e(t)}</p></li>" for k, t in paren) + "</ul>"


def kit_pagina(S, c):
    taal = S["taal"]
    nl = taal == "nl"
    titel, omschr = TITELS[(taal, "kit")]
    faq = I.FAQ[taal]
    product = {"@type": "Product", "@id": url(S, "kit") + "#product",
               "name": "Bouwpakket: bouw je eigen bitcoinbot met AI" if nl else "Build kit: build your own bitcoin bot with AI",
               "description": omschr, "image": S["url"] + "/og-image.png", "category": "Software documentation",
               "brand": {"@type": "Brand", "name": S["naam"]}, "offers": K.aanbiedingen_ld(taal, url(S, "kit") + "#buy")}
    # Product/Offer alleen als er echt iets te koop is: zonder kassa zou Google een product tonen dat niet te kopen is
    te_koop = K.live(taal)
    webpagina = {"@type": "WebPage", "@id": url(S, "kit"), "url": url(S, "kit"), "name": titel, "description": omschr,
                 "inLanguage": taal, "isPartOf": {"@id": url(S, "home") + "#website"}, "author": {"@id": f"{B.SITE}/#daan"}}
    if te_koop:
        webpagina["about"] = {"@id": url(S, "kit") + "#product"}
    graph = {"@context": "https://schema.org", "@graph": [
        webpagina, *([product] if te_koop else []), persoon(S), kruimel(S, "kit", "Bouwpakket" if nl else "Build kit"),
        {"@type": "FAQPage", "@id": url(S, "kit") + "#faq",
         "mainEntity": [{"@type": "Question", "name": v, "acceptedAnswer": {"@type": "Answer", "text": a}} for v, a in faq]},
    ]}
    med = D.f_pct(c["mediaan"], taal)
    n = len(c["reeks"])
    if nl:
        intro = ("Dit is het stappenplan van de bitcoinbot uit het logboek, geschreven zodat een AI-assistent hem "
                 "samen met jou bouwt. Je krijgt de logica, de veiligheidscontroles en de lessen uit elke fout. Je "
                 "krijgt géén belofte over wat hij oplevert. De naam beloofde 2% per week; het realistische doel bleek 0,5%, en "
                 "ook dat is geen belofte.")
        echt = (f"Dezelfde bot staat in het logboek: {n} weken, mediaan {med} gerealiseerd per week na kosten; de "
                f"open posities staan ernaast. Afgelopen weken zeggen niets over komende weken; je kunt je hele inleg "
                f"verliezen.")
        koppen = ("Zo werkt het, in vier stappen", "Wat je krijgt", "Wat het niet is", "Wat je nodig hebt",
                  "Maak er je eigen bot van", "Veelgestelde vragen")
        links_tekst = ("Bekijk het logboek", "Zie het dashboard en de ontwerpkeuzes")
    else:
        intro = ("This is the step-by-step plan of the bitcoin bot in the logbook, written so an AI assistant builds it "
                 "with you. You get the logic, the safety checks and the lessons from every mistake. You don't get a "
                 "promise about what it will make. The name promised 2% a week; the realistic goal turned out to be 0.5%, and "
                 "that isn't a promise either.")
        echt = (f"The same bot is in the logbook: {n} weeks, a median of {med} realized per week after fees; its "
                f"open positions are shown next to it. Past weeks say nothing about future weeks; you can lose your "
                f"entire stake.")
        koppen = ("How it works, in four steps", "What you get", "What it isn't", "What you need",
                  "Make it yours", "Questions")
        links_tekst = ("See the logbook", "See the dashboard and design decisions")
    faq_html = "".join(f'<details class="faq"><summary>{B.e(v)}</summary><p>{B.e(a)}</p></details>' for v, a in faq)
    return f"""<!DOCTYPE html>
<html lang="{taal}">
{hoofd(S, "kit", graph)}
<body>
{kopbalk(S, "kit")}
<main id="main">
<div class="hero kit-hero"><div class="wrap kit-grid">
<div>
<nav class="crumbs" aria-label="{"Kruimelpad" if nl else "Breadcrumb"}"><a href="/">{"Het logboek" if nl else "The logbook"}</a> &rsaquo; {"Bouwpakket" if nl else "Build kit"}</nav>
<p class="kicker">{"Bouwpakket · voor je AI-assistent" if nl else "Build kit · for your AI assistant"}</p>
<h1>{"Bouw je eigen bitcoin trading bot, met je AI als bouwer" if nl else "Build your own bitcoin trading bot, with your AI doing the building"}</h1>
<p class="lead-groot">{intro}</p>
<p class="echt">{echt} <a href="/">{links_tekst[0]}</a> · <a href="{S["paden"]["werking"]}">{links_tekst[1]}</a></p>
</div>
{koopkaart(S)}
</div></div>

<section id="steps"><div class="wrap">
<div class="sec-head"><h2>{koppen[0]}</h2></div>
{stappen_html(taal)}
</div></section>

<section id="get"><div class="wrap two-col">
<div><h2>{koppen[1]}</h2>{_lijst(I.KRIJG[taal])}</div>
<div><h2>{koppen[2]}</h2><ul class="niet">{"".join(f"<li>{B.e(x)}</li>" for x in I.NIET[taal])}</ul></div>
</div></section>

<section id="need"><div class="wrap">
<div class="sec-head"><h2>{koppen[3]}</h2></div>
{_lijst(I.NODIG[taal])}
</div></section>

<section id="yours"><div class="wrap">
<div class="sec-head"><h2>{koppen[4]}</h2><p>{B.e(I.AANPASSEN[taal])}</p></div>
<ul class="voorbeelden">{"".join(f"<li>{B.e(v)}</li>" for v in I.VOORBEELDEN[taal])}</ul>
<p><a href="{S["paden"]["werking"]}#decisions">{"Elke ontwerpkeuze, met datum en reden" if nl else "Every design decision, with its date and why"}</a></p>
</div></section>

<section id="faq" style="border-bottom:0"><div class="wrap">
<div class="sec-head"><h2>{koppen[5]}</h2></div>
<div class="faqs">{faq_html}</div>
<p class="terug"><a class="btn" href="#buy">{"Naar het bouwpakket" if nl else "Back to the build kit"} · {K.prijs_tekst(taal)}</a></p>
{K.risico_html(taal)}
</div></section>
</main>
{voet(S)}
</body>
</html>
"""


def werking_pagina(S, c, m, vol):
    taal = S["taal"]
    nl = taal == "nl"
    titel, omschr = TITELS[(taal, "werking")]
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "TechArticle", "@id": url(S, "werking") + "#article", "headline": titel, "description": omschr,
         "url": url(S, "werking"), "mainEntityOfPage": url(S, "werking"), "inLanguage": taal,
         "author": {"@id": f"{B.SITE}/#daan"}, "image": S["url"] + "/og-image.png",
         "dateModified": c["gelezen"].isoformat()},
        persoon(S), kruimel(S, "werking", "Zo werkt het" if nl else "How it works"),
    ]}
    weken = c["weken"]
    wide = B.grafiek(weken, 960, 300, 46, 70, 22, 34, 13, "wide", f"ww-{taal}", taal)
    narrow = B.grafiek(weken, 360, 240, 42, 42, 22, 32, 6, "narrow", f"wn-{taal}", taal)
    keuzes = "".join(
        f'<li class="keuze" id="{k["id"]}"><p class="keuze-wanneer">{B.e(k["wanneer"])}</p><h3>{B.e(k["kop"])}</h3>'
        f'<p>{B.e(k["waarom"])}</p><p class="keuze-ai"><span>{"Zeg tegen je AI" if nl else "Tell your AI"}</span> {B.e(k["ai"])}</p></li>'
        for k in I.KEUZES[taal])
    if vol:
        jaar = D.f_pct(vol["jaar_pct"], taal, False, 0)
        dag = D.f_pct(vol["mediaan_dag_pct"], taal, False, 1)
        if nl:
            vol_html = (f'<p class="vol-getal">{jaar}</p><p class="vol-sub">gerealiseerde volatiliteit op jaarbasis, '
                        f'{vol["n"]} dagrendementen tot en met {D.d_lang(vol["tot"], taal)}</p>'
                        f'<p>Op een gewone dag beweegt bitcoin ongeveer {dag} (mediaan van de dagelijkse beweging in dat '
                        f'venster). Een ladder die op kleine stappen koopt en een paar procent hoger verkoopt, heeft '
                        f'die beweging nodig: zonder schommelingen gebeurt er niets.</p>'
                        f'<p class="small muted">Methode: dagcandles BTC-EUR van de publieke Bitvavo-API, '
                        f'standaardafwijking van de dagelijkse log-rendementen van de slotkoers, maal √365 (bitcoin '
                        f'handelt elke dag). Wordt opnieuw berekend telkens als deze pagina wordt bijgewerkt.</p>')
        else:
            vol_html = (f'<p class="vol-getal">{jaar}</p><p class="vol-sub">realized volatility, annualised, '
                        f'{vol["n"]} daily returns up to {D.d_lang(vol["tot"], taal)}</p>'
                        f'<p>On an ordinary day bitcoin moves about {dag} (median daily move in that window). A '
                        f'ladder that buys in small steps and sells a few percent higher needs that movement: without '
                        f'swings, nothing happens.</p>'
                        f'<p class="small muted">Method: daily BTC-EUR candles from Bitvavo\'s public API, standard '
                        f'deviation of the daily log returns of the close, times √365 (bitcoin trades every day). '
                        f'Recomputed every time this page is built.</p>')
    else:
        vol_html = ("<p>De volatiliteit kon deze keer niet berekend worden (de koersdata van Bitvavo was niet "
                    "bereikbaar).</p>" if nl else
                    "<p>Volatility could not be computed in this build (Bitvavo's price data was not reachable).</p>")
    if nl:
        stroom = [("De ladder wacht", "Onder de koers staan limiet-kooporders op vaste afstanden: een fijne en een grove ladder."),
                  ("Een dip vult een trede", "Daalt de koers, dan wordt een order gevuld. Dat wordt een positie met een eigen aankoopprijs."),
                  ("Elke positie krijgt een eigen verkoop", "Direct erna staat een limiet-verkooporder klaar, een paar procent boven die aankoopprijs."),
                  ("Verkopen alleen met winst", "Een positie wordt nooit onder zijn aankoopprijs verkocht. Wat in de min staat, wacht."),
                  ("Het weekcijfer", "Alleen wat verkocht is telt mee in het weekresultaat, na kosten aan beide kanten.")]
        kop_d, kop_s, kop_b, kop_w, kop_k = ("Het dashboard, minstens 24 uur oud", "Zo loopt één trade",
                                             "Waarom bitcoin", "Het weekresultaat", "De ontwerpkeuzes, en waarom")
        d_intro = ("Dit is wat de bot zelf ziet, in procenten en BTC-koersen. Het is een momentopname van minstens 24 "
                   "uur geleden, zodat het nooit een signaal is om op te handelen.")
        k_intro = ("Elke regel in de bot heeft een geschiedenis. Hier staan de belangrijkste, met datum, wat er "
                   "gemeten werd en hoe je hem met één zin aan je AI verandert.")
        cta = f'Bouw je eigen versie: het bouwpakket · {K.prijs_tekst("nl")}'
        h1 = "Zo werkt de bot: het dashboard en de keuzes erachter"
        lead = ("Een bitcoinbot die op Bitvavo met echt geld BTC-EUR handelt. Hieronder zie je zijn dashboard zoals "
                "het een dag geleden was, hoe één trade verloopt, waarom het om bitcoin draait, en elke ontwerpkeuze "
                "met de reden erachter.")
    else:
        stroom = [("The ladder waits", "Limit buy orders sit below the price at fixed distances: a fine and a coarse ladder."),
                  ("A dip fills a rung", "When the price falls, an order fills. It becomes a position with its own buy price."),
                  ("Each position gets its own sale", "Straight after, a limit sell order waits a few percent above that buy price."),
                  ("Only sold at a profit", "A position is never sold below its buy price. What is down, waits."),
                  ("The weekly figure", "Only what is sold counts in the weekly result, after fees on both sides.")]
        kop_d, kop_s, kop_b, kop_w, kop_k = ("The dashboard, at least 24 hours old", "How one trade runs",
                                             "Why bitcoin", "The weekly result", "The design decisions, and why")
        d_intro = ("This is what the bot itself sees, in percentages and BTC prices. It is a snapshot from at least 24 "
                   "hours ago, so it is never a signal to trade on.")
        k_intro = ("Every rule in the bot has a history. These are the main ones, with their date, what was measured, "
                   "and how one sentence to your AI changes it.")
        cta = f'Build your own version: the build kit · {K.prijs_tekst("en")}'
        h1 = "How the bot works: its dashboard and the decisions behind it"
        lead = ("A bitcoin bot that trades BTC-EUR on Bitvavo with real money. Below: its dashboard as it was a day "
                "ago, how one trade runs, why it is bitcoin, and every design decision with the reason behind it.")
    stroom_html = '<ol class="stroom">' + "".join(f"<li><h3>{B.e(k)}</h3><p>{B.e(t)}</p></li>" for k, t in stroom) + "</ol>"
    return f"""<!DOCTYPE html>
<html lang="{taal}">
{hoofd(S, "werking", graph, "article")}
<body>
{kopbalk(S, "werking")}
<main id="main">
<div class="hero"><div class="wrap">
<nav class="crumbs" aria-label="{"Kruimelpad" if nl else "Breadcrumb"}"><a href="/">{"Het logboek" if nl else "The logbook"}</a> &rsaquo; {"Zo werkt het" if nl else "How it works"}</nav>
<p class="kicker">{"Live bot · BTC-EUR · Bitvavo" if nl else "Live bot · BTC-EUR · Bitvavo"}</p>
<h1>{h1}</h1>
<p class="lead-groot">{lead}</p>
</div></div>

<section id="dashboard" class="dash"><div class="wrap">
<div class="sec-head"><p class="folio"><b>01</b> {"Dashboard" if nl else "Dashboard"}</p><h2>{kop_d}</h2><p>{d_intro}</p></div>
{D.dashboard(m, taal)}
</div></section>

<section id="flow"><div class="wrap">
<div class="sec-head"><p class="folio"><b>02</b> {"Werking" if nl else "Mechanics"}</p><h2>{kop_s}</h2></div>
{stroom_html}
</div></section>

<section id="why-bitcoin"><div class="wrap two-col">
<div><p class="folio"><b>03</b> {"Onderliggende waarde" if nl else "Underlying"}</p><h2>{kop_b}</h2></div>
<div class="vol">{vol_html}</div>
</div></section>

<section id="weekly"><div class="wrap">
<div class="sec-head"><p class="folio"><b>04</b> {"Resultaat" if nl else "Result"}</p><h2>{kop_w}</h2>
<p>{"Gerealiseerde winst per week als % van het ingezette kapitaal, na kosten, een week vertraagd." if nl else "Realized profit per week as % of the capital in play, after fees, one week delayed."} <a href="/">{"Het hele logboek" if nl else "The full logbook"}</a></p></div>
<figure class="chart" style="margin:0">{wide}{narrow}</figure>
</div></section>

<section id="decisions" style="border-bottom:0"><div class="wrap">
<div class="sec-head"><p class="folio"><b>05</b> {"Ontwerp" if nl else "Design"}</p><h2>{kop_k}</h2><p>{k_intro}</p></div>
<ol class="keuzes">{keuzes}</ol>
<p class="terug"><a class="btn" href="{S["paden"]["kit"]}#buy">{cta}</a></p>
{K.risico_html(taal)}
</div></section>
</main>
{voet(S)}
</body>
</html>
"""
