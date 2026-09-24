import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Secrets are loaded from environment variables. Never commit real API keys.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

CHROMADB_PATH = os.getenv("CHROMADB_PATH", str(BASE_DIR / "chroma_db"))
CONTEXT_COLLECTION = "brand_consumer_context"
DROPPED_PATTERNS_COLLECTION = "dropped_query_patterns"
KEYWORDS_COLLECTION = "company_keywords"

CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", str(BASE_DIR / "chrome_profile"))
OUTPUTS_PATH = os.getenv("OUTPUTS_PATH", str(BASE_DIR / "outputs"))

Path(CHROMADB_PATH).mkdir(parents=True, exist_ok=True)
Path(CHROME_PROFILE_PATH).mkdir(parents=True, exist_ok=True)
Path(OUTPUTS_PATH).mkdir(parents=True, exist_ok=True)
