"""Ingestion de la base de connaissances FlowPulse dans ChromaDB.

Reprend le pipeline du dépôt ITUAIReadiness (simulation/server/knowledge/ingest.py) :
extraction PDF avec PyMuPDF, découpage en passages de 256 mots avec 30 mots de
recouvrement, vecteurs nomic-embed-text via Ollama, stockage ChromaDB.

Ajouts FlowPulse :
- les métadonnées viennent de sources.csv (référence, autorité, date, domaine…) ;
- les textes juridiques sont d'abord découpés par article, pour que l'agent
  Politique puisse citer « Article 12 » plutôt qu'un morceau anonyme ;
- seuls les documents au statut « verifie » ou « indexe » sont ingérés.

Usage :
    python scripts/ingest.py --dry-run        # affiche le découpage, sans Ollama ni ChromaDB
    python scripts/ingest.py                  # ingère dans chroma/
    python scripts/ingest.py --reset          # vide les collections avant

Dépendances (hors --dry-run) : pip install chromadb ollama pymupdf
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KB_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = KB_DIR / "InputDocs"
MANIFEST = KB_DIR / "sources.csv"
GAPS = KB_DIR / "registres" / "manques_reglementaires.csv"
CHROMA_DIR = Path(os.environ.get("FLOWPULSE_CHROMA_DIR", KB_DIR / "chroma"))

CHUNK_SIZE = 256      # mots, comme le dépôt ITU
CHUNK_OVERLAP = 30    # mots, comme le dépôt ITU
MAX_CHARS = 2000      # limite de sûreté pour nomic-embed-text, comme le dépôt ITU
EMBED_MODEL = os.environ.get("FLOWPULSE_EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL = os.environ.get("FLOWPULSE_OLLAMA_URL", "http://localhost:11434")

INGESTABLE = {"verifie", "indexe"}

SOURCE_TYPE = {
    "LOI": "law", "DECRET": "law", "ARRETE": "law", "DECISION": "policy_document",
    "PLAN": "policy_document", "CONTRAT": "contract", "STRATEGIE": "national_strategy",
    "NORME_ITU": "standards_document", "CONVENTION": "policy_document", "REGLEMENT": "law",
}

# « Article 12 », « Art. 12 », « ARTICLE 1er », « Article premier »
ARTICLE_RE = re.compile(r"(?im)^\s*(?:article|art\.)\s+(\d+(?:\s*(?:er|bis|ter))?|premier)\b")


def collection_for(dossier: str) -> str:
    return "kb_framework" if dossier.startswith("ITU") else "kb_reglementaire"


# ------------------------------------------------------------------
# Extraction
# ------------------------------------------------------------------

def parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(str(path)) as doc:
            return "\n\n".join(page.get_text() for page in doc)
    if suffix == ".html":
        text = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="replace"))
        return re.sub(r"[ \t]+", " ", text)
    return path.read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------
# Découpage
# ------------------------------------------------------------------

def split_articles(text: str) -> list[tuple[str, str]]:
    """Découpe un texte juridique en (article, contenu). Renvoie [("", texte)] si aucun article."""
    matches = list(ARTICLE_RE.finditer(text))
    if len(matches) < 2:
        return [("", text)]
    parts = []
    preamble = text[: matches[0].start()].strip()
    if len(preamble.split()) > 20:
        parts.append(("Préambule", preamble))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = "Article " + re.sub(r"\s+", " ", m.group(1)).strip()
        parts.append((label, text[m.start():end].strip()))
    return parts


def chunk_words(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Passages de *size* mots avec *overlap* mots de recouvrement, plafonnés à MAX_CHARS."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    # Un dernier passage trop court est rattaché au précédent, comme dans le dépôt ITU
    if len(chunks) > 1 and len(chunks[-1].split()) <= 20:
        chunks[-2] += " " + chunks.pop()
    safe = []
    for c in chunks:
        safe.extend(c[i:i + MAX_CHARS] for i in range(0, len(c), MAX_CHARS))
    return [c.strip() for c in safe if c.strip()]


def chunk_document(text: str) -> list[tuple[str, str]]:
    """(article, passage) pour tout le document."""
    out = []
    for article, body in split_articles(text):
        out.extend((article, chunk) for chunk in chunk_words(body))
    return out


# ------------------------------------------------------------------
# Métadonnées
# ------------------------------------------------------------------

def build_metadata(row: dict[str, str], article: str, index: int, total: int) -> dict[str, Any]:
    return {
        "source_file": row["fichier"],
        "source_type": SOURCE_TYPE.get(row["type"], "policy_document"),
        "country": row["pays"],
        "document_category": row["dossier"],
        "doc_id": row["id"],
        "titre": row["titre"],
        "reference": row["reference"],
        "type_texte": row["type"],
        "autorite": row["autorite"],
        "date_adoption": row["date_adoption"],
        "domaine": row["domaine"],
        "article": article,
        "chunk_index": str(index),
        "total_chunks": str(total),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


# ------------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------------

def embed(texts: list[str]) -> list[list[float]]:
    import ollama
    client = ollama.Client(host=OLLAMA_URL)
    vectors = []
    for i in range(0, len(texts), 32):
        vectors.extend(client.embed(model=EMBED_MODEL, input=texts[i:i + 32])["embeddings"])
    return vectors


def load_rows() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="affiche le découpage sans rien écrire")
    parser.add_argument("--reset", action="store_true", help="vide les collections avant ingestion")
    parser.add_argument("--all", action="store_true", help="ingère aussi les documents non vérifiés (tests uniquement)")
    args = parser.parse_args()

    rows = [r for r in load_rows() if r["fichier"] and (args.all or r["statut"] in INGESTABLE)]
    if not rows:
        print("Aucun document à ingérer : renseignez « fichier » et passez le statut à « verifie » dans sources.csv.")
        return

    client = None
    if not args.dry_run:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        if args.reset:
            for name in ("kb_reglementaire", "kb_framework", "kb_manques"):
                try:
                    client.delete_collection(name)
                except Exception:
                    pass

    total = 0
    for row in rows:
        path = INPUT_DIR / row["dossier"] / row["fichier"]
        if not path.exists():
            print(f"[MANQUANT] {row['id']} : {path}")
            continue
        chunks = chunk_document(parse_file(path))
        articles = sorted({a for a, _ in chunks if a}, key=lambda a: (len(a), a))
        print(f"{row['id']} : {len(chunks)} passages, {len(articles)} articles détectés ({path.name})")
        if args.dry_run:
            for article, chunk in chunks[:3]:
                print(f"   [{article or '—'}] {chunk[:120]}…")
            continue
        texts = [c for _, c in chunks]
        col = client.get_or_create_collection(collection_for(row["dossier"]), metadata={"hnsw:space": "cosine"})
        col.upsert(
            ids=[f"{row['id']}-{i}" for i in range(len(chunks))],
            documents=texts,
            embeddings=embed(texts),
            metadatas=[build_metadata(row, a, i, len(chunks)) for i, (a, _) in enumerate(chunks)],
        )
        total += len(chunks)

    if not args.dry_run and GAPS.exists():
        with GAPS.open(encoding="utf-8", newline="") as f:
            gaps = list(csv.DictReader(f))
        if gaps:
            col = client.get_or_create_collection("kb_manques", metadata={"hnsw:space": "cosine"})
            texts = [f"{g['categorie']} : {g['description']} (décision : {g['decision_concernee']})" for g in gaps]
            col.upsert(ids=[g["id"] for g in gaps], documents=texts, embeddings=embed(texts),
                       metadatas=[{k: v for k, v in g.items()} for g in gaps])
            print(f"{len(gaps)} manques réglementaires indexés")

    if not args.dry_run:
        print(f"\n{total} passages ingérés dans {CHROMA_DIR}")


if __name__ == "__main__":
    main()
