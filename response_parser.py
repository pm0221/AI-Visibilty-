import json
import os
from config import OUTPUTS_PATH

def parse_results(audit_records: list, brand_name: str,
                  competitors: list,
                  intent_map: dict = None) -> list:
    """
    Presence-based scoring — no ranking.
    A brand gets 1 point for a query if it appeared in 2+ of 3 sessions.
    Each parsed record now carries an 'intent' field (informational / features / comparison).
    """
    print("\n[Phase 10] Parsing results (presence-based, no ranking)...")
    all_brands  = [brand_name] + competitors
    intent_map  = intent_map or {}
    parsed      = []

    for record in audit_records:
        query         = record["query"]
        consistency   = record["consistency"]
        brand_sessions= record["brand_sessions"]   # {brand: sessions_count 0-3}
        others        = record["others"]            # {name: sessions_count}
        intent        = intent_map.get(query, "informational")

        brand_data = {}
        for brand in all_brands:
            sessions_count = brand_sessions.get(brand, 0)
            appeared       = sessions_count >= 2
            brand_data[brand] = {
                "sessions_appeared": sessions_count,
                "appeared":          appeared,
                "consistency":       consistency,
                "segment":           "our_brand" if brand == brand_name else "competitor"
            }

        # Others — appeared in 2+ sessions
        others_list = [
            {"brand": name, "sessions": count}
            for name, count in others.items() if count >= 2
        ]
        others_list.sort(key=lambda x: x["sessions"], reverse=True)

        parsed.append({
            "query":       query,
            "intent":      intent,
            "consistency": consistency,
            "session1":    record["session1_brands"],
            "session2":    record["session2_brands"],
            "session3":    record["session3_brands"],
            "brands":      brand_data,
            "others":      others_list
        })

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(f"{OUTPUTS_PATH}/parsed_results.json", "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    hc   = sum(1 for r in parsed if r["consistency"] == "HC")
    mc   = sum(1 for r in parsed if r["consistency"] == "MC")
    drop = sum(1 for r in parsed if r["consistency"] == "DROP")
    print(f"  HC: {hc} | MC: {mc} | Dropped: {drop} | Total: {len(parsed)}")
    return parsed