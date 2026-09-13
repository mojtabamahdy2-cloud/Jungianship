import sqlite3
from pathlib import Path
from src.config import DB_PATH

def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a thread-safe connection to the SQLite database with WAL mode."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Path = DB_PATH):
    """Initialize database tables and FTS5 search index."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        author TEXT DEFAULT 'C. G. Jung',
        cw_volume TEXT,
        year TEXT,
        format TEXT,
        chunk_count INTEGER DEFAULT 0,
        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Chunks table (with BLOB embedding)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        chapter TEXT,
        section TEXT,
        para_range TEXT,
        content TEXT NOT NULL,
        token_count INTEGER DEFAULT 0,
        embedding BLOB,
        FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks (doc_id);")

    # FTS5 virtual table for keyword search
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        content,
        chapter,
        cw_volume,
        title,
        tokenize = 'porter unicode61'
    );
    """)

    # User sessions & conversation memory
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        user_id INTEGER PRIMARY KEY,
        chat_id INTEGER,
        mode TEXT DEFAULT 'jung',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        citations TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user_id ON chat_history (user_id);")

    # Curated Aphorisms / Quotes table for /quote
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote TEXT NOT NULL,
        source TEXT NOT NULL,
        cw_ref TEXT,
        theme TEXT
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
