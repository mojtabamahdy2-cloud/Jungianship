"""
index_corpus.py — Corpus Ingestion Script

Parses EPUB files from your corpus directory, chunks them into semantically
coherent passages, indexes them into SQLite + FTS5, and optionally generates
dense vector embeddings via Google Gemini.

Usage:
    # Index all EPUBs in your corpus directory (default, recommended)
    python index_corpus.py --scope all

    # Index only a hand-picked core set defined in CORE_FILENAMES below
    python index_corpus.py --scope core

    # Index a single specific file
    python index_corpus.py --scope single --file "YourBook.epub"

    # Include embedding generation (requires GEMINI_API_KEY)
    python index_corpus.py --scope all --embed

Adapting for a different persona:
    1. Set PERSONA_NAME, CORPUS_DIR etc. in your .env file.
    2. Place your legally-obtained EPUBs in the corpus directory.
    3. Optionally update CORE_FILENAMES below to match your key works.
    4. Run this script with --scope all --embed.
"""

import sys
import argparse
import logging
from pathlib import Path

from src.config import CORPUS_DIR, DB_PATH, PERSONA_NAME
from src.db.database import init_db
from src.db.repository import Repository
from src.ingestion.epub_parser import EpubParser
from src.ingestion.chunker import Chunker
from src.engine.embedder import Embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# CORE_FILENAMES — Optional hand-picked priority works.
# Edit this list to match the key texts in your corpus.
# These are indexed when using --scope core.
#
# Default example: Carl Jung's foundational works.
# Replace with your own filenames for a different persona.
# ──────────────────────────────────────────────────────────────
CORE_FILENAMES = [
    # Add the filenames of your most important source EPUBs here, e.g.:
    # "Author - Major_Work_One (Publisher, Year).epub",
    # "Author - Major_Work_Two (Publisher, Year).epub",
]


def index_epub(epub_file: Path, repo: Repository, chunker: Chunker, embedder: Embedder = None, embed: bool = False):
    logger.info(f"Parsing: {epub_file.name}")
    parser = EpubParser(epub_file, author=PERSONA_NAME)
    meta = parser.meta

    sections = parser.parse()
    if not sections:
        logger.warning(f"No sections extracted from {epub_file.name}")
        return

    chunks = chunker.chunk_sections(sections, meta)
    logger.info(f"Extracted {len(chunks)} chunks from '{meta['title']}' ({meta.get('cw_volume', '')})")

    # Save to SQLite and FTS5
    doc_id = repo.save_document(
        filename=epub_file.name,
        title=meta["title"],
        author=meta.get("author", PERSONA_NAME),
        cw_volume=meta.get("cw_volume", ""),
        year=meta.get("year", ""),
        file_format="epub"
    )

    repo.save_chunks(doc_id, chunks, title=meta["title"], cw_volume=meta.get("cw_volume", ""))
    logger.info(f"Saved {len(chunks)} chunks & FTS index for '{meta['title']}'")

    # Embed if requested
    if embed and embedder:
        logger.info(f"Generating embeddings for {len(chunks)} chunks in '{meta['title']}'...")
        unembedded = repo.get_unembedded_chunks(limit=1000)
        while unembedded:
            texts = [c["content"] for c in unembedded]
            cids = [c["id"] for c in unembedded]
            embeddings = embedder.embed_batch(texts, batch_size=25, delay_sec=0.2)
            for cid, emb in zip(cids, embeddings):
                repo.update_chunk_embedding(cid, emb)
            logger.info(f"Embedded batch of {len(embeddings)} chunks.")
            unembedded = repo.get_unembedded_chunks(limit=1000)


def main():
    parser = argparse.ArgumentParser(
        description=f"Index corpus texts for '{PERSONA_NAME}' into SQLite + FTS5 + Vector DB"
    )
    parser.add_argument(
        "--scope",
        choices=["single", "core", "all"],
        default="all",
        help=(
            "Indexing scope:\n"
            "  'all'    — Index every EPUB in CORPUS_DIR (recommended)\n"
            "  'core'   — Index only the files listed in CORE_FILENAMES\n"
            "  'single' — Index one specific file (use with --file)"
        )
    )
    parser.add_argument("--file", type=str, default=None,
                        help="Specific EPUB filename to index (required if --scope single)")
    parser.add_argument("--embed", action="store_true",
                        help="Generate dense vector embeddings during indexing (requires GEMINI_API_KEY)")
    args = parser.parse_args()

    if not CORPUS_DIR.exists():
        logger.error(
            f"Corpus directory not found: {CORPUS_DIR}\n"
            "Create the directory and place your legally-obtained EPUB files in it.\n"
            "See README → 'Sourcing the Corpus' for guidance."
        )
        sys.exit(1)

    init_db()
    repo = Repository()
    chunker = Chunker(target_words=350, overlap_words=50)
    embedder = Embedder() if args.embed else None

    if args.scope == "single":
        filename = args.file
        if not filename:
            logger.error("--scope single requires --file <filename>")
            sys.exit(1)
        epub_path = CORPUS_DIR / filename
        if not epub_path.exists():
            logger.error(f"File not found: {epub_path}")
            sys.exit(1)
        index_epub(epub_path, repo, chunker, embedder, embed=args.embed)

    elif args.scope == "core":
        if not CORE_FILENAMES:
            logger.warning("CORE_FILENAMES is empty. Edit index_corpus.py to add your key works, or use --scope all.")
            sys.exit(0)
        for fn in CORE_FILENAMES:
            path = CORPUS_DIR / fn
            if path.exists():
                index_epub(path, repo, chunker, embedder, embed=args.embed)
            else:
                logger.warning(f"Core file not found (skipping): {fn}")

    elif args.scope == "all":
        epubs = list(CORPUS_DIR.glob("*.epub"))
        if not epubs:
            logger.warning(f"No EPUB files found in {CORPUS_DIR}")
            sys.exit(0)
        logger.info(f"Found {len(epubs)} EPUBs to index.")
        for ep in epubs:
            index_epub(ep, repo, chunker, embedder, embed=args.embed)

    stats = repo.get_stats()
    logger.info("=== Indexing Completed ===")
    logger.info(f"Persona: {PERSONA_NAME}")
    logger.info(f"Total documents indexed: {stats['document_count']}")
    logger.info(f"Total text chunks: {stats['chunk_count']}")
    logger.info(f"Vector embedded chunks: {stats['embedded_count']}")
    if stats["volumes"]:
        logger.info(f"Indexed volumes: {', '.join(stats['volumes'])}")


if __name__ == "__main__":
    main()
