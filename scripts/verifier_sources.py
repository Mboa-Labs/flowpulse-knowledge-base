"""Vérifie la cohérence entre sources.csv et les fichiers présents dans InputDocs/.

Signale :
- les lignes de sources.csv sans fichier (ou dont le fichier est introuvable) ;
- les fichiers d'InputDocs/ qui ne sont déclarés dans aucune ligne ;
- les champs obligatoires vides pour les documents marqués « verifie » ou « indexe ».

Usage : python scripts/verifier_sources.py
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = KB_DIR / "InputDocs"
MANIFEST = KB_DIR / "sources.csv"

SUPPORTED = {".pdf", ".txt", ".md", ".html"}
REQUIRED_WHEN_VERIFIED = ["fichier", "titre", "reference", "type", "autorite", "date_adoption", "url_source"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    problems = 0
    declared: set[Path] = set()

    for row in rows:
        if not row["fichier"]:
            continue
        path = INPUT_DIR / row["dossier"] / row["fichier"]
        declared.add(path.resolve())
        if not path.exists():
            print(f"[MANQUANT] {row['id']} : {path.relative_to(KB_DIR)} introuvable")
            problems += 1

    for row in rows:
        if row["statut"] in ("verifie", "indexe"):
            empty = [c for c in REQUIRED_WHEN_VERIFIED if not row[c] or "vérifier" in row[c] or "identifier" in row[c]]
            if empty:
                print(f"[INCOMPLET] {row['id']} est « {row['statut']} » mais ces champs restent à remplir : {', '.join(empty)}")
                problems += 1

    for path in sorted(INPUT_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED and path.resolve() not in declared:
            print(f"[NON DÉCLARÉ] {path.relative_to(KB_DIR)} n'a pas de ligne dans sources.csv")
            problems += 1

    counts = Counter(row["statut"] for row in rows)
    print(f"\n{len(rows)} documents déclarés : " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    print("Aucun problème." if problems == 0 else f"{problems} problème(s) à corriger.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
