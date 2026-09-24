import json
import os
import re
import time
from groq import Groq
from playwright.sync_api import sync_playwright
from config import GROQ_API_KEY, GROQ_MODEL, OUTPUTS_PATH, CHROME_PROFILE_PATH
from chroma_memory import ChromaMemory

groq_client = Groq(api_key=GROQ_API_KEY)

# Gemini audit budget. We generate a larger pool, then audit up to 90 high-quality
# queries. If fewer than 60 genuinely valid queries survive, we still audit all
# valid queries rather than inventing fake questions.
AUDIT_TARGET_QUERIES = 90
AUDIT_MIN_QUERIES = 60
MAX_GENERATION_ATTEMPTS = 3

# ── Validation helpers ─────────────────────────────────────────────────────────
PAGE_GARBAGE = [
    "about this page", "ip address", "cached", "similar pages",
    "search tools", "settings", "sign in", "did you mean",
    "showing results", "feedback", "safesearch", "privacy", "terms",
    "advertise", "translate this page", "google account", "gmail",
    "read more", "see more", "view all", "show more", "next page",
    "http", "www.", ".com", ".in", ".org", "©", "→", "»",
]

def _is_valid(text: str) -> bool:
    t = text.strip()
    if len(t.split()) < 4 or len(t.split()) > 20:
        return False
    if not t[0].isalpha():
        return False
    if any(p in t.lower() for p in PAGE_GARBAGE):
        return False
    if any(c in t for c in ["|", "©", "•", "·"]):
        return False
    return True

def _contains_brand(query: str, brands: list) -> bool:
    q = query.lower()
    for brand in brands:
        for word in brand.lower().split():
            if len(word) > 3 and word in q:
                return True
    return False

def _word_overlap(q1: str, q2: str) -> float:
    w1 = set(q1.lower().split())
    w2 = set(q2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / min(len(w1), len(w2))

def _deduplicate(items: list, threshold: float = 0.80) -> list:
    kept    = []
    dropped = 0
    for item in items:
        q      = item["query"]
        is_dup = any(_word_overlap(q, k["query"]) >= threshold for k in kept)
        if not is_dup:
            kept.append(item)
        else:
            dropped += 1
    print(f"  Deduplication: {len(items)} → {len(kept)} ({dropped} removed)")
    return kept

# ── Google mining ──────────────────────────────────────────────────────────────
def _scrape_google(page, search_query: str, n: int = 20) -> list:
    results = []
    try:
        page.goto(
            f"https://www.google.com/search?q={search_query.replace(' ','+')}",
            timeout=15000)
        time.sleep(3)
        text = page.inner_text("body")
        for line in text.split("\n"):
            line = line.strip()
            if _is_valid(line):
                results.append(line)
            if len(results) >= n:
                break
    except Exception as e:
        print(f"    Scrape error '{search_query}': {e}")
    return results

def _mine_google(page, industry: str, keywords: list) -> tuple:
    print("  Mining Google search patterns (20 results per search)...")
    searches = [industry + " India", "best " + industry + " India"]
    for kw in keywords[:5]:
        searches.append(kw + " India")

    all_lines     = []
    seen          = set()
    mining_record = {}

    for search in searches:
        lines = _scrape_google(page, search, n=20)
        taken = []
        for line in lines:
            k = line.lower().strip()
            if k not in seen:
                seen.add(k)
                all_lines.append({"text": line, "source": f"Google: {search}"})
                taken.append(line)
        mining_record[search] = taken
        print(f"    '{search}' → {len(taken)} lines")

    print(f"    Total search patterns: {len(all_lines)}")
    return all_lines[:200], mining_record

# ── Groq call ──────────────────────────────────────────────────────────────────
def _groq_call(prompt: str, call_name: str, max_tokens: int = 4096) -> list:
    print(f"  [{call_name}] Sending to Groq...")
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=max_tokens
        )
        data    = json.loads(resp.choices[0].message.content)
        queries = [q.strip() for q in data.get("queries", []) if q.strip()]
        print(f"    Returned: {len(queries)} queries")
        return queries
    except Exception as e:
        print(f"    Groq error: {e}")
        return []


# ── Raw query deduplication ────────────────────────────────────────────────────
def _deduplicate_raw(queries: list, threshold: float = 0.75) -> list:
    """Deduplicate a flat list of query strings before scoring."""
    kept       = []
    seen_exact = set()
    for q in queries:
        q = q.strip()
        if not q or len(q.split()) < 3:
            continue
        key = q.lower()
        if key in seen_exact:
            continue
        seen_exact.add(key)
        if not any(_word_overlap(q, k) >= threshold for k in kept):
            kept.append(q)
    return kept

# ── Step 1 prompt — free, unconstrained generation ────────────────────────────
def _free_gen_prompt(mined_content: str, paa_str: str,
                     kw_str: str, industry: str) -> str:
    return f"""Study the real Indian consumer discussions below about {industry}.
Find the patterns — how do Indians phrase questions about {industry}?
What vocabulary, what specific details, what tone?
How do they mix English and Hindi (Hinglish)?

KEYWORDS (from {industry} company websites):
{kw_str}

REAL DISCUSSIONS (Reddit, Quora, Google — how Indians actually talk about {industry}):
{mined_content}

REAL QUESTIONS Indians typed on Google:
{paa_str}

Generate 100 search queries that match these patterns exactly.
These should be queries a real Indian person would type into an AI chatbot or Google.

Let the content above drive the distribution — do NOT force an equal split.
If the discussions are mostly about specific problems, generate more problem-specific queries.
If they discuss buying more, generate more purchase queries. Follow the pattern naturally.

DO NOT:
- Mention any specific brand or company name
- Generate formal survey-style questions ("What are the comprehensive benefits of...")
- Invent topics not present in the discussions above

DO:
- Match the tone and vocabulary from the discussions above exactly
- Include Hinglish where it appears naturally in the discussions
- Include specific details (skin type, hair issue, lifestyle, location)
- Vary query length — some short (5-6 words), most medium (8-12 words)
- Let grammar imperfections stay if that is how the original content reads

Return ONLY valid json: {{"queries": ["query 1", "query 2", ...]}}"""

# ── Step 2 prompt — naturalness scoring + intent classification ───────────────
def _score_classify_prompt(numbered: str, n: int, industry: str) -> str:
    return f"""You are evaluating search queries about {industry} written for an Indian audience.

For EACH query, give TWO things:

1. NATURALNESS score — how likely is a real Indian person to type this exact query:
   3 = Definitely real. Sounds like someone typed it, not wrote it.
       Examples: "beard oil kaun sa best hai patchy growth ke liye",
                 "does face wash actually remove tanning in humid weather",
                 "which shampoo good for oily scalp AND dandruff both problem"
   2 = Borderline. Could be real but slightly generic or slightly formal.
   1 = Clearly AI-generated. Formal, polished, no real person types this.
       Examples: "What are the comprehensive benefits of beard oil?",
                 "How does one select the optimal hair care product for their needs?",
                 "Please suggest grooming solutions pertaining to my requirements"

2. INTENT — what stage of the journey is this query from:
   informational = learning what something is, how it works, types available
   features      = asking about specific product attributes, ingredients, effects
   situational   = person describes their specific personal context or problem
   purchase      = ready to buy, asking where/how/price/what to check before buying

QUERIES:
{numbered}

Return ONLY valid json with exactly {n} items:
{{
  "results": [
    {{"id": 1, "naturalness": 3, "intent": "situational"}},
    {{"id": 2, "naturalness": 1, "intent": "informational"}},
    ...
  ]
}}
Score every single query — return exactly {n} results."""

# ── Main generate_queries ──────────────────────────────────────────────────────
def generate_queries(brand_name: str, competitors: list,
                     keywords: list, memory: ChromaMemory,
                     cat_data: dict = None,
                     paa_questions: list = None,
                     keyword_patterns: list = None) -> list:

    print(f"\n[Phase 6] Query generation — 2 steps: free generation → Groq scoring")

    cat_data         = cat_data or {}
    # Industry fallback chain: detected → raw category → brand name
    # Never use brand_name alone — it tells Groq nothing about the domain
    industry = (cat_data.get("industry")
                or cat_data.get("category")
                or cat_data.get("brand_summary", "")[:40]
                or brand_name + " products")

    print(f"  Industry for query generation: {industry}")

    all_brands       = [brand_name] + competitors
    paa_questions    = paa_questions    or []
    keyword_patterns = keyword_patterns or []
    kw_str           = ", ".join(keywords[:40])
    paa_str          = "\n".join(paa_questions[:40]) if paa_questions else "(none)"

    # NOTE: We deliberately do NOT use memory.get_context() here.
    # ChromaDB accumulates data across all runs (different brands/categories).
    # Using it would mix life insurance content into a grooming audit, etc.
    # Instead we use only freshly mined keyword_patterns from the current run.

    # Mine Google at category level for additional patterns
    p = browser = page = None
    google_data   = []
    mining_record = {}
    try:
        p       = sync_playwright().start()
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH, headless=True)
        page    = browser.new_page()
        google_data, mining_record = _mine_google(page, industry, keywords)
    except Exception as e:
        print(f"  Browser error: {e}")
    finally:
        if browser: browser.close()
        if p:       p.stop()

    # Pool mined content — keyword_patterns (Reddit/Quora/Hinglish) + Google
    # Do NOT include ChromaDB context (stale from previous runs)
    google_text     = "\n".join(item["text"] for item in google_data[:30])
    kw_pattern_text = "\n".join(keyword_patterns[:150])
    mined_content   = "\n".join(filter(None, [
        google_text,       # category-level Google (current run)
        kw_pattern_text    # per-keyword Reddit/Quora/Hinglish (current run)
    ])).strip()

    if not mined_content.strip():
        print("  WARNING: mined content is empty — queries may be generic")

    print(f"  Mined content: {len(mined_content.splitlines())} lines "
          f"({len(google_data)} google + {len(keyword_patterns)} kw-specific patterns)")

    # ── STEP 1: Free unconstrained generation ──────────────────────────────────
    print("\n  Step 1: Free generation (up to 3 Groq calls)...")
    gen_prompt = _free_gen_prompt(mined_content[:2500], paa_str[:800], kw_str[:600], industry)

    raw_queries = []
    cleaned = []
    unique = []
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        batch = _groq_call(gen_prompt, f"Free Generation {attempt}/{MAX_GENERATION_ATTEMPTS}", max_tokens=9000)
        raw_queries.extend(batch)

        cleaned = []
        for q in raw_queries:
            q = q.strip()
            if not q:
                continue
            if any(c in q for c in ["|", "©", "•"]):
                continue
            if any(p in q.lower() for p in ["http", "www.", ".com"]):
                continue
            if _contains_brand(q, all_brands):
                c = q
                for brand in all_brands:
                    for word in brand.split():
                        if len(word) > 3:
                            c = re.sub(r'\b' + re.escape(word) + r'\b', '', c, flags=re.IGNORECASE)
                c = re.sub(r'\s+', ' ', c).strip()
                if len(c.split()) >= 3 and not _contains_brand(c, all_brands):
                    cleaned.append(c)
            else:
                cleaned.append(q)

        unique = _deduplicate_raw(cleaned)
        print(f"  Generation pool after attempt {attempt}: raw={len(raw_queries)} cleaned={len(cleaned)} deduped={len(unique)}")
        if len(unique) >= AUDIT_TARGET_QUERIES:
            break

    if not unique:
        print("  No queries generated. Exiting.")
        return []

    # ── STEP 2: Score naturalness + classify intent (batches of 50) ───────────
    print(f"\n  Step 2: Groq scoring naturalness + intent ({len(unique)} queries in batches of 50)...")
    scored_all = []
    batch_size = 50

    for batch_start in range(0, len(unique), batch_size):
        batch    = unique[batch_start:batch_start + batch_size]
        numbered = "\n".join(f"{j+1}. {q}" for j, q in enumerate(batch))
        prompt   = _score_classify_prompt(numbered, len(batch), industry)

        print(f"    Scoring batch {batch_start//batch_size + 1} "
              f"(queries {batch_start+1}–{batch_start+len(batch)})...")
        try:
            resp = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data    = json.loads(resp.choices[0].message.content)
            results = data.get("results", [])
            for item in results:
                idx = item.get("id", 0) - 1
                if 0 <= idx < len(batch):
                    scored_all.append({
                        "query":       batch[idx],
                        "naturalness": int(item.get("naturalness", 2)),
                        "intent":      item.get("intent", "informational"),
                        "source":      "free_generation",
                        "branded":     False,
                    })
        except Exception as e:
            print(f"    Scoring error: {e} — adding batch with naturalness=2")
            for q in batch:
                scored_all.append({
                    "query": q, "naturalness": 2, "intent": "informational",
                    "source": "free_generation", "branded": False
                })

    # ── Filter: keep naturalness ≥ 2, sort 3s first ───────────────────────────
    passed  = [r for r in scored_all if r.get("naturalness", 1) >= 2]
    dropped = [r for r in scored_all if r.get("naturalness", 1) < 2]
    passed.sort(key=lambda x: x["naturalness"], reverse=True)

    # Keep the Gemini workload bounded. Target 90, with 60 as the minimum
    # acceptable audit set when enough valid queries exist.
    if len(passed) >= AUDIT_TARGET_QUERIES:
        final = passed[:AUDIT_TARGET_QUERIES]
    else:
        final = passed

    final_queries = [item["query"] for item in final]

    # ── Summary ───────────────────────────────────────────────────────────────
    n3 = sum(1 for r in final if r["naturalness"] == 3)
    n2 = sum(1 for r in final if r["naturalness"] == 2)
    by_intent = {}
    for r in final:
        by_intent[r.get("intent", "informational")] = \
            by_intent.get(r.get("intent", "informational"), 0) + 1

    print(f"\n  ── RESULTS ──────────────────────────────────────")
    print(f"  Generated raw        : {len(raw_queries)}")
    print(f"  After dedup+clean    : {len(unique)}")
    print(f"  Naturalness ≥ 2      : {len(passed)}  "
          f"(score 3 genuine: {n3}  score 2 borderline: {n2})")
    print(f"  Dropped (score 1)    : {len(dropped)}")
    print(f"  Audit target          : {AUDIT_TARGET_QUERIES} (minimum {AUDIT_MIN_QUERIES})")
    print(f"  FINAL → Gemini       : {len(final)}")
    if len(final) < AUDIT_MIN_QUERIES:
        print(f"  WARNING: only {len(final)} valid queries survived; auditing all valid queries available.")
    print(f"\n  Intent distribution (Groq-classified, not forced):")
    for intent in ["informational", "features", "situational", "purchase"]:
        n = by_intent.get(intent, 0)
        bar = "█" * (n // 2)
        print(f"    {intent:<16} {n:>3}  {bar}")

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(f"{OUTPUTS_PATH}/queries_sourced.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/queries_all.json", "w", encoding="utf-8") as f:
        json.dump(final_queries, f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/queries_mining_record.json", "w", encoding="utf-8") as f:
        json.dump(mining_record, f, indent=2, ensure_ascii=False)

    return final_queries