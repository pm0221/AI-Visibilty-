import json
import os
import re
import time
from playwright.sync_api import sync_playwright
from config import CHROME_PROFILE_PATH, OUTPUTS_PATH

def _start_browser():
    p       = sync_playwright().start()
    browser = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE_PATH,
        headless=False,
        args=["--no-sandbox","--disable-blink-features=AutomationControlled"]
    )
    page = browser.new_page()
    for attempt in range(3):
        try:
            print(f"  Connecting to Gemini (attempt {attempt+1}/3)...")
            page.goto("https://gemini.google.com/app",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(6)
            print("  Connected")
            return p, browser, page
        except Exception as e:
            print(f"  Connection failed: {e}")
            if attempt < 2:
                time.sleep(10)
            else:
                raise RuntimeError("Cannot reach Gemini.")

def _new_chat(page):
    for attempt in range(3):
        try:
            page.goto("https://gemini.google.com/app",
                      timeout=20000, wait_until="domcontentloaded")
            time.sleep(4)
            return
        except Exception:
            time.sleep(5)

def _ask_query(page, query: str) -> str:
    prompt = (f"{query} "
              f"— list only the brand names that are relevant, "
              f"comma separated. No ranking. No explanation.")
    try:
        box = page.locator("div[contenteditable='true']").first
        box.click()
        box.fill("")
        box.type(prompt)
        page.keyboard.press("Enter")
        time.sleep(12)
        responses = page.locator("message-content").all()
        return responses[-1].inner_text() if responses else ""
    except Exception as e:
        print(f"    Query error: {e}")
        return ""

def _parse_brands(response: str, known_brands: list) -> dict:
    text  = re.sub(r'\*+', '', response)
    text  = re.sub(r'^\d+[\.\)]\s*', '', text, flags=re.MULTILINE)
    text  = text.replace('\n', ',')
    parts = [p.strip() for p in text.split(',') if p.strip()]

    noise = {"the","and","for","with","from","india","best","good","top",
             "also","some","most","other","others","brand","company",
             "option","insurance","plan","products","services","life"}

    known_present  = []
    others_present = []
    seen           = set()

    for part in parts:
        if not part or len(part) < 2:
            continue
        part_lower = part.lower()
        matched = None
        for brand in known_brands:
            b_lower = brand.lower()
            core    = [w for w in b_lower.split() if len(w) > 3]
            if b_lower in part_lower:
                matched = brand; break
            if core and all(w in part_lower for w in core[:2]):
                matched = brand; break
            if core and core[0] in part_lower:
                matched = brand; break

        if matched and matched not in seen:
            seen.add(matched)
            known_present.append(matched)
        elif not matched:
            cap = re.search(r'\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)\b', part)
            if cap:
                name = cap.group(1).strip()
                if name.lower() not in noise and len(name) > 2 and name not in seen:
                    seen.add(name)
                    others_present.append(name)

    return {"known": known_present, "others": others_present}

def _sessions_appeared(brand: str, s1p: dict, s2p: dict, s3p: dict) -> int:
    return sum(1 for s in [s1p, s2p, s3p] if brand in s["known"])

def _query_consistency(s1p: dict, s2p: dict, s3p: dict) -> str:
    s1 = set(s1p["known"])
    s2 = set(s2p["known"])
    s3 = set(s3p["known"])
    if s1 == s2 == s3: return "HC"
    if s1==s2 or s1==s3 or s2==s3: return "MC"
    return "DROP"

def run_audit(queries: list, brand_name: str, competitors: list) -> list:
    print(f"\n[Phase 9] Gemini audit — {len(queries)} queries x 3 sessions")
    print("  Scoring: brand PRESENCE only — no ranking")
    known_brands = [brand_name] + competitors
    session_data = [[], [], []]

    for run_num in range(3):
        print(f"\n  -- Session {run_num+1}/3 --")
        p, browser, page = _start_browser()
        for i, query in enumerate(queries, 1):
            _new_chat(page)
            response = _ask_query(page, query)
            parsed   = _parse_brands(response, known_brands)
            session_data[run_num].append({
                "query":         query,
                "raw_response":  response[:300],
                "known_present": parsed["known"],
                "others_present":parsed["others"]
            })
            print(f"  [{i:02d}/{len(queries)}] {query[:50]}")
            print(f"    Known: {parsed['known']} | Others: {parsed['others'][:3]}")
        browser.close(); p.stop()
        print(f"  Session {run_num+1} complete")

    final = []
    for qi, query in enumerate(queries):
        s1 = session_data[0][qi] if qi < len(session_data[0]) else {}
        s2 = session_data[1][qi] if qi < len(session_data[1]) else {}
        s3 = session_data[2][qi] if qi < len(session_data[2]) else {}
        s1p = {"known":s1.get("known_present",[]),"others":s1.get("others_present",[])}
        s2p = {"known":s2.get("known_present",[]),"others":s2.get("others_present",[])}
        s3p = {"known":s3.get("known_present",[]),"others":s3.get("others_present",[])}
        consistency  = _query_consistency(s1p, s2p, s3p)
        brand_sessions = {b: _sessions_appeared(b,s1p,s2p,s3p) for b in known_brands}
        all_others = {}
        for sp in [s1p, s2p, s3p]:
            for name in sp["others"]:
                all_others[name] = all_others.get(name,0) + 1
        final.append({
            "query":           query,
            "consistency":     consistency,
            "session1_brands": s1p["known"] + s1p["others"],
            "session2_brands": s2p["known"] + s2p["others"],
            "session3_brands": s3p["known"] + s3p["others"],
            "session1_raw":    s1.get("raw_response",""),
            "session2_raw":    s2.get("raw_response",""),
            "session3_raw":    s3.get("raw_response",""),
            "brand_sessions":  brand_sessions,
            "others":          all_others
        })
        status = {"HC":"HC","MC":"MC","DROP":"DROP"}
        print(f"  {status.get(consistency,'?')} | {query[:50]}")
        for b in known_brands:
            if brand_sessions[b] > 0:
                print(f"    {b}: {brand_sessions[b]}/3 sessions")

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(f"{OUTPUTS_PATH}/audit_raw.json","w",encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    hc   = sum(1 for r in final if r["consistency"]=="HC")
    mc   = sum(1 for r in final if r["consistency"]=="MC")
    drop = sum(1 for r in final if r["consistency"]=="DROP")
    print(f"\n  HC: {hc} | MC: {mc} | Dropped: {drop}")
    return final