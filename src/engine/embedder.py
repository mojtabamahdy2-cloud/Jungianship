import time
import logging
from typing import List, Optional
from google import genai
from google.genai.errors import APIError
from src.config import GEMINI_API_KEY, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

class Embedder:
    """Generates dense vector embeddings using Google Gemini API."""

    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = EMBEDDING_MODEL):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Embed a single query or text string. Fail-fast if quota is constrained."""
        clean = text.strip()[:2000]
        if not clean:
            return None
        
        try:
            resp = self.client.models.embed_content(
                model=self.model,
                contents=clean
            )
            return resp.embeddings[0].values
        except Exception as e:
            logger.info(f"Embedding API unavailable/quota constrained ({e}); falling back to FTS5 lexical search.")
            return None

    def embed_batch(self, texts: List[str], batch_size: int = 20, delay_sec: float = 0.5) -> List[List[float]]:
        """Embed a batch of texts with progress and automatic rate-limit throttling."""
        all_embeddings = []
        clean_texts = [t.strip()[:2000] for t in texts]

        for i in range(0, len(clean_texts), batch_size):
            batch = clean_texts[i : i + batch_size]
            for attempt in range(5):
                try:
                    resp = self.client.models.embed_content(
                        model=self.model,
                        contents=batch
                    )
                    for emb in resp.embeddings:
                        all_embeddings.append(emb.values)
                    break
                except Exception as e:
                    logger.warning(f"Batch embedding error at index {i} (attempt {attempt + 1}/5): {e}")
                    time.sleep(2 ** (attempt + 1))
            
            if delay_sec > 0:
                time.sleep(delay_sec)

        return all_embeddings
