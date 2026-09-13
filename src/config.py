import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# API Keys & Tokens
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Database & Corpus paths
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "jungianship.db"

# The corpus directory — place your legally-obtained EPUB/PDF texts here.
# Default: a folder named after your persona (e.g., "corpus/") at the project root.
CORPUS_DIR = ROOT_DIR / os.getenv("CORPUS_DIR", "corpus")

# Model Configurations
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))

# Generation Model (Gemini 3.7 Flash)
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "models/gemini-3.7-flash")

# Retrieval Hyperparameters
TOP_K_CHUNKS = 6
CHUNK_SIZE_WORDS = 350
CHUNK_OVERLAP_WORDS = 50
RRF_K = 60

# ──────────────────────────────────────────────────────────────
# Persona Configuration
# Change these (via .env) to adapt the bot to any wise figure.
# Examples: Marcus Aurelius, Friedrich Nietzsche, Simone de Beauvoir,
#           Rumi, Dostoevsky, Epictetus, Ada Lovelace, Einstein…
# ──────────────────────────────────────────────────────────────
PERSONA_NAME        = os.getenv("PERSONA_NAME",        "Carl Gustav Jung")
PERSONA_ERA         = os.getenv("PERSONA_ERA",         "1875–1961")
PERSONA_ROLE        = os.getenv("PERSONA_ROLE",        "Swiss psychiatrist and founder of analytical psychology")
PERSONA_WORKS       = os.getenv("PERSONA_WORKS",       "Collected Works, The Red Book, Memories Dreams Reflections, Seminars, and Letters")
PERSONA_DOMAIN      = os.getenv("PERSONA_DOMAIN",      "analytical psychology, archetypes, the unconscious, individuation, alchemy, and mythology")

# Persona mode: 'first_person' (bot speaks as the figure) or 'scholar' (academic guide)
DEFAULT_MODE = "first_person"   # Options: 'first_person' | 'scholar'
