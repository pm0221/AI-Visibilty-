import asyncio
import json
import urllib.request
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from chroma_memory import ChromaMemory

# ── Search amplifiers — surface discussions not product pages ──────────────────
# For each keyword we run 3 targeted searches to get real user discussions
KW_AMPLIFIERS = [
    "{kw} reddit india",              # Reddit threads — most authentic
    "{kw} quora india problems",      # Quora Q&A — real questions + answers
    "{kw} india kaisa hota hai",      # Hinglish amplifier — surfaces Indian-language content
]

# ── PAA extractor ──────────────────────────────────────────────────────────────
def _extract_paa(text: str) -> list:
    paa, seen = [], set()
    starters = [
        "what ", "how ", "why ", "which ", "when ", "where ", "who ",
        "is ", "are ", "can ", "do ", "does ", "should ", "will ", "was ",
        "क्या ", "कैसे ", "कौन ", "कब ", "क्यों ",
        "kya ", "kaisa ", "konsa ", "kaunsa ", "kaise ",
    ]
    bad = [
        "cookie", "privacy", "terms", "login", "sign in", "click here",
        "menu", "search", "filter", "sort", "home page", "http",
        "newsletter", "subscribe", "advertis",
    ]
    for line in text.split("\n"):
        line = line.strip()
        if not (12 < len(line) < 180):
            continue
        lower = line.lower()
        if not any(lower.startswith(w) for w in starters):
            continue
        if any(b in lower for b in bad):
            continue
        key = lower.strip("?. ")
        if key not in seen:
            seen.add(key)
            paa.append(line)
            if len(paa) >= 60:
                break
    return paa

def _clean_lines(raw: str, min_len=20, max_len=250) -> list:
    return [l.strip() for l in raw.split("\n")
            if min_len < len(l.strip()) < max_len
            and not l.strip().startswith("http")
            and not l.strip().startswith("[")]

# ── Reddit JSON API — no browser needed ───────────────────────────────────────
def _fetch_reddit(keyword: str) -> list:
    """Fetch real Reddit post titles + body snippets for a keyword."""
    encoded = keyword.replace(" ", "+")
    results = []
    for subreddit_scope in [f"{encoded}+india", f"{encoded}+India+advice"]:
        url = (f"https://www.reddit.com/search.json"
               f"?q={subreddit_scope}&limit=6&sort=relevance&t=year")
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 GEO-Audit-Tool/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                pd    = post.get("data", {})
                title = pd.get("title", "").strip()
                body  = pd.get("selftext", "").strip()[:200]
                if title and 15 < len(title) < 220:
                    results.append(f"[Reddit] {title}")
                if body and len(body) > 25:
                    # extract first real sentence from body
                    first_sentence = body.split(".")[0].strip()
                    if len(first_sentence) > 20:
                        results.append(f"[Reddit] {first_sentence}")
        except Exception:
            pass
    return results[:8]

# ── Main async miner ───────────────────────────────────────────────────────────
async def _mine_all(category: str, keywords: list) -> tuple:
    """
    3-layer mining strategy:
      Layer 1 — Category-level Google (3 searches) → broad context + PAA
      Layer 2 — Per-keyword Google with 3 amplifiers each → real discussions + PAA
               Amplifiers: reddit / quora problems / hinglish kaisa hota hai
      Layer 3 — Per-keyword Reddit JSON API → authentic post titles and discussions
    """
    browser_cfg = BrowserConfig(browser_type="chromium", headless=True)
    run_cfg     = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        page_timeout=20000)

    all_lines   = []
    all_paa     = []
    kw_patterns = []
    seen_lines  = set()
    seen_paa    = set()
    seen_kw     = set()

    cat = category.replace(" ", "+")
    cat_urls = [
        f"https://www.google.com/search?q={cat}+india+best+review&hl=en",
        f"https://www.google.com/search?q={cat}+india+tips+experience&hl=en",
        f"https://www.google.com/search?q={cat}+india+which+is+best&hl=en",
    ]

    async with AsyncWebCrawler(config=browser_cfg) as crawler:

        # ── Layer 1: Category-level Google ────────────────────────────────────
        print("  Layer 1: category-level Google")
        for url in cat_urls:
            try:
                res = await crawler.arun(url=url, config=run_cfg)
                if not res.success or not res.markdown:
                    continue
                lines = _clean_lines(res.markdown)[:15]
                for l in lines:
                    k = l.lower().strip()
                    if k not in seen_lines:
                        seen_lines.add(k)
                        all_lines.append(l)
                for q in _extract_paa(res.markdown):
                    k = q.lower().strip("?. ")
                    if k not in seen_paa:
                        seen_paa.add(k)
                        all_paa.append(q)
                print(f"    {len(lines)} lines")
            except Exception as e:
                print(f"    Error: {e}")

        # ── Layer 2: Per-keyword Google × 3 amplifiers ────────────────────────
        top_kws = keywords[:10]   # top 10 × 3 amplifiers = 30 searches
        print(f"\n  Layer 2: per-keyword Google × 3 amplifiers ({len(top_kws)} keywords)")

        for kw in top_kws:
            kw_added = 0
            for amplifier_template in KW_AMPLIFIERS:
                search_term = amplifier_template.replace("{kw}", kw)
                encoded     = search_term.replace(" ", "+")
                url         = f"https://www.google.com/search?q={encoded}&hl=en"
                try:
                    res = await crawler.arun(url=url, config=run_cfg)
                    if not res.success or not res.markdown:
                        continue
                    lines = _clean_lines(res.markdown)[:8]
                    paa   = _extract_paa(res.markdown)[:5]
                    for l in lines:
                        k = l.lower().strip()
                        if k not in seen_kw:
                            seen_kw.add(k)
                            kw_patterns.append(f"[{kw}] {l}")
                            kw_added += 1
                    for q in paa:
                        k = q.lower().strip("?. ")
                        if k not in seen_paa:
                            seen_paa.add(k)
                            all_paa.append(q)
                except Exception as e:
                    print(f"      '{search_term[:40]}' error: {e}")

            print(f"    '{kw}': {kw_added} discussion lines collected")

    # ── Layer 3: Per-keyword Reddit JSON API ─────────────────────────────────
    print(f"\n  Layer 3: per-keyword Reddit ({len(top_kws)} keywords)")
    for kw in top_kws:
        reddit_lines = _fetch_reddit(kw)
        added = 0
        for l in reddit_lines:
            k = l.lower().strip()
            if k not in seen_kw:
                seen_kw.add(k)
                kw_patterns.append(f"[{kw}] {l}")
                added += 1
        if added:
            print(f"    '{kw}': {added} Reddit posts")

    total_kw = len(kw_patterns)
    print(f"\n  Total discussion patterns collected: {total_kw}")
    return all_lines[:60], all_paa[:60], kw_patterns[:200]

# ── Public API ─────────────────────────────────────────────────────────────────
def mine_context(category: str, memory: ChromaMemory,
                 keywords: list = None) -> tuple:
    """
    Returns (context_lines, paa_questions, keyword_patterns).

    context_lines    — category-level Google lines (stored in ChromaDB)
    paa_questions    — real PAA questions from all searches
    keyword_patterns — per-keyword discussion lines from Google (reddit/quora/hinglish
                       amplified) + Reddit JSON, labelled as "[keyword] line"
                       These are the raw material for extraction-based query generation.
    """
    print(f"\n[Phase 4] Mining context for: {category}")
    print(f"  Using top 10 keywords × 3 amplifiers + Reddit JSON")

    context_lines, paa_questions, keyword_patterns = asyncio.run(
        _mine_all(category, keywords or []))

    if context_lines:
        memory.store_context(context_lines, source="google_reddit")

    print(f"  Context lines  : {len(context_lines)}")
    print(f"  PAA questions  : {len(paa_questions)}")
    print(f"  Kw patterns    : {len(keyword_patterns)}")
    return context_lines, paa_questions, keyword_patterns