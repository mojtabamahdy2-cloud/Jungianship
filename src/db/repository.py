import json
import sqlite3
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from src.db.database import get_db_connection

class Repository:
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or get_db_connection()

    def get_document_by_filename(self, filename: str) -> Optional[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE filename = ?", (filename,))
        return cursor.fetchone()

    def save_document(self, filename: str, title: str, author: str = "C. G. Jung",
                      cw_volume: str = "", year: str = "", file_format: str = "epub") -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO documents (filename, title, author, cw_volume, year, format)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                title = excluded.title,
                cw_volume = excluded.cw_volume,
                year = excluded.year,
                format = excluded.format
            RETURNING id;
        """, (filename, title, author, cw_volume, year, file_format))
        doc_id = cursor.fetchone()[0]
        self.conn.commit()
        return doc_id

    def save_chunks(self, doc_id: int, chunks: List[Dict[str, Any]], title: str = "", cw_volume: str = ""):
        """Batch save chunks and index them in FTS5."""
        cursor = self.conn.cursor()
        
        # Delete old chunks for this doc if re-indexing
        cursor.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))
        old_ids = [row[0] for row in cursor.fetchall()]
        if old_ids:
            cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            cursor.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", [(i,) for i in old_ids])

        for c in chunks:
            emb_bytes = None
            if c.get("embedding") is not None:
                emb = np.array(c["embedding"], dtype=np.float32)
                emb_bytes = emb.tobytes()

            cursor.execute("""
                INSERT INTO chunks (doc_id, chapter, section, para_range, content, token_count, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                c.get("chapter", ""),
                c.get("section", ""),
                c.get("para_range", ""),
                c["content"],
                c.get("token_count", 0),
                emb_bytes
            ))
            chunk_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO chunks_fts (chunk_id, content, chapter, cw_volume, title)
                VALUES (?, ?, ?, ?, ?)
            """, (
                chunk_id,
                c["content"],
                c.get("chapter", ""),
                cw_volume,
                title
            ))

        cursor.execute("UPDATE documents SET chunk_count = ? WHERE id = ?", (len(chunks), doc_id))
        self.conn.commit()

    def update_chunk_embedding(self, chunk_id: int, embedding: List[float]):
        cursor = self.conn.cursor()
        emb_bytes = np.array(embedding, dtype=np.float32).tobytes()
        cursor.execute("UPDATE chunks SET embedding = ? WHERE id = ?", (emb_bytes, chunk_id))
        self.conn.commit()

    def get_unembedded_chunks(self, limit: int = 200) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, content FROM chunks WHERE embedding IS NULL LIMIT ?
        """, (limit,))
        return [{"id": row["id"], "content": row["content"]} for row in cursor.fetchall()]

    def fts_search(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search full-text FTS5 index using BM25 scoring."""
        # Sanitize query: remove special characters that break FTS syntax
        cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in query).strip()
        if not cleaned:
            return []
        
        # Build token query with wildcard for trailing words
        tokens = cleaned.split()
        fts_query = " ".join(f'"{t}"*' if len(t) > 2 else f'"{t}"' for t in tokens)

        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    f.chunk_id,
                    f.content,
                    f.chapter,
                    f.cw_volume,
                    f.title,
                    bm25(chunks_fts) as rank_score,
                    c.para_range,
                    c.section,
                    c.doc_id
                FROM chunks_fts f
                JOIN chunks c ON c.id = f.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY rank_score ASC
                LIMIT ?
            """, (fts_query, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            # Fallback simple search if match fails
            try:
                simple_query = f'"{cleaned}"'
                cursor.execute("""
                    SELECT 
                        f.chunk_id,
                        f.content,
                        f.chapter,
                        f.cw_volume,
                        f.title,
                        bm25(chunks_fts) as rank_score,
                        c.para_range,
                        c.section,
                        c.doc_id
                    FROM chunks_fts f
                    JOIN chunks c ON c.id = f.chunk_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank_score ASC
                    LIMIT ?
                """, (simple_query, limit))
                return [dict(r) for r in cursor.fetchall()]
            except Exception:
                return []

    def get_all_embeddings(self) -> Tuple[List[int], Optional[np.ndarray]]:
        """Load all chunk IDs and their embedding vectors into memory for fast cosine search."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL")
        rows = cursor.fetchall()
        if not rows:
            return [], None

        chunk_ids = []
        vectors = []
        for r in rows:
            chunk_ids.append(r["id"])
            vec = np.frombuffer(r["embedding"], dtype=np.float32)
            vectors.append(vec)

        matrix = np.vstack(vectors)
        # Normalize vectors for fast dot product cosine similarity
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        norm_matrix = matrix / norms

        return chunk_ids, norm_matrix

    def get_chunks_by_ids(self, chunk_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch chunks by IDs with joined document metadata."""
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        cursor = self.conn.cursor()
        cursor.execute(f"""
            SELECT 
                c.id as chunk_id,
                c.content,
                c.chapter,
                c.section,
                c.para_range,
                c.doc_id,
                d.title,
                d.cw_volume,
                d.author,
                d.year
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE c.id IN ({placeholders})
        """, chunk_ids)
        rows = {r["chunk_id"]: dict(r) for r in cursor.fetchall()}
        # Preserve input order
        return [rows[cid] for cid in chunk_ids if cid in rows]

    # Session & Chat History Methods
    def get_user_mode(self, user_id: int) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT mode FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["mode"] if row else "jung"

    def set_user_mode(self, user_id: int, mode: str, chat_id: Optional[int] = None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO user_sessions (user_id, chat_id, mode, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                mode = excluded.mode,
                chat_id = COALESCE(excluded.chat_id, user_sessions.chat_id),
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, chat_id, mode))
        self.conn.commit()

    def save_message(self, user_id: int, role: str, content: str, citations: Optional[List[str]] = None):
        cursor = self.conn.cursor()
        cit_str = json.dumps(citations) if citations else None
        cursor.execute("""
            INSERT INTO chat_history (user_id, role, content, citations)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, content, cit_str))
        self.conn.commit()

    def get_history(self, user_id: int, limit: int = 8) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT role, content, citations, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        history = [dict(r) for r in reversed(rows)]
        for h in history:
            if h["citations"]:
                try:
                    h["citations"] = json.loads(h["citations"])
                except Exception:
                    pass
        return history

    def clear_history(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        self.conn.commit()

    # Quotes / Synchronistic Aphorisms
    def get_random_quote(self, theme: Optional[str] = None) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if theme:
            cursor.execute("""
                SELECT quote, source, cw_ref, theme FROM quotes
                WHERE theme LIKE ? ORDER BY RANDOM() LIMIT 1
            """, (f"%{theme}%",))
        else:
            cursor.execute("SELECT quote, source, cw_ref, theme FROM quotes ORDER BY RANDOM() LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    def seed_quotes(self, quotes_list: List[Dict[str, str]]):
        cursor = self.conn.cursor()
        for q in quotes_list:
            cursor.execute("""
                INSERT INTO quotes (quote, source, cw_ref, theme)
                VALUES (?, ?, ?, ?)
            """, (q["quote"], q.get("source", "C. G. Jung"), q.get("cw_ref", ""), q.get("theme", "General")))
        self.conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
        embedded_count = cursor.fetchone()[0]
        cursor.execute("SELECT DISTINCT cw_volume FROM documents WHERE cw_volume != ''")
        volumes = [r[0] for r in cursor.fetchall()]
        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "embedded_count": embedded_count,
            "volumes": volumes
        }
