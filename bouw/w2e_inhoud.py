"""Teksten voor het bouwpakket en 'hoe het werkt', Engels en Nederlands (Daan, 27 okt 2026).

Geen vertaling van elkaar: elke taal is apart geschreven, met dezelfde feiten. Elke datum en elk percentage hier komt
uit LEKKEN in build_logboek.py of uit het ontwerplogboek van de bot (CLAUDE.md / replit.md in de private bot-repo,
gelezen 27 okt 2026); wat de pagina uit de data haalt (volatiliteit, RSI-rem aan/uit) staat níet hier.
Regels: geen advies, geen signalen, geen rendementsbelofte; de bot kan verliezen.
"""

STAPPEN = {
    "en": [
        ("Download the plan", "One document that describes this bot step by step, written to be carried out by an AI assistant."),
        ("Hand it to your AI", "Upload it into Claude, ChatGPT or a similar assistant and let it walk you through every step: code, database, alerts, deployment."),
        ("Open an exchange account", "Create an account at a crypto exchange and an API key for the bot. The plan is written for Bitvavo's BTC-EUR market."),
        ("Have fun", "Run it, watch it, change it. Start small: it trades with real money, and you can lose it."),
    ],
    "nl": [
        ("Download het plan", "Eén document dat deze bot stap voor stap beschrijft, geschreven om door een AI-assistent uitgevoerd te worden."),
        ("Geef het aan je AI", "Upload het in Claude, ChatGPT of een vergelijkbare assistent en laat die je door elke stap leiden: code, database, meldingen, livegang."),
        ("Open een account bij een beurs", "Maak een account aan bij een cryptobeurs en een API-sleutel voor de bot. Het plan is geschreven voor de BTC-EUR-markt van Bitvavo."),
        ("Veel plezier", "Laat hem draaien, kijk mee, pas hem aan. Begin klein: hij handelt met echt geld, en dat kun je kwijtraken."),
    ],
}

KRIJG = {
    "en": [
        ("The build plan", "One document covering the whole bot: the buy ladder, the sell logic, the safety checks, the database, Telegram alerts, the dashboard and how to keep it running 24/7. Written as instructions an AI can execute, step by step."),
        ("Delivered by email", "Right after payment you get a download link (valid for 72 hours, up to 5 downloads)."),
        ("Updates, if you want them", "With the update subscription, every time the bot changes in a way the plan should reflect, you get the new version by email with a short changelog. It renews yearly; cancel any time."),
    ],
    "nl": [
        ("Het bouwplan", "Eén document over de hele bot: de koopladder, de verkooplogica, de veiligheidscontroles, de database, Telegram-meldingen, het dashboard en hoe je hem dag en nacht laat draaien. Geschreven als instructies die een AI stap voor stap kan uitvoeren."),
        ("Per e-mail", "Direct na betaling krijg je een downloadlink (72 uur geldig, maximaal 5 downloads)."),
        ("Updates, als je wilt", "Met het update-abonnement krijg je bij elke wijziging aan de bot die in het plan hoort, de nieuwe versie per mail met een korte lijst van wat er veranderde. Het verlengt jaarlijks; opzeggen kan altijd."),
    ],
}

NODIG = {
    "en": [
        ("An AI assistant", "Claude, ChatGPT or similar, one that can read a long document."),
        ("An exchange account with API keys", "The plan is written for Bitvavo (BTC-EUR). Another exchange means asking your AI to adapt the exchange calls: your own engineering."),
        ("Telegram or Discord", "For alerts: fills, sales, warnings, the daily summary."),
        ("A GitHub account", "To keep your code versioned, so every change can be rolled back."),
        ("Somewhere to run it", "The bot runs around the clock. Replit or a small VPS both work; they have their own monthly costs."),
        ("Money you can afford to lose", "The bot trades with real funds on your exchange account. Nothing here protects you from a falling bitcoin price."),
    ],
    "nl": [
        ("Een AI-assistent", "Claude, ChatGPT of vergelijkbaar, een die een lang document kan lezen."),
        ("Een beursaccount met API-sleutels", "Het plan is geschreven voor Bitvavo (BTC-EUR). Een andere beurs betekent je AI de beurskoppeling laten aanpassen: dat is je eigen bouwwerk."),
        ("Telegram of Discord", "Voor meldingen: aankopen, verkopen, waarschuwingen, het dagoverzicht."),
        ("Een GitHub-account", "Om je code te bewaren met versies, zodat je elke wijziging kunt terugdraaien."),
        ("Een plek om hem te draaien", "De bot draait dag en nacht. Replit of een kleine VPS werken allebei; die hebben hun eigen maandkosten."),
        ("Geld dat je kunt missen", "De bot handelt met echt geld op je beursaccount. Niets hier beschermt je tegen een dalende bitcoinkoers."),
    ],
}

AANPASSEN = {
    "en": ("Make it yours, before or after you build it. Every rule in the plan is a sentence your AI can change: "
           "tell it what you want different and it rewrites the code. A few examples:"),
    "nl": ("Maak hem van jezelf, vóór of na het bouwen. Elke regel in het plan is een zin die je AI kan veranderen: "
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
           "“Voeg een stop-loss toe op −15%.” (Deze bot heeft er bewust geen; zie de ontwerpkeuzes.)"],
}

NIET = {
    "en": ["Not signals and not copy-trading: nothing here tells you when to buy or sell.",
           "Not managed money: you run your own bot, on your own account.",
           "Not a return promise: the logbook shows what this bot did, including the open positions that are down."],
    "nl": ["Geen signalen en geen copy-trading: niets hier zegt je wanneer je moet kopen of verkopen.",
           "Geen vermogensbeheer: je draait je eigen bot, op je eigen account.",
           "Geen rendementsbelofte: het logboek laat zien wat deze bot deed, ook de open posities die in de min staan."],
}

# Ontwerpkeuzes door de tijd. 'wanneer' en de feiten: LEKKEN en het ontwerplogboek van de bot.
KEUZES = {
    "en": [
        dict(id="goal", wanneer="From the logbook", kop="A 0.5% weekly goal, not 2%",
             waarom="The name promised 2% a week. Measured honestly, week after week, 0.5% turned out to be the realistic goal. The chart on the logbook draws both lines.",
             ai="“Report every week against a goal of 0.3%.”"),
        dict(id="fees", wanneer="5 Aug 2026", kop="Book the real fee on every fill",
             waarom="Fees took roughly a fifth of gross profit between late April and early August. The bot now books the actual fee per fill, and since 10 Oct 2026 it also fills in fees the exchange settles later.",
             ai="“Use my own fee tier when you calculate sell targets.”"),
        dict(id="time-decay", wanneer="Measured 5 Aug 2026", kop="Switch off time-decay",
             waarom="A rule lowered the sell target as a position aged. In 78% of the 152 sales it touched, the original target was still reached (median: 3 hours later). It gave up about 0.33% per trade, so it was switched off.",
             ai="“Lower the sell target by 0.1% for each day a position stays open.”"),
        dict(id="rsi", wanneer="9 Aug 2026", kop="An RSI taper instead of a hard block",
             waarom="Blocking all buys above RSI 70 also froze the ladder, so a later shallow dip caught nothing. It became a taper: smaller orders between RSI 70 and 80, a hard block only above 80. The dashboard shows whether the brake is on right now.",
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
             waarom="De naam beloofde 2% per week. Eerlijk gemeten, week na week, bleek 0,5% het realistische doel. De grafiek in het logboek tekent beide lijnen.",
             ai="“Rapporteer elke week tegen een doel van 0,3%.”"),
        dict(id="kosten", wanneer="5 aug 2026", kop="Boek de echte beurskosten per vulling",
             waarom="Tussen eind april en begin augustus ging ongeveer een vijfde van de brutowinst op aan beurskosten. De bot boekt nu de werkelijke kosten per vulling, en sinds 10 okt 2026 ook kosten die de beurs pas later verrekent.",
             ai="“Gebruik mijn eigen kostentarief bij het berekenen van verkoopdoelen.”"),
        dict(id="time-decay", wanneer="Gemeten 5 aug 2026", kop="Time-decay uit",
             waarom="Een regel verlaagde het verkoopdoel naarmate een positie ouder werd. Bij 78% van de 152 verkopen die hij raakte, werd het oorspronkelijke doel alsnog gehaald (mediaan: 3 uur later). Hij kostte ongeveer 0,33% per trade, dus ging hij uit.",
             ai="“Verlaag het verkoopdoel met 0,1% voor elke dag dat een positie openstaat.”"),
        dict(id="rsi", wanneer="9 aug 2026", kop="Een RSI-rem die afbouwt in plaats van blokkeert",
             waarom="Alle aankopen blokkeren boven RSI 70 bevroor ook de ladder, waardoor een latere ondiepe dip niets opleverde. Het werd een afbouw: kleinere orders tussen RSI 70 en 80, pas boven 80 een harde stop. Het dashboard laat zien of de rem nu aan staat.",
             ai="“Zet de ladder helemaal stil zolang de RSI boven 75 staat.”"),
        dict(id="geen-verlies", wanneer="20 aug 2026; stop-loss en timers weg 26–29 sep 2026", kop="Nooit met verlies verkopen",
             waarom="Een positie wordt alleen boven de aankoopprijs verkocht; stop-losses en positietimers zijn weg. De prijs van die keuze: verliezen verdwijnen niet, ze wachten in open posities. Bij een diepe daling groeit het open getal voordat er iets in het weekcijfer verschijnt.",
             ai="“Voeg alleen voor de fijne ladder een stop-loss toe op −15%.”"),
        dict(id="limietorders", wanneer="2 sep 2026", kop="Echte limietorders op de beurs",
             waarom="Verkoopdoelen werden echte limietorders op de beurs in plaats van koersen die de bot in de gaten hield. Ook de koopladder zet echte limietorders: tot 20 fijne en 10 grove treden onder de koers. Een order die klaarstaat, wordt gevuld tegen zijn eigen prijs.",
             ai="“Gebruik 10 fijne treden en houd ze 0,2% uit elkaar.”"),
        dict(id="dieptebudget", wanneer="2 okt 2026", kop="Een dieptebudget voor aankopen",
             waarom="Hoeveel van het kapitaal de bot in bitcoin mag hebben, hangt af van hoe diep de koers onder de hoogste open aankoop staat: 50% op die top, in een rechte lijn oplopend naar 100% op 25% eronder. Zo blijft er kapitaal over voor diepere dips.",
             ai="“Zet nooit meer dan 60% van mijn kapitaal in, bij geen enkele koers.”"),
        dict(id="eenvoudiger", wanneer="September 2026", kop="Minder bewegende delen",
             waarom="Er gingen meerdere lagen uit: een machine-learning-voorspeller, een anomaliedetector, een strategietoernooi en meer. De meeste bleken de orders van de bot niet te veranderen. Eenvoudiger code is makkelijker te controleren, voor jou en voor je AI.",
             ai="“Leg elke regel in de code in één zin aan me uit.”"),
    ],
}

FAQ = {
    "en": [
        ("Do I need to be able to code?",
         "No. Your AI writes the code and walks you through the steps. You do need to be comfortable creating API keys, reading what the AI tells you, and checking the bot before it trades real money."),
        ("Does it only work on Bitvavo?",
         "The plan is written for Bitvavo's BTC-EUR market. You can ask your AI to adapt it to another exchange's API, but that is your own engineering and not something the plan covers."),
        ("Will it make money?",
         "Nobody can promise that, and this site doesn't. The logbook shows what this bot did each week, and the open positions next to it. Past weeks say nothing about future weeks; you can lose your entire stake."),
        ("How much money do I need to start?",
         "The plan doesn't prescribe an amount, and this site never publishes account sizes. The exchange has minimum order sizes. Only use money you can afford to lose entirely."),
        ("What do the updates contain?",
         "When the bot changes in a way the plan should reflect, subscribers get the new version by email with a short changelog. The subscription renews yearly; you can cancel at any time."),
        ("Can I get a refund?",
         "It is a digital download. At checkout you agree to immediate delivery and acknowledge that you lose the 14-day right of withdrawal once delivery has started, as EU rules for digital content allow."),
        ("Is this financial advice or a signal service?",
         "No. It is engineering documentation for building and running your own software. Nothing here tells you when to buy or sell."),
    ],
    "nl": [
        ("Moet ik kunnen programmeren?",
         "Nee. Je AI schrijft de code en leidt je door de stappen. Je moet wel API-sleutels kunnen aanmaken, kunnen lezen wat de AI je vertelt en de bot controleren voordat hij met echt geld handelt."),
        ("Werkt het alleen op Bitvavo?",
         "Het plan is geschreven voor de BTC-EUR-markt van Bitvavo. Je kunt je AI vragen het aan te passen aan de API van een andere beurs, maar dat is je eigen bouwwerk en valt buiten het plan."),
        ("Verdien ik er geld mee?",
         "Dat kan niemand beloven, en deze site doet dat ook niet. Het logboek laat zien wat deze bot elke week deed, met de open posities ernaast. Afgelopen weken zeggen niets over komende weken; je kunt je hele inleg verliezen."),
        ("Met hoeveel geld moet ik beginnen?",
         "Het plan schrijft geen bedrag voor, en deze site publiceert nooit rekeninggroottes. De beurs heeft minimale ordergroottes. Gebruik alleen geld dat je helemaal kunt missen."),
        ("Wat zit er in de updates?",
         "Als de bot verandert op een manier die in het plan hoort, krijgen abonnees de nieuwe versie per mail met een korte lijst van wijzigingen. Het abonnement verlengt jaarlijks; opzeggen kan altijd."),
        ("Kan ik mijn geld terugkrijgen?",
         "Het is een digitale download. Bij het afrekenen ga je akkoord met directe levering en erken je dat je herroepingsrecht van 14 dagen vervalt zodra de levering begint, zoals de EU-regels voor digitale inhoud toestaan."),
        ("Is dit financieel advies of een signaaldienst?",
         "Nee. Het is technische documentatie om je eigen software te bouwen en te draaien. Niets hier zegt je wanneer je moet kopen of verkopen."),
    ],
}

# De lekken uit build_logboek.LEKKEN, in het Nederlands (zelfde feiten, zelfde data).
LEKKEN_NL = [
    dict(kop="Beurskosten slokten ongeveer een vijfde van de brutowinst op",
         uitleg="Tussen eind april en begin augustus ging ongeveer 20% van de bruto handelswinst naar beurskosten. De "
                "bot boekt nu de werkelijke kosten per vulling. De beurs rekent bij het volume van de bot 0,18% per "
                "taker-order en 0,09% per maker-order.",
         datum="gemeten 5 aug 2026; tarieven gelezen 8 sep 2026", iso="2026-08-05",
         cijfer="~20%", cijfer_uitleg="van de brutowinst ging naar kosten", nu="Echte kosten nu per vulling geboekt"),
    dict(kop="Het winstdoel laten zakken met de tijd kostte geld",
         uitleg="Een 'time-decay'-regel verlaagde het verkoopdoel naarmate een positie ouder werd. Van de 152 "
                "verkopen die hij in 55 dagen raakte, haalde 78% het oorspronkelijke doel alsnog (mediaan: 3 uur "
                "later). De regel gaf ongeveer 0,33% per trade weg, dus ging hij uit.",
         datum="gemeten 5 aug 2026", iso="2026-08-05",
         cijfer="0,33%", cijfer_uitleg="weggegeven per trade", nu="Regel uitgezet"),
    dict(kop="Een veiligheidsfilter bevroor de koopladder",
         uitleg="Een harde koopstop bij een RSI boven 70 hield de ladder ook tegen om de koers te volgen, zodat een "
                "latere ondiepe dip niets opleverde. Het werd een afbouw: kleinere orders tussen RSI 70 en 80, pas "
                "boven 80 een harde stop.",
         datum="aangepast 9 aug 2026", iso="2026-08-09",
         cijfer="RSI 70", cijfer_uitleg="harde stop die de ladder bevroor", nu="Nu een afbouw; harde stop pas boven 80"),
    dict(kop="Eén weekrapport miste ongeveer de helft van de winst",
         uitleg="In één week van het wekelijkse Telegram-rapport van de bot ontbrak ongeveer de helft van de "
                "gerealiseerde winst. Het rapport keek naar het moment waarop een positie begon in plaats van waarop "
                "hij verkocht werd, waardoor posities over twee weken verdwenen. Opgelost en nagerekend met de "
                "handelsgegevens.",
         datum="opgelost 9 aug 2026", iso="2026-08-09",
         cijfer="~½", cijfer_uitleg="van de winst van één week ontbrak in het rapport",
         nu="Opgelost en nagerekend met de handelsgegevens"),
]
