import json
import os
import math
import time
from groq import Groq
from playwright.sync_api import sync_playwright
from config import GROQ_API_KEY, GROQ_MODEL, OUTPUTS_PATH, CHROME_PROFILE_PATH
from chroma_memory import ChromaMemory

client = Groq(api_key=GROQ_API_KEY)

INTENT_WORDS = [
    "best", "top", "which", "what", "how", "why", "where",
    "kaun", "konsa", "kya", "kaise", "recommend", "suggest",
    "compare", "vs", "versus", "better", "difference", "sahi",
    "accha", "batao", "lena chahiye", "buy", "purchase", "review",
    "option", "plan", "policy", "sabse", "kaunsa", "choose",
    "should", "worth", "reliable", "trusted", "safe"
]

NOISE_PHRASES = [
    "it looks like", "feel free", "let me know",
    "as an ai", "i cannot", "please note",
    "i'm sorry", "as requested", "certainly here",
    "about this page", "ip address", "cached"
]

def _classify_intent(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["vs", "versus", "compare", "better than",
                              "difference", "or ", "which is better"]):
        return "commercial investigation"
    elif any(w in q for w in ["buy", "purchase", "apply", "get policy",
                               "lena", "khareed", "enroll"]):
        return "transactional"
    elif any(w in q for w in ["best", "top", "recommend", "suggest",
                               "kaun", "sabse", "accha", "sahi", "review"]):
        return "commercial investigation"
    elif any(w in q for w in ["what is", "how does", "explain", "kya hai",
                               "kaise kaam", "meaning", "define", "kya hota"]):
        return "informational"
    else:
        return "informational"

def _structural_score(query: str, keywords: list) -> tuple:
    score  = 0
    reason = []
    words  = query.strip().split()

    # Signal 1 — length (0 or 25)
    if 4 <= len(words) <= 18:
        score += 25
    else:
        reason.append(f"bad length ({len(words)} words)")

    # Signal 2 — intent word (0 or 25)
    if any(w.lower() in query.lower() for w in INTENT_WORDS):
        score += 25
    else:
        reason.append("no intent words")

    # Instant fail for noise
    if any(p in query.lower() for p in NOISE_PHRASES):
        return 0, "instant fail — noise phrase"

    # Signal 3 — keyword match (0 or 25)
    if keywords and any(k.lower() in query.lower() for k in keywords[:100]):
        score += 25
    else:
        reason.append("no keyword match")

    # max structural = 75
    return score, ", ".join(reason) if reason else "passed"

def _google_score(page, query: str) -> float:
    if page is None:
        return 10.0
    try:
        page.goto(
            f"https://www.google.com/search?q={query.replace(' ','+')}",
            timeout=15000)
        time.sleep(2)
        text  = page.inner_text("body").lower()
        words = set(query.lower().split())
        lines = [l.strip() for l in text.split("\n")
                 if 10 < len(l.strip()) < 120]
        best  = max(
            (len(words & set(l.split())) for l in lines), default=0)
        return min(round(best / max(len(words), 1) * 25, 2), 25.0)
    except Exception:
        return 10.0

def _logprob_score(query: str) -> float:
    try:
        half = query[:max(len(query) // 2, 10)]
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system",
                 "content": "Complete this Indian consumer search query naturally:"},
                {"role": "user", "content": half}
            ],
            max_tokens=15,
            logprobs=True,
            top_logprobs=1
        )
        tokens = (resp.choices[0].logprobs.content
                  if resp.choices[0].logprobs else [])
        if not tokens:
            return 12.5
        avg_lp = sum(t.logprob for t in tokens) / len(tokens)
        return min(round(math.exp(avg_lp) * 25, 2), 25.0)
    except Exception:
        return 12.5

def _get_label(score: float) -> str:
    # Max possible: structural(75) + consistency(25) + google(25) + logprob(25) = 150
    # HC: structural passes fully (75) + consistency (25) = 100 minimum
    # MC: at least 2 structural signals + consistency = 75
    # LC: below 75
    if score >= 100:
        return "HC"
    elif score >= 70:
        return "MC"
    else:
        return "LC"

def score_queries(queries: list, keywords: list,
                  memory: ChromaMemory) -> tuple:
    print(f"\n[Phase 7] Scoring {len(queries)} queries...")
    print(f"  Max possible score: 150")
    print(f"  HC ≥ 100 | MC 70-99 | LC < 70\n")

    # load source map
    sourced_path = f"{OUTPUTS_PATH}/queries_sourced.json"
    source_map   = {}
    if os.path.exists(sourced_path):
        try:
            with open(sourced_path, encoding="utf-8") as f:
                for item in json.load(f):
                    source_map[item["query"].lower().strip()] = item.get("source","")
        except Exception:
            pass

    p = browser = page = None
    try:
        p       = sync_playwright().start()
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH, headless=True)
        page    = browser.new_page()
    except Exception as e:
        print(f"  Browser error: {e}")
        page = None

    passed     = []
    lc_list    = []
    all_scored = []

    print(f"  {'#':<4} {'Score':>6}/150 {'Label':<5} {'Intent':<25} Query")
    print(f"  {'-'*80}")

    for i, q in enumerate(queries, 1):
        s1, reason = _structural_score(q, keywords)

        if s1 == 0:
            s2 = s3 = s4 = 0
            total = 0
        else:
            s2    = 25.0
            s3    = _google_score(page, q)
            s4    = _logprob_score(q)
            total = round(s1 + s2 + s3 + s4, 2)

        label      = _get_label(total)
        intent     = _classify_intent(q)
        difficulty = min(round(total / 1.5), 100)  # scale to 0-100
        source     = source_map.get(q.lower().strip(), "Groq AI")

        drop_reason = ""
        if label == "LC":
            if "noise"   in reason: drop_reason = "Contains noise text"
            elif "length" in reason: drop_reason = "Query too short or long"
            elif "intent" in reason: drop_reason = "No search intent detected"
            elif "keyword"in reason: drop_reason = "Not relevant to category"
            else:                    drop_reason = f"Low score: {reason}"

        entry = {
            "query":       q,
            "score":       total,
            "label":       label,
            "passed":      label in ("HC", "MC"),
            "intent":      intent,
            "difficulty":  difficulty,
            "source":      source,
            "drop_reason": drop_reason,
            "reason":      reason,
            "layers": {
                "structural":  s1,
                "consistency": s2,
                "google":      round(s3, 2),
                "logprob":     round(s4, 2)
            }
        }
        all_scored.append(entry)

        print(f"  {i:<4} [{total:>6.1f}] {label:<5} {intent:<25} {q[:45]}")

        if label in ("HC", "MC"):
            passed.append(q)
        else:
            lc_list.append(entry)

    if browser: browser.close()
    if p:       p.stop()

    # store LC in ChromaDB
    memory.store_dropped([
        {"query": e["query"], "reason": e["drop_reason"]}
        for e in lc_list
    ])

    hc = sum(1 for r in all_scored if r["label"] == "HC")
    mc = sum(1 for r in all_scored if r["label"] == "MC")
    lc = sum(1 for r in all_scored if r["label"] == "LC")

    print(f"\n  ┌──────────────────────────────────────────┐")
    print(f"  │  SCORING SUMMARY (max score = 150)       │")
    print(f"  ├──────────────────────────────────────────┤")
    print(f"  │ HC (≥100)  → Gemini : {hc:>4}              │")
    print(f"  │ MC (70-99) → Gemini : {mc:>4}              │")
    print(f"  │ LC (<70)   → dropped: {lc:>4}              │")
    print(f"  │ Passing to audit    : {len(passed):>4}              │")
    print(f"  └──────────────────────────────────────────┘")

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(f"{OUTPUTS_PATH}/scored_queries.json",
              "w", encoding="utf-8") as f:
        json.dump(all_scored, f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/hc_queries.json",
              "w", encoding="utf-8") as f:
        json.dump([r for r in all_scored if r["label"]=="HC"],
                  f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/mc_queries.json",
              "w", encoding="utf-8") as f:
        json.dump([r for r in all_scored if r["label"]=="MC"],
                  f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/lc_queries.json",
              "w", encoding="utf-8") as f:
        json.dump(lc_list, f, indent=2, ensure_ascii=False)
    with open(f"{OUTPUTS_PATH}/passed_queries.json",
              "w", encoding="utf-8") as f:
        json.dump(passed, f, indent=2, ensure_ascii=False)

    return passed, all_scored