"""Teksten voor het bouwpakket en 'hoe het werkt', Engels en Nederlands (Daan, 27 okt 2026).

Geen vertaling van elkaar: elke taal is apart geschreven, met dezelfde feiten. Elke datum en elk percentage hier komt
uit LEKKEN in build_logboek.py of uit het ontwerplogboek van de bot (CLAUDE.md / replit.md in de private bot-repo,
gelezen 27 okt 2026); wat de pagina uit de data haalt (volatiliteit, RSI-rem aan/uit) staat níet hier.
Regels: geen advies, geen signalen, geen rendementsbelofte; de bot kan verliezen.
"""

STAPPEN = {
    "en": [
        ("Download the plan", "One document that describes this bot's design step by step, with a few deliberately safer defaults, written for an AI assistant to carry out."),
        ("Hand it to your AI", "Upload it into Claude, ChatGPT or a similar assistant and let it walk you through every step: code, database, alerts, deployment."),
        ("Open an exchange account", "Create an account at a crypto exchange and an API key for the bot (view and trade only, never withdrawal). The plan is written for Bitvavo's BTC-EUR market; it also explains how to port it to another exchange."),
        ("Have fun", "Start in paper mode, then with the smallest amounts the exchange allows. Once live it trades with real money, and you can lose it."),
    ],
    "nl": [
        ("Download het plan", "Eén document dat het ontwerp van deze bot stap voor stap beschrijft, met een paar bewust veiligere standaardinstellingen, zo geschreven dat een AI-assistent het kan uitvoeren."),
        ("Geef het aan je AI", "Zet het in Claude, ChatGPT of een vergelijkbare assistent en laat die je door elke stap leiden: code, database, meldingen, livegang."),
        ("Open een account bij een beurs", "Maak een account aan bij een cryptobeurs en maak daar een API-sleutel voor de bot (alleen bekijken en handelen, nooit opnemen). Het plan is geschreven voor de BTC-EUR-markt van Bitvavo en legt ook uit hoe je overstapt naar een andere beurs."),
        ("Veel plezier", "Begin op papier, daarna met de kleinste bedragen die de beurs toestaat. Eenmaal live handelt hij met echt geld, en dat kun je kwijtraken."),
    ],
}

KRIJG = {
    "en": [
        ("The build plan", "One document in 14 build phases, each with acceptance tests: the exchange wrapper and a paper exchange, the buy ladder, the sells, risk limits, the database, Telegram or Discord alerts, a read-only dashboard, integrity checks, deployment and backups. Plus the dated design decisions, going live, and what to do when it breaks. Version 1.1 (27 Oct 2026); PDF, in English."),
        ("Delivered by email", "Right after payment you get a download link (valid for 72 hours, up to 5 downloads)."),
        ("Updates, if you want them", "With the update subscription, whenever the bot or the plan changes, you get the new version by email with a short changelog. It renews yearly; cancel any time."),
    ],
    "nl": [
        ("Het bouwplan", "Eén document in 14 bouwfasen, elk met acceptatietests: de beurskoppeling en een papieren beurs, de koopladder, de verkopen, de risicolimieten, de database, meldingen via Telegram of Discord, een dashboard om mee te kijken, integriteitscontroles, livegang en back-ups. Plus de ontwerpkeuzes met datum, live gaan, en wat je doet als er iets stukgaat. Versie 1.1 (27 okt 2026); pdf, in het Nederlands."),
        ("Per e-mail", "Direct na betaling krijg je een downloadlink (72 uur geldig, maximaal 5 downloads)."),
        ("Updates, als je wilt", "Met het update-abonnement krijg je de nieuwe versie per mail zodra de bot of het plan verandert, met een korte lijst van wat er veranderd is. Het wordt elk jaar verlengd; je kunt altijd opzeggen."),
    ],
}

NODIG = {
    "en": [
        ("An AI assistant", "Claude, ChatGPT or similar, one that can handle a long document. Expect about a dozen evenings."),
        ("An exchange account with API keys", "Keys with view and trade rights only, never withdrawal. The plan is written for Bitvavo (BTC-EUR) and includes a prompt to port it to another exchange; testing that port is up to you."),
        ("Telegram or Discord", "For alerts: fills, sales, warnings, the daily summary."),
        ("A GitHub account", "A private repository, to keep your code versioned so every change can be rolled back."),
        ("A database and a password manager", "PostgreSQL 14 or newer (on your server or managed), and a password manager for your keys."),
        ("Somewhere to run it", "The bot runs around the clock. Replit or a small VPS both work; they have their own monthly costs."),
        ("Money you can afford to lose", "The bot trades with real funds on your exchange account. Nothing here protects you from a falling bitcoin price."),
    ],
    "nl": [
        ("Een AI-assistent", "Claude, ChatGPT of een vergelijkbare assistent die een lang document aankan. Reken op een avond of twaalf."),
        ("Een beursaccount met API-sleutels", "Sleutels die alleen mogen bekijken en handelen, nooit opnemen. Het plan is geschreven voor Bitvavo (BTC-EUR) en bevat een opdracht om over te stappen naar een andere beurs; die overstap test je zelf."),
        ("Telegram of Discord", "Voor meldingen: aankopen, verkopen, waarschuwingen, het dagoverzicht."),
        ("Een GitHub-account", "Een privé-repository, om je code met versiebeheer te bewaren zodat je elke wijziging kunt terugdraaien."),
        ("Een database en een wachtwoordmanager", "PostgreSQL 14 of nieuwer (op je eigen server of als dienst), en een wachtwoordmanager voor je sleutels."),
        ("Een plek om hem te draaien", "De bot draait dag en nacht. Replit of een kleine VPS werken allebei; die hebben hun eigen maandkosten."),
        ("Geld dat je kunt missen", "De bot handelt met echt geld op je beursaccount. Niets hier beschermt je tegen een dalende bitcoinkoers."),
    ],
}

AANPASSEN = {
    "en": ("Make it yours, before or after you build it. Every rule in the plan is a sentence your AI can change: "
           "tell it what you want different and it rewrites the code. A few examples:"),
    "nl": ("Maak er je eigen bot van, vóór of na het bouwen. Elke regel in het plan is een zin die je AI kan veranderen: "
           "zeg wat je anders wilt en hij herschrijft de code. Een paar voorbeelden:"),
}
VOORBEELDEN = {
    "en": ["“Use 15 rungs on the fine ladder instead of 20.”",
           "“Send my alerts to Discord instead of Telegram.”",
           "“Don't buy at all while the daily RSI is above 75.”",
           "“Add a stop-loss at −15%.” (This bot deliberately has none; see the design decisions.)"],
    "nl": ["“Gebruik 15 treden op de fijne ladder in plaats van 20.”",
           "“Stuur mijn meldingen naar Discord in plaats van Telegram.”",
           "“Koop helemaal niet zolang de dag-RSI boven 75 staat.”",
           "“Voeg een stop-loss toe bij −15%.” (Deze bot heeft er bewust geen; zie de ontwerpkeuzes.)"],
}

NIET = {
    "en": ["Not signals and not copy-trading: nothing here tells you when to buy or sell.",
           "Not managed money: you run your own bot, on your own account.",
           "Not a return promise: the logbook shows what this bot did, including the open positions that are down."],
    "nl": ["Geen signalen en geen copy-trading: niets hier vertelt je wanneer je moet kopen of verkopen.",
           "Geen vermogensbeheer: je draait je eigen bot, op je eigen account.",
           "Geen rendementsbelofte: het logboek laat zien wat deze bot deed, ook de open posities die in de min staan."],
}

# Ontwerpkeuzes door de tijd. 'wanneer' en de feiten: LEKKEN en het ontwerplogboek van de bot.
KEUZES = {
    "en": [
        dict(id="goal", wanneer="From the logbook", kop="A 0.5% weekly goal, not 2%",
             waarom="The name promised 2% a week. Measured honestly, week after week, 0.5% turned out to be the realistic goal. The chart on the logbook draws both lines.",
             ai="“Report every week against a goal of 0.3%.”"),
        dict(id="fees", wanneer="Measured 5 Aug 2026", kop="Book the real fee on every fill",
             waarom="Fees took roughly a fifth of gross profit between late April and early August. The bot now books the actual fee per fill, and since 10 Oct 2026 it also fills in fees the exchange settles later.",
             ai="“Use my own fee tier when you calculate sell targets.”"),
        dict(id="time-decay", wanneer="Measured 5 Aug 2026", kop="Switch off time-decay",
             waarom="A rule lowered the sell target as a position aged. In 78% of the 152 sales it touched, the original target was reached again within 24 hours (median: 3 hours later). It gave up about 0.33% per trade, so it was switched off.",
             ai="“Lower the sell target by 0.1% for each day a position stays open.”"),
        dict(id="rsi", wanneer="Aug 2026; off for the ladder since 2 Oct 2026", kop="An RSI brake: first a taper, then off",
             waarom="Blocking all buys above RSI 70 also froze the ladder, so a later shallow dip caught nothing. In August it became a taper: smaller orders between RSI 70 and 80, a hard block only above 80. On 2 Oct 2026 the brake was switched off for the ladder entirely; the separate RSI dip-buy strategy is unaffected. The dashboard shows the brake's state at snapshot time.",
             ai="“Pause the ladder completely whenever RSI is above 75.”"),
        dict(id="no-loss", wanneer="20 Aug 2026; stop-loss and timers removed 26–29 Sep 2026", kop="Never sell at a loss",
             waarom="A position is only sold above its buy price; stop-losses and position timers are gone. The price of that choice: losses don't disappear, they wait in open positions. In a deep drop the open number grows before anything shows up in the weekly figure.",
             ai="“Add a stop-loss at −15% for the fine ladder only.”"),
        dict(id="limit-orders", wanneer="2 Sep 2026", kop="Real limit orders on the exchange",
             waarom="Sell targets became real limit orders at the exchange instead of prices the bot watched. The buy ladder also places real limit orders: up to 20 fine and 10 coarse rungs below the price. A resting order is filled at its own price.",
             ai="“Use 10 fine rungs and keep them 0.2% apart.”"),
        dict(id="depth-budget", wanneer="2 Oct 2026", kop="A depth budget for buying",
             waarom="How much of the capital the bot may have in bitcoin depends on how deep the price is below the highest open purchase: 50% at that top, rising in a straight line to 100% at 25% below it. Capital is kept back for deeper dips.",
             ai="“Never put more than 60% of my capital in, at any price.”"),
        dict(id="simpler", wanneer="September 2026", kop="Fewer moving parts",
             waarom="Several layers were removed: a machine-learning predictor, an anomaly detector, a strategy tournament and more. Most of them turned out not to change the orders the bot placed. Simpler code is easier to check, for you and for your AI.",
             ai="“Explain every rule in the code to me in one sentence each.”"),
    ],
    "nl": [
        dict(id="doel", wanneer="Uit het logboek", kop="Een weekdoel van 0,5%, niet 2%",
             waarom="De naam beloofde 2% per week. Na weken eerlijk meten bleek 0,5% het realistische doel. De grafiek in het logboek tekent beide lijnen.",
             ai="“Rapporteer elke week tegen een doel van 0,3%.”"),
        dict(id="kosten", wanneer="Gemeten 5 aug 2026", kop="Boek de echte beurskosten per uitgevoerde order",
             waarom="Tussen eind april en begin augustus ging ongeveer een vijfde van de brutowinst op aan beurskosten. De bot boekt nu de werkelijke kosten per uitgevoerde order, en sinds 10 okt 2026 ook kosten die de beurs pas later verrekent.",
             ai="“Gebruik mijn eigen kostentarief bij het berekenen van verkoopdoelen.”"),
        dict(id="time-decay", wanneer="Gemeten 5 aug 2026", kop="Time-decay uit",
             waarom="Een regel verlaagde het verkoopdoel naarmate een positie ouder werd. Bij 78% van de 152 verkopen waar hij invloed op had, werd het oorspronkelijke doel binnen 24 uur alsnog gehaald (mediaan: 3 uur later). Hij kostte ongeveer 0,33% per trade, dus is hij uitgezet.",
             ai="“Verlaag het verkoopdoel met 0,1% voor elke dag dat een positie openstaat.”"),
        dict(id="rsi", wanneer="aug 2026; uit voor de ladder sinds 2 okt 2026", kop="Een RSI-rem: eerst geleidelijk, daarna uit",
             waarom="Alle aankopen blokkeren boven RSI 70 bevroor ook de ladder, waardoor een latere ondiepe dip niets opleverde. In augustus werd het een geleidelijke rem: kleinere orders tussen RSI 70 en 80, pas boven 80 een harde stop. Op 2 okt 2026 ging de rem voor de ladder helemaal uit; de aparte RSI-dipkoopstrategie blijft werken. Het dashboard laat zien hoe de rem stond op het moment van de momentopname.",
             ai="“Zet de ladder helemaal stil zolang de RSI boven 75 staat.”"),
        dict(id="geen-verlies", wanneer="20 aug 2026; stop-loss en timers weg 26–29 sep 2026", kop="Nooit met verlies verkopen",
             waarom="Een positie wordt alleen boven de aankoopprijs verkocht; stop-losses en positietimers zijn weg. De prijs van die keuze: verliezen verdwijnen niet, ze wachten in open posities. Bij een diepe daling groeit het open verlies voordat er iets in het weekcijfer verschijnt.",
             ai="“Voeg alleen voor de fijne ladder een stop-loss toe op −15%.”"),
        dict(id="limietorders", wanneer="2 sep 2026", kop="Echte limietorders op de beurs",
             waarom="Verkoopdoelen werden echte limietorders op de beurs in plaats van koersen die de bot in de gaten hield. Ook de koopladder zet echte limietorders: tot 20 fijne en 10 grove treden onder de koers. Een order die in het orderboek staat, wordt uitgevoerd tegen zijn eigen limietprijs.",
             ai="“Gebruik 10 fijne treden en houd ze 0,2% uit elkaar.”"),
        dict(id="dieptebudget", wanneer="2 okt 2026", kop="Een dieptebudget voor aankopen",
             waarom="Hoeveel van het kapitaal de bot in bitcoin mag hebben, hangt af van hoe diep de koers onder de hoogste open aankoop staat: 50% op die top, in een rechte lijn oplopend naar 100% op 25% eronder. Zo blijft er kapitaal over voor diepere dips.",
             ai="“Zet nooit meer dan 60% van mijn kapitaal in, bij geen enkele koers.”"),
        dict(id="eenvoudiger", wanneer="September 2026", kop="Minder bewegende delen",
             waarom="Er zijn meerdere lagen geschrapt: een machine-learning-voorspeller, een anomaliedetector, een strategietoernooi en meer. De meeste bleken de orders van de bot niet te veranderen. Eenvoudiger code is makkelijker te controleren, voor jou en voor je AI.",
             ai="“Leg elke regel in de code in één zin aan me uit.”"),
    ],
}

FAQ = {
    "en": [
        ("Do I need to be able to code?",
         "No. Your AI writes the code and walks you through the steps. You do need to be comfortable creating API keys, reading what the AI tells you, and checking the bot before it trades real money."),
        ("Does it only work on Bitvavo?",
         "The plan is written for Bitvavo's BTC-EUR market. It includes a prompt to port the exchange code to another exchange (for example Kraken or Coinbase), with the tests to re-run; checking that port is up to you."),
        ("Will it make money?",
         "Nobody can promise that, and this site doesn't. The logbook shows what this bot did each week, and the open positions next to it. Past weeks say nothing about future weeks; you can lose your entire stake."),
        ("How much money do I need to start?",
         "The plan doesn't prescribe an amount, and this site never publishes account sizes. The exchange has minimum order sizes. Only use money you can afford to lose entirely."),
        ("What do the updates contain?",
         "When the bot or the plan changes, subscribers get the new version by email with a changelog that says what to hand back to their AI. The subscription renews yearly; you can cancel at any time."),
        ("Can I get a refund?",
         "It is a digital download. At checkout you agree to immediate delivery and acknowledge that you lose the 14-day right of withdrawal once delivery has started, as EU rules for digital content allow."),
        ("Is this financial advice or a signal service?",
         "No. It is engineering documentation for building and running your own software. Nothing here tells you when to buy or sell."),
    ],
    "nl": [
        ("Moet ik kunnen programmeren?",
         "Nee. Je AI schrijft de code en leidt je door de stappen. Reken op een avond of twaalf. Je moet wel API-sleutels kunnen aanmaken, kunnen lezen wat de AI je vertelt en de bot controleren voordat hij met echt geld handelt."),
        ("Werkt het alleen op Bitvavo?",
         "Het plan is geschreven voor de BTC-EUR-markt van Bitvavo. Er staat een opdracht in om de beurskoppeling om te zetten naar een andere beurs (bijvoorbeeld Kraken of Coinbase), met de tests die je daarna opnieuw draait; die overstap controleer je zelf."),
        ("Verdien ik er geld mee?",
         "Dat kan niemand beloven, en deze site doet dat ook niet. Het logboek laat zien wat deze bot elke week deed, met de open posities ernaast. Afgelopen weken zeggen niets over komende weken; je kunt je hele inleg verliezen."),
        ("Met hoeveel geld moet ik beginnen?",
         "Het plan schrijft geen bedrag voor, en deze site publiceert nooit rekeninggroottes. De beurs heeft minimale ordergroottes. Gebruik alleen geld dat je helemaal kunt missen."),
        ("Wat zit er in de updates?",
         "Als de bot of het plan verandert, krijgen abonnees de nieuwe versie per mail, met een lijst van wijzigingen en wat je daarvan aan je AI teruggeeft. Het abonnement wordt elk jaar verlengd; je kunt altijd opzeggen."),
        ("Kan ik mijn geld terugkrijgen?",
         "Het is een digitale download. Bij het afrekenen ga je akkoord met directe levering en erken je dat je herroepingsrecht van 14 dagen vervalt zodra de levering begint, zoals de EU-regels voor digitale inhoud toestaan."),
        ("Is dit financieel advies of een signaaldienst?",
         "Nee. Het is technische documentatie om je eigen software te bouwen en te draaien. Niets hier vertelt je wanneer je moet kopen of verkopen."),
    ],
}

# De lekken uit build_logboek.LEKKEN, in het Nederlands (zelfde feiten, zelfde data).
LEKKEN_NL = [
    dict(kop="Beurskosten slokten ongeveer een vijfde van de brutowinst op",
         uitleg="Tussen eind april en begin augustus ging ongeveer 20% van de bruto handelswinst naar beurskosten. De "
                "bot boekt nu de werkelijke kosten per uitgevoerde order. De beurs rekent bij het volume van de bot 0,18% per "
                "taker-order en 0,09% per maker-order.",
         datum="gemeten 5 aug 2026; tarieven gelezen 8 sep 2026", iso="2026-08-05",
         cijfer="~20%", cijfer_uitleg="van de brutowinst ging naar kosten", nu="Echte kosten nu per uitgevoerde order geboekt"),
    dict(kop="Het winstdoel na verloop van tijd verlagen kostte geld",
         uitleg="Een 'time-decay'-regel verlaagde het verkoopdoel naarmate een positie ouder werd. Van de 152 "
                "verkopen die hij in 55 dagen raakte, haalde 78% het oorspronkelijke doel alsnog (mediaan: 3 uur "
                "later). De regel gaf ongeveer 0,33% per trade weg, dus ging hij uit.",
         datum="gemeten 5 aug 2026", iso="2026-08-05",
         cijfer="0,33%", cijfer_uitleg="weggegeven per trade", nu="Regel uitgezet"),
    dict(kop="Een veiligheidsfilter bevroor de koopladder",
         uitleg="Een harde koopstop bij een RSI boven 70 verhinderde ook dat de ladder de koers volgde, zodat een "
                "latere ondiepe dip niets opleverde. Het werd een geleidelijke rem: kleinere orders tussen RSI 70 en "
                "80, pas boven 80 een harde stop. Sinds 2 okt 2026 staat de rem voor de ladder helemaal uit.",
         datum="aangepast 9 aug 2026", iso="2026-08-09",
         cijfer="RSI 70", cijfer_uitleg="harde stop die de ladder bevroor", nu="Eerst geleidelijk; sinds 2 okt uit voor de ladder"),
    dict(kop="Eén weekrapport miste ongeveer de helft van de winst",
         uitleg="In één wekelijks Telegram-rapport van de bot ontbrak ongeveer de helft van de "
                "gerealiseerde winst. Het rapport keek naar het moment waarop een positie begon in plaats van waarop "
                "hij verkocht werd, waardoor posities die over een weekgrens liepen wegvielen. Opgelost en nagerekend met de "
                "handelsgegevens.",
         datum="opgelost 9 aug 2026", iso="2026-08-09",
         cijfer="~½", cijfer_uitleg="van de winst van één week ontbrak in het rapport",
         nu="Opgelost en nagerekend met de handelsgegevens"),
]
