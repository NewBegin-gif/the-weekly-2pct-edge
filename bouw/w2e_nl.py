"""mijnbitcoinstrategie.nl: het Nederlandse/Vlaamse zusterdomein (Daan, 27 okt 2026).

Zelfde bot, zelfde data, zelfde eerlijkheidsregels; de tekst is in gewoon Nederlands geschreven, niet vertaald. Wordt
uit dezelfde run van build_logboek.py geschreven naar sites/mijnbitcoinstrategie.nl/ (eigen webroot bij het deployen;
de Engelse site moet sites/ uitsluiten). Het domein wijst nog niet naar de server.
"""
import datetime

import build_logboek as B
import w2e_dash as D
import w2e_inhoud as I
import w2e_kassa as K
import w2e_site as W

S = W.SITES["nl"]
DOEL_NL = f"{B.DOEL}".replace(".", ",")


def p(x):
    return D.f_pct(x, "nl")


def home(c):
    weken, reeks = c["weken"], c["reeks"]
    laatste = weken[-1]
    j1 = laatste[0].isocalendar()[0]
    periode = c["periode"].replace(" to ", " tot ")
    n = len(reeks)
    verlies = [x for x in reeks if x < 0]
    titel, omschr = W.TITELS[("nl", "home")]
    wide = B.grafiek(weken, 960, 340, 46, 70, 22, 34, 13, "wide", "cw", "nl")
    narrow = B.grafiek(weken, 360, 260, 42, 42, 22, 32, 6, "narrow", "cn", "nl")
    tabel = "".join(
        f'<tr><td class="lbl">{label} {start.isocalendar()[0]}</td><td><time datetime="{start}">{D.d_kort(start, "nl")}</time></td>'
        f'<td class="r">{p(x)}</td><td class="r">{"<span class=goal-met>doel gehaald</span>" if x >= B.DOEL else ("verlies" if x < 0 else "")}</td></tr>'
        for start, label, x in reversed(weken))
    strat_rijen = "".join(
        f'<tr><td><span class="code">{B.e(s["strategy"])}</span></td><td class="r">{int(s["total_trades"])}</td>'
        f'<td class="r">{p(float(s["roi_pct"]))}</td><td class="r">{float(s["median_hold_hours"]):.0f} u</td></tr>'
        for s in sorted(c["strat"], key=lambda s: -s["total_trades"]))
    lekken = "".join(
        f'<article class="leak" id="lek-{i}"><div class="leak-top"><a href="#lek-{i}" aria-label="Link naar lek {i}">Lek {i}</a><time datetime="{l["iso"]}">{B.e(l["datum"])}</time></div>'
        f'<p class="leak-fig">{B.e(l["cijfer"])}</p><p class="leak-fig-sub">{B.e(l["cijfer_uitleg"])}</p>'
        f'<h3>{B.e(l["kop"])}</h3><p class="txt">{B.e(l["uitleg"])}</p><p class="now">{B.e(l["nu"])}</p></article>'
        for i, l in enumerate(I.LEKKEN_NL, 1))
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": f"{S['url']}/#website", "name": S["naam"], "url": f"{S['url']}/",
         "inLanguage": "nl", "description": "Het openbare logboek van een live BTC-EUR-handelsbot, in procenten, en het bouwpakket om er zelf een te maken.",
         "publisher": {"@id": f"{B.SITE}/#daan"}, "author": {"@id": f"{B.SITE}/#daan"}},
        W.persoon(S),
        {"@type": "WebPage", "@id": f"{S['url']}/#webpage", "url": f"{S['url']}/", "name": titel, "description": omschr,
         "isPartOf": {"@id": f"{S['url']}/#website"}, "about": {"@id": f"{B.SITE}/#weekly-series"},
         "author": {"@id": f"{B.SITE}/#daan"}, "inLanguage": "nl", "dateModified": c["gelezen"].isoformat()},
        {"@type": "Dataset", "@id": f"{B.SITE}/#weekly-series", "name": "Gerealiseerde weekwinst van een live BTC-EUR-handelsbot",
         "description": (f"Gerealiseerde winst per kalenderweek (maandag tot zondag) van een live BTC-EUR-handelsbot op "
                         f"Bitvavo, als percentage van het kapitaal dat de bot die week had ingezet, na beurskosten op "
                         f"aankoop en verkoop. Alleen percentages, geen bedragen. Elke week verschijnt een week na afloop. "
                         f"Periode: {periode}."),
         "url": f"{B.SITE}/", "creator": {"@id": f"{B.SITE}/#daan"}, "isAccessibleForFree": True, "inLanguage": "nl",
         "temporalCoverage": f"{weken[0][0].isoformat()}/{(laatste[0] + datetime.timedelta(days=6)).isoformat()}",
         "distribution": {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{B.SITE}/weekly-series.csv"}},
    ]}
    return f"""<!DOCTYPE html>
<html lang="nl">
{W.hoofd(S, "home", graph)}
<body>
{W.kopbalk(S, "home")}
<main id="main">

<div class="hero"><div class="wrap hero-grid">
<div class="hero-head">
<p class="kicker">Live botlogboek &middot; {B.e(periode)} &middot; weken 7 dagen vertraagd</p>
<h1>De naam beloofde 2% per week. Dit verdiende de bot echt.</h1>
</div>
<aside class="answer" aria-label="Het korte antwoord">
<p class="answer-label">Mediane week &middot; gerealiseerd, na kosten</p>
<p class="hero-num">{p(c["mediaan"])}</p>
<p class="answer-sub">van het ingezette kapitaal, over {n} weken ({B.e(periode)}). Het realistische doel is {DOEL_NL}% per week.</p>
<dl class="facts">
<div><dt>Doel van {DOEL_NL}% gehaald</dt><dd>{c["raak"]} <span>van {n} weken</span></dd></div>
<div><dt>Gemiddelde week</dt><dd>{p(c["gemiddeld"])}</dd></div>
<div><dt>Beste week</dt><dd>{p(max(reeks))}</dd></div>
<div><dt>Verliesweken</dt><dd>{"geen" if not verlies else len(verlies)}{f' <span>slechtste {p(min(reeks))}</span>' if verlies else ''}</dd></div>
</dl>
<p class="answer-note">Niet in deze cijfers: posities die de bot nog vasthoudt. De afgelopen zeven dagen stonden die tussen <strong>{p(c["open_lo"])}</strong> en <strong>{p(c["open_hi"])}</strong> van de rekening. <a href="#gerealiseerd-open">Waarom dat telt</a></p>
</aside>
<div class="hero-lead">
<p>Sinds april 2026 handelt een bitcoinbot die ik bouwde dag en nacht BTC-EUR op Bitvavo, met echt geld. Hier staat elke week die hij draaide, alleen in procenten, en waar de winst weglekte.</p>
<p>Wil je zelf een bitcoin trading bot maken? Kijk dan eerst hier. Ik verkoop geen signalen, geen copy-trading en geen advies: dit is de meetlat, geen rendementsbelofte.</p>
</div>
</div></div>
<div class="edition-bar"><div class="wrap edition">
<span>Logboek tot en met <strong>{B.e(laatste[1])} {j1}</strong> (week van {D.d_lang(laatste[0], "nl")})</span>
<span>Data gelezen <time datetime="{c["gelezen"].isoformat()}">{D.d_lang(c["gelezen"], "nl")}</time></span>
<a href="/zo-werkt-het/">Zo werkt het</a>
</div></div>

<section id="weken"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>01</b> Weekoverzicht</p>
<h2>Elke week: gerealiseerde winst als % van het ingezette kapitaal</h2>
<p>Na beurskosten op zowel de aankoop als de verkoop, inclusief de zeldzame gedwongen verkopen met verlies. Elke week wordt afgezet tegen het kapitaal dat de bot die week had ingezet, dus stortingen blazen de percentages niet op.</p>
</div>
<figure class="chart" style="margin:0">
{wide}
{narrow}
<ul class="legend" aria-label="Legenda">
<li><span class="sw hit"></span>Op of boven het doel van {DOEL_NL}%</li>
<li><span class="sw below"></span>Positief, onder het doel</li>
<li><span class="sw neg"></span>Verliesweek</li>
<li><span class="sw line"></span>Doel, {DOEL_NL}%</li>
<li><span class="sw line name"></span>De naam, {B.NAAM_BELOFTE:g}%</li>
</ul>
<figcaption class="chart-note">{n} weken, {B.e(periode)}. De nieuwste week eindigde minstens zeven dagen voordat deze pagina gebouwd werd. Ga met de muis over een staaf voor de waarde, of open de tabel.</figcaption>
</figure>
<details>
<summary>Alle {n} weken als tabel</summary>
<div class="tbl" tabindex="0" role="region" aria-label="Weekresultaten"><table>
<caption class="sr">Gerealiseerde winst per week, nieuwste eerst</caption>
<thead><tr><th scope="col">Week</th><th scope="col">Begint</th><th scope="col" class="r">Gerealiseerd</th><th scope="col" class="r"><span class="sr">Status</span></th></tr></thead>
<tbody>{tabel}</tbody>
</table></div>
</details>
</div></section>

<section id="gerealiseerd-open"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>02</b> Open posities</p>
<h2>Gerealiseerd en open: wat de meeste botresultaten weglaten</h2>
<p>Elk weekcijfer hierboven is <em>gerealiseerd</em>: winst die vastligt omdat er verkocht is. De bitcoin die de bot nog vasthoudt is <em>open</em>, en die zit niet in die cijfers.</p>
</div>
<div class="two">
<div class="card">
<span class="tag in">In het weekcijfer</span>
<h3>Gerealiseerd</h3>
<p>Een positie telt mee op het moment dat hij verkocht wordt, in de week van de verkoop.</p>
<ul><li>Kosten op aankoop en verkoop zijn er al af.</li><li>De zeldzame gedwongen verkopen met verlies tellen mee.</li><li>Staat het er eenmaal in, dan verandert het niet meer.</li></ul>
</div>
<div class="card">
<span class="tag out">Niet in het weekcijfer</span>
<h3>Open</h3>
<p>Bitcoin die gekocht maar nog niet verkocht is. De waarde beweegt elke minuut mee met de koers.</p>
<ul><li>Er ligt niets vast tot er verkocht wordt.</li><li>Een dalende koers zie je hier het eerst.</li><li>Het komt pas in het weekcijfer bij verkoop.</li></ul>
</div>
</div>
<div class="range">
<h3>Open posities, afgelopen zeven dagen</h3>
<p class="small muted" style="margin:0">{D.d_kort(c["ph_van"], "nl")} tot {D.d_lang(c["ph_tot"], "nl")}: wat de open posities waard waren vergeleken met wat ervoor betaald is, als % van de rekening. Laagste en hoogste meting.</p>
{B.bereik_html(c["open_lo"], c["open_hi"], "nl")}
</div>
<div class="callout">
<p><strong>Waarom bijna elke afgesloten trade een winnaar is.</strong> De bot is zo gebouwd dat hij een positie alleen boven de aankoopprijs verkoopt. Dat is een ontwerpkeuze, geen kunde. Verliezen wachten vooral in open posities in plaats van in het weekcijfer te verschijnen. Bij een diepe daling van bitcoin wordt het open getal veel groter voordat er iets van in het weekcijfer komt.</p>
</div>
</div></section>

<section id="lekken"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>03</b> Gemeten lekken</p>
<h2>Waar de winst weglekt</h2>
<p>Een bot die alleen met winst verkoopt, verliest toch geld, alleen minder zichtbaar. Dit zijn de lekken die ik op deze bot gemeten heb, elk met de datum van meting of reparatie.</p>
</div>
<div class="leaks">{lekken}</div>
</div></section>

{W.kit_teaser(S)}

<section id="strategieen"><div class="wrap">
<div class="sec-head">
<p class="folio"><b>04</b> Strategieën</p>
<h2>Wat elke strategie deed, laatste 90 dagen</h2>
<p>De bot draait meerdere strategieën naast elkaar. Namen zoals de bot ze logt; de 90 dagen lopen tot {D.d_lang(c["gelezen"], "nl")}.</p>
</div>
<div class="tbl plain-tbl" tabindex="0" role="region" aria-label="Strategieën"><table>
<thead><tr><th scope="col">Strategie</th><th scope="col" class="r">Afgesloten trades</th><th scope="col" class="r">Rendement per trade</th><th scope="col" class="r">Mediane duur</th></tr></thead>
<tbody>{strat_rijen}</tbody>
</table></div>
<p class="chart-note">Rendement per trade = nettowinst gedeeld door het bedrag dat in die trades zat, na kosten, alleen afgesloten trades. Het is geen weekrendement: een trade kan dagen openstaan.</p>
</div></section>

<section id="over"><div class="wrap author">
<div class="mono-badge" aria-hidden="true">DH</div>
<div class="prose">
<h2>Wie dit logboek bijhoudt</h2>
<p>Ik ben Daan (Daniel Haket), oud-bankier: 23 jaar in de internationale financiële wereld. Ik woon in Rotterdam. Ik bouwde deze bot met de AI-agent van Replit, en sinds april 2026 handelt hij met echt geld BTC-EUR op Bitvavo.</p>
<p>De naam beloofde 2% per week. Dit logboek is de meetlat: wat de bot echt doet, week na week, ook wat er misging. <a href="{B.LINKEDIN}" rel="me noopener">LinkedIn</a></p>
</div>
</div></section>

<section id="volgen" style="border-bottom:0"><div class="wrap">
<div class="sec-head"><h2>Volg het logboek</h2></div>
<div class="signup">
<div class="box">
<h3>Eén eerlijke mail per week (in het Engels)</h3>
<p>Wat er aan de bot veranderde, wat er brak en wat ik heb gemeten. Geen tips.</p>
<form action="https://aibuildermarketplace.beehiiv.com/subscribe" method="get" target="_blank"><input type="hidden" name="utm_source" value="{S["bron"]}"><input type="hidden" name="utm_campaign" value="weekmail"><label class="sr" for="mail-week">E-mailadres</label><input id="mail-week" type="email" name="email" placeholder="jij@voorbeeld.nl" autocomplete="email" required><button type="submit">Aanmelden</button></form>
</div>
<div class="box">
{W.koopkaart(S, "h3")}
</div>
</div>
</div></section>

</main>
{W.voet(S, f"Weken {B.e(periode)} &middot; data gelezen op {D.d_lang(c['gelezen'], 'nl')} &middot; een nieuwe week verschijnt zeven dagen na afloop.")}
</body>
</html>
"""


def pagina_404():
    return f"""<!DOCTYPE html>
<html lang="nl">
{B.kop_html("Pagina niet gevonden | Mijn Bitcoinstrategie", "Deze pagina bestaat niet op Mijn Bitcoinstrategie.", "", robots="noindex")}
<body>
{W.kopbalk(S, "")}
<main id="main" class="doc"><div class="wrap"><div class="prose">
<p class="kicker">Fout 404</p>
<h1>Deze pagina bestaat niet</h1>
<p class="lead">Misschien zocht je een van deze:</p>
<ul>
<li><a href="/">Het logboek</a>: elke week van de bot, de open posities en de lekken.</li>
<li><a href="/bouwpakket/">Het bouwpakket</a>: bouw je eigen versie met je AI-assistent.</li>
<li><a href="/zo-werkt-het/">Zo werkt het</a>: het dashboard en de ontwerpkeuzes.</li>
</ul>
</div></div></main>
{W.voet(S)}
</body>
</html>
"""


def llms(c, m, vol):
    weken, reeks = c["weken"], c["reeks"]
    laatste = weken[-1]
    periode = c["periode"].replace(" to ", " tot ")
    q = lambda x: p(x).replace("−", "-")
    vol_regel = (f"- Gerealiseerde volatiliteit BTC-EUR op jaarbasis: {D.f_pct(vol['jaar_pct'], 'nl', False, 0)} "
                 f"({vol['n']} dagrendementen tot en met {vol['tot'].isoformat()}, Bitvavo-dagcandles)\n" if vol else "")
    exp_regel = (f"- Exposure op het momentopname-moment ({m['T']:%Y-%m-%d %H:%M} UTC): {D.f_pct(m['exposure']['pct'], 'nl', False, 1)} van het kapitaal\n"
                 if m and m.get("exposure") else "")
    return f"""# Mijn Bitcoinstrategie

> Het openbare logboek van een live BTC-EUR-handelsbot op Bitvavo (gerealiseerde winst per week als percentage van het ingezette kapitaal, na kosten, een week vertraagd), met de open posities ernaast, de gemeten lekken, en het bouwpakket: een stappenplan om met een AI-assistent je eigen versie te bouwen. Alleen percentages; geen signalen, geen advies. Data gelezen op {c["gelezen"].isoformat()}.

De site is van Daan (Daniel Haket), oud-bankier (23 jaar in de internationale financiële wereld) uit Rotterdam. Hij bouwde de bot met de AI-agent van Replit; de bot handelt sinds april 2026 met echt geld. Engelse versie: {W.SITES["en"]["url"]}/

## Pagina's
- [Het logboek]({S["url"]}/): elke week sinds {weken[0][1]} {weken[0][0].isocalendar()[0]}, gerealiseerd en open, de lekken, rendement per strategie
- [Het bouwpakket]({S["url"]}/bouwpakket/): wat je krijgt, de vier stappen, wat je nodig hebt, vragen; {K.prijs_tekst("nl")} eenmalig, updates {K.jaar_tekst("nl")} per jaar
- [Zo werkt het]({S["url"]}/zo-werkt-het/): het dashboard van de bot (minstens 24 uur oud), hoe een trade loopt, waarom bitcoin, en elke ontwerpkeuze met datum

## Actuele cijfers ({periode}, {len(reeks)} weken)
- Mediane week: {q(c["mediaan"])} gerealiseerd; gemiddelde week {q(c["gemiddeld"])}
- Doel van {DOEL_NL}% per week gehaald in {c["raak"]} van {len(reeks)} weken
- Beste week {q(max(reeks))}, slechtste week {q(min(reeks))}
- Open posities {c["ph_van"]} tot {c["ph_tot"]}: tussen {q(c["open_lo"])} en {q(c["open_hi"])} van de rekening
{exp_regel}{vol_regel}
## Regels
- Alleen percentages: nooit eurobedragen, rekeninggrootte of ordergroottes
- Weekresultaten een week vertraagd; dashboardgegevens minstens 24 uur oud
- Geen signalen, geen advies, geen copy-trading; het bouwpakket is technische documentatie, geen rendementsbelofte
- Afgelopen weken zeggen niets over komende weken; je kunt je hele inleg verliezen

## Actualiteit
- Laatste week: {laatste[1]} {laatste[0].isocalendar()[0]} (begint {laatste[0].isoformat()})
- Wordt dagelijks gecontroleerd en alleen herbouwd als er een nieuwe week bij komt; dit bestand wordt in dezelfde ronde bijgewerkt

## Contact
- [Daniel Haket op LinkedIn]({B.LINKEDIN})
"""


ROBOTS = f"""# Mijn Bitcoinstrategie: het openbare logboek van een live BTC-EUR-handelsbot en het bouwpakket.
# Alles hier mag gelezen worden, door mensen, zoekmachines en AI-crawlers.
# Samenvatting voor taalmodellen: {S["url"]}/llms.txt

User-agent: *
Allow: /

# AI-crawlers, met naam, zodat de bedoeling ondubbelzinnig is: welkom.
User-agent: GPTBot
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: ClaudeBot
User-agent: Claude-SearchBot
User-agent: Claude-User
User-agent: anthropic-ai
User-agent: PerplexityBot
User-agent: Perplexity-User
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
User-agent: meta-externalagent
User-agent: Amazonbot
User-agent: DuckAssistBot
User-agent: MistralAI-User
Allow: /

Sitemap: {S["url"]}/sitemap.xml
"""


def sitemap(lastmod):
    regels = "".join(f"  <url><loc>{S['url']}{pad}</loc><lastmod>{d}</lastmod></url>\n" for pad, d in lastmod)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{regels}</urlset>\n'
