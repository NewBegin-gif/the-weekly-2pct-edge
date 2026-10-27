"""Publiceert sites/mijnbitcoinstrategie.nl/ naar zijn eigen webroot met rsync. Alleen stdlib.

    python3 deploy/publiceer_nl.py --dry-run          # laat zien wat er zou veranderen, verandert niets
    python3 deploy/publiceer_nl.py                    # publiceert naar /var/www/mijnbitcoinstrategie.nl
    python3 deploy/publiceer_nl.py --doel /tmp/nl     # ergens anders (bv. voor deploy/rooktest.py lokaal)
    python3 deploy/publiceer_nl.py --doel root@187.124.167.150:/var/www/mijnbitcoinstrategie.nl   # vanaf de Mac
    python3 deploy/publiceer_nl.py --en-exclude       # print alleen de excludes die de EN-rsync erbij moet krijgen

Zelfde excludes als de EN-site (.git, *.bak*, *.tmp-*, *.orig, *.py), plus --delete zodat een weggehaalde pagina ook
van de server verdwijnt. Vóór het kopiëren controleert het script de bron: geen .md, database, .env, .py(c),
.pr-screenshots of document (pdf/docx/epub) mag erin staan, en de vaste bestanden (index, 404, robots, sitemap,
llms.txt, og-image) moeten er zijn. Anders stopt het zonder iets te kopiëren.

De EN-rsync (die de repo-root publiceert) moet sites/, levering/, deploy/ en bouw/ uitsluiten, anders staan de
Nederlandse site en lege mappen van de dienst ook onder theweekly2pctedge.com. Die regel print dit script.
"""
import argparse
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True

REPO = pathlib.Path(__file__).resolve().parent.parent
BRON = REPO / "sites" / "mijnbitcoinstrategie.nl"
DOEL = "/var/www/mijnbitcoinstrategie.nl"
EXCLUDES = [".git", "*.bak*", "*.tmp-*", "*.orig", "*.py"]
EN_EXTRA = ["sites/", "levering/", "deploy/", "bouw/", "__pycache__/", ".pr-screenshots/"]
VERBODEN = (".md", ".db", ".sqlite", ".sqlite3", ".env", ".py", ".pyc", ".pdf", ".docx", ".epub", ".csv", ".log", ".key", ".pem")
VERPLICHT = ["index.html", "404.html", "robots.txt", "sitemap.xml", "llms.txt", "og-image.png", "bouwpakket/index.html",
             "zo-werkt-het/index.html"]


def en_exclude_regel():
    return " ".join(f"--exclude '{x}'" for x in EN_EXTRA)


def controleer_bron(bron):
    fouten = [f"ontbreekt: {v}" for v in VERPLICHT if not (bron / v).is_file()]
    for f in bron.rglob("*"):
        rel = f.relative_to(bron).as_posix()
        if f.is_file() and (f.suffix.lower() in VERBODEN or f.name.startswith(".env") or ".pr-screenshots" in rel
                            or "__pycache__" in rel):
            fouten.append(f"mag niet gepubliceerd worden: {rel}")
    return fouten


def rsync_opdracht(bron, doel, dry_run):
    cmd = ["rsync", "-a", "--delete", "--itemize-changes"]
    if dry_run:
        cmd.append("--dry-run")
    for x in EXCLUDES:
        cmd += ["--exclude", x]
    return cmd + [f"{str(bron).rstrip('/')}/", f"{str(doel).rstrip('/')}/"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--doel", default=DOEL)
    p.add_argument("--bron", default=str(BRON))
    p.add_argument("--en-exclude", action="store_true", help="print alleen de extra excludes voor de EN-rsync")
    a = p.parse_args(argv)
    if a.en_exclude:
        print(en_exclude_regel())
        return 0
    bron = pathlib.Path(a.bron)
    fouten = controleer_bron(bron)
    if fouten:
        print("NIET gepubliceerd:\n  " + "\n  ".join(fouten), file=sys.stderr)
        return 1
    if not a.dry_run and ":" not in a.doel:  # op afstand (root@host:/pad) maakt rsync zelf de map
        pathlib.Path(a.doel).mkdir(parents=True, exist_ok=True)
    cmd = rsync_opdracht(bron, a.doel, a.dry_run)
    print("$ " + " ".join(cmd))
    uit = subprocess.run(cmd)
    if uit.returncode:
        return uit.returncode
    print(f"\n{'(dry-run) ' if a.dry_run else ''}klaar: {bron} -> {a.doel}")
    print(f"De EN-rsync van de repo-root moet hier bovenop uitsluiten:\n  {en_exclude_regel()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
