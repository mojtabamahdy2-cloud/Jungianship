import sys
import time
import logging
from src.db.database import init_db
from src.db.repository import Repository
from src.engine.embedder import Embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main(max_chunks: int = 1500):
    init_db()
    repo = Repository()
    embedder = Embedder()

    logger.info(f"Checking for unembedded chunks (target limit: {max_chunks})...")
    unembedded = repo.get_unembedded_chunks(limit=max_chunks)
    total = len(unembedded)
    logger.info(f"Found {total} unembedded chunks.")

    if total == 0:
        logger.info("All chunks already have embeddings!")
        return

    batch_size = 25
    done = 0
    for i in range(0, total, batch_size):
        batch = unembedded[i : i + batch_size]
        texts = [c["content"] for c in batch]
        cids = [c["id"] for c in batch]

        t0 = time.time()
        try:
            embeddings = embedder.embed_batch(texts, batch_size=batch_size, delay_sec=0.2)
            for cid, emb in zip(cids, embeddings):
                repo.update_chunk_embedding(cid, emb)
            done += len(embeddings)
            logger.info(f"Progress: [{done}/{total}] chunks embedded ({time.time() - t0:.1f}s for batch)")
        except Exception as e:
            logger.error(f"Error embedding batch at {i}: {e}")
            time.sleep(3)

    stats = repo.get_stats()
    logger.info(f"Done! Total embedded chunks in database: {stats['embedded_count']}")

if __name__ == "__main__":
    max_c = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    main(max_c)
