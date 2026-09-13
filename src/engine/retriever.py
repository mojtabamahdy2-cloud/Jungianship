import logging
import numpy as np
from typing import List, Dict, Any, Optional
from src.db.repository import Repository
from src.engine.embedder import Embedder
from src.config import TOP_K_CHUNKS, RRF_K

logger = logging.getLogger(__name__)

class HybridRetriever:
    """Combines FTS5 (BM25) keyword search and Dense Vector embeddings with Reciprocal Rank Fusion (RRF)."""

    def __init__(self, repository: Repository, embedder: Optional[Embedder] = None):
        self.repo = repository
        self.embedder = embedder or Embedder()
        self._cached_chunk_ids: List[int] = []
        self._cached_matrix: Optional[np.ndarray] = None
        self._refresh_vector_index()

    def _refresh_vector_index(self):
        """Loads normalized embedding matrix into memory for microsecond cosine similarity."""
        chunk_ids, matrix = self.repo.get_all_embeddings()
        self._cached_chunk_ids = chunk_ids
        self._cached_matrix = matrix
        if matrix is not None:
            logger.info(f"Loaded {len(chunk_ids)} vector embeddings into in-memory index.")

    def search(self, query: str, top_k: int = TOP_K_CHUNKS) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval and return top matching chunks with metadata."""
        rrf_scores: Dict[int, float] = {}

        # 1. Lexical Search via FTS5
        fts_results = self.repo.fts_search(query, limit=30)
        for rank, item in enumerate(fts_results, start=1):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (RRF_K + rank))

        # 2. Dense Vector Search
        if self._cached_matrix is not None and len(self._cached_chunk_ids) > 0:
            try:
                query_vec = self.embedder.embed_text(query)
                if query_vec is not None:
                    q_arr = np.array(query_vec, dtype=np.float32)
                    q_norm = np.linalg.norm(q_arr)
                    if q_norm > 0:
                        q_arr = q_arr / q_norm
                    # Cosine similarities via dot product with normalized matrix
                    sims = np.dot(self._cached_matrix, q_arr)
                    # Get top matches
                    top_indices = np.argsort(-sims)[:30]
                    for rank, idx in enumerate(top_indices, start=1):
                        cid = self._cached_chunk_ids[idx]
                        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (RRF_K + rank))
            except Exception as e:
                logger.warning(f"Vector search failed, continuing with lexical results: {e}")

        if not rrf_scores:
            return []

        # Sort by combined RRF score descending
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
        
        # Retrieve rich chunk details
        chunks = self.repo.get_chunks_by_ids(sorted_chunk_ids)
        for c in chunks:
            c["rrf_score"] = rrf_scores.get(c["chunk_id"], 0.0)

        return chunks

    def format_context_for_llm(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved passages into structured context with academic citations."""
        if not chunks:
            return "No specific passages found in the indexed corpus."

        formatted_passages = []
        for i, c in enumerate(chunks, start=1):
            source_tag = c.get("cw_volume") or c.get("title") or "Collected Works"
            para_tag = f" {c['para_range']}" if c.get("para_range") else ""
            chapter_tag = f" - Chapter: {c['chapter']}" if c.get("chapter") else ""
            header = f"--- [Passage {i}] Source: {source_tag}{para_tag}{chapter_tag} ---"
            body = c["content"].strip()
            formatted_passages.append(f"{header}\n{body}")

        return "\n\n".join(formatted_passages)
