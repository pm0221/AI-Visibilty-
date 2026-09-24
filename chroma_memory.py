import chromadb
import time
from config import (CHROMADB_PATH, CONTEXT_COLLECTION,
                    DROPPED_PATTERNS_COLLECTION, KEYWORDS_COLLECTION)

class ChromaMemory:
    def __init__(self):
        self.client       = chromadb.PersistentClient(path=CHROMADB_PATH)
        self.context_col  = self.client.get_or_create_collection(CONTEXT_COLLECTION)
        self.dropped_col  = self.client.get_or_create_collection(DROPPED_PATTERNS_COLLECTION)
        self.keywords_col = self.client.get_or_create_collection(KEYWORDS_COLLECTION)

    def store_keywords(self, company: str, keywords: list):
        if not keywords:
            return
        ids  = [f"kw_{company}_{i}_{abs(hash(k))}" for i, k in enumerate(keywords)]
        meta = [{"company": company} for _ in keywords]
        try:
            self.keywords_col.upsert(documents=keywords, metadatas=meta, ids=ids)
            print(f"  Stored {len(keywords)} keywords for {company}")
        except Exception as e:
            print(f"  Keyword store error: {e}")

    def get_keywords_by_company(self, company: str) -> list:
        try:
            results = self.keywords_col.get(where={"company": company})
            return results.get("documents", [])
        except Exception:
            return []

    def get_all_companies(self) -> list:
        try:
            results = self.keywords_col.get()
            metas   = results.get("metadatas", [])
            return list({m["company"] for m in metas if m})
        except Exception:
            return []

    def store_context(self, texts: list, source: str = "web"):
        if not texts:
            return
        ts   = int(time.time() * 1000)
        ids  = [f"ctx_{source}_{ts}_{i}" for i, _ in enumerate(texts)]
        meta = [{"source": source} for _ in texts]
        try:
            self.context_col.upsert(documents=texts, metadatas=meta, ids=ids)
            print(f"  Stored {len(texts)} context blocks [{source}]")
        except Exception as e:
            print(f"  Context store error: {e}")

    def get_context(self, limit: int = 20) -> str:
        try:
            results = self.context_col.get(limit=limit)
            docs    = results.get("documents", [])
            return "\n".join(docs) if docs else "No context found."
        except Exception:
            return "No context found."

    def store_dropped(self, dropped: list):
        if not dropped:
            return
        ts   = int(time.time() * 1000)
        ids  = [f"drop_{ts}_{i}" for i, _ in enumerate(dropped)]
        docs = [f"Query: '{d['query']}' | Reason: {d.get('reason','Low score')}" for d in dropped]
        meta = [{"reason": d.get("reason","Low score")} for d in dropped]
        try:
            self.dropped_col.upsert(documents=docs, metadatas=meta, ids=ids)
            print(f"  Stored {len(dropped)} dropped patterns")
        except Exception as e:
            print(f"  Dropped store error: {e}")

    def get_dropped_patterns(self, limit: int = 15) -> list:
        try:
            results = self.dropped_col.get(limit=limit)
            return results.get("documents", [])
        except Exception:
            return []