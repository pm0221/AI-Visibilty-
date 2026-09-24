import json
import os
from config import OUTPUTS_PATH

def _any_brand_scored(entry: dict, all_brands: list) -> bool:
    """A query is useful if at least one tracked brand appeared in 2+ sessions."""
    return any(
        entry["brands"].get(b, {}).get("appeared", False)
        for b in all_brands
    )

def calculate_scores(parsed: list, brand_name: str,
                     competitors: list) -> dict:
    print("\n[Phase 11] Calculating visibility scores (presence-based)...")
    all_brands = [brand_name] + competitors

    # CORRECT DROP LOGIC:
    # A query is dropped ONLY when NO tracked brand (brand or competitor)
    # appeared in 2+ sessions. The old SET-based consistency check was wrong —
    # Beardo appearing in 3/3 sessions should always score even if other brands
    # varied across sessions.
    scored  = [r for r in parsed if _any_brand_scored(r, all_brands)]
    dropped = [r for r in parsed if not _any_brand_scored(r, all_brands)]

    organic     = scored
    n           = len(organic)
    INTENT_KEYS = ("informational", "features", "situational", "purchase")

    scores = {}

    for brand in all_brands:
        points      = 0
        appeared_in = []
        hc_list     = []
        mc_list     = []
        by_intent   = {k: {"points": 0, "total_queries": 0} for k in INTENT_KEYS}

        # Score on organic queries only
        for entry in organic:
            intent = entry.get("intent", "informational")
            if intent in by_intent:
                by_intent[intent]["total_queries"] += 1

            bd = entry["brands"].get(brand, {})
            if bd.get("appeared"):
                points += 1
                if intent in by_intent:
                    by_intent[intent]["points"] += 1
                appeared_in.append({
                    "query":       entry["query"],
                    "intent":      intent,
                    "sessions":    bd.get("sessions_appeared", 0),
                    "consistency": entry["consistency"]
                })
                if entry["consistency"] == "HC":
                    hc_list.append(entry["query"])
                elif entry["consistency"] == "MC":
                    mc_list.append(entry["query"])

        scores[brand] = {
            "segment":          "our_brand" if brand == brand_name else "competitor",
            "points":           points,
            "mention_rate":     round(points / n * 100, 1) if n else 0,
            "mention_count":    points,
            "hc_queries":       len(hc_list),
            "mc_queries":       len(mc_list),
            "total_organic_queries": n,
            "total_scored_queries":  len(scored),
            "dropped_queries":  len(dropped),
            "by_intent":        by_intent,
            "appeared_in":      appeared_in
        }

    # Share of Voice — organic points only
    total_points = sum(scores[b]["points"] for b in all_brands)
    for brand in all_brands:
        sov = round(scores[brand]["points"] / total_points * 100, 1) \
              if total_points else 0
        scores[brand]["share_of_voice"] = sov

    # Others — unique QUERIES where at least one untracked brand appeared (2+ sessions)
    # We track each brand individually but the combined "Others" count is
    # unique queries, not the sum of all appearances (which would exceed 100%).
    others_map = {}
    other_query_set = set()      # track unique queries for the combined count

    for entry in organic:
        has_other = False
        for other in entry.get("others", []):
            name = other.get("brand", "")
            if not name:
                continue
            has_other = True
            if name not in others_map:
                others_map[name] = {"brand": name, "points": 0, "queries": set()}
            others_map[name]["points"] += 1
            others_map[name]["queries"].add(entry["query"])
        if has_other:
            other_query_set.add(entry["query"])

    others_scored = sorted(
        [{"brand": name,
          "mention_count": d["points"],
          "mention_rate": round(d["points"] / n * 100, 1) if n else 0,
          "appeared_in": list(d["queries"])[:10]}
         for name, d in others_map.items()],
        key=lambda x: x["mention_count"], reverse=True
    )
    other_query_count = len(other_query_set)   # unique queries, always ≤ n
    scores["__others__"] = {
        "segment":        "others",
        "brands":         others_scored[:20],
        "total_brands":   len(others_scored),
        "mention_count":  other_query_count,
        "mention_rate":   round(other_query_count / n * 100, 1) if n else 0,
        "unique_queries": other_query_count
    }

    # Dropped queries — logged for dashboard insight section
    scores["__dropped__"] = {
        "count":   len(dropped),
        "queries": [
            {
                "query":    d["query"],
                "session1": d["session1"],
                "session2": d["session2"],
                "session3": d["session3"]
            }
            for d in dropped
        ]
    }

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(f"{OUTPUTS_PATH}/scores.json", "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)

    # Console summary
    print("\n" + "="*60)
    print("  FINAL RESULTS (all scored queries — dropped excluded)")
    print(f"  Scored queries: {n} | Dropped: {len(dropped)}")
    print("="*60)
    for brand in all_brands:
        s   = scores[brand]
        tag = " <- YOUR BRAND" if brand == brand_name else " [COMPETITOR]"
        print(f"\n  {brand}{tag}")
        print(f"    Organic Points  : {s['points']}/{n}")
        print(f"    Mention Rate    : {s['mention_rate']}%")
        print(f"    Share of Voice  : {s['share_of_voice']}%")
        bi = s["by_intent"]
        print(f"    Informational   : {bi['informational']['points']} pts / {bi['informational']['total_queries']} q")
        print(f"    Features        : {bi['features']['points']} pts / {bi['features']['total_queries']} q")
    print("="*60)
    return scores

# ── Standalone re-run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    OUTPUTS_PATH = "./outputs"

    def _load(fname):
        import os
        p = f"{OUTPUTS_PATH}/{fname}"
        if not os.path.exists(p):
            print(f"  ERROR: {p} not found — run main.py first"); sys.exit(1)
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    print("Re-calculating scores from existing parsed_results.json ...")
    parsed      = _load("parsed_results.json")
    meta        = _load("meta.json")
    brand_name  = meta.get("brand_name", "")
    competitors = meta.get("competitors", [])

    if not brand_name:
        print("  ERROR: meta.json missing brand_name"); sys.exit(1)

    scores = calculate_scores(parsed, brand_name, competitors)
    print(f"\n  scores.json updated → {OUTPUTS_PATH}/scores.json")
    print("  Now run:  python report_generator.py")