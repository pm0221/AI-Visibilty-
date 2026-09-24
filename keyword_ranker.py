import re
import time
from playwright.sync_api import sync_playwright
from config import CHROME_PROFILE_PATH

def _open_gemini():
    """Open one Gemini browser session for keyword ranking."""
    p       = sync_playwright().start()
    browser = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE_PATH,
        headless=False,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    page = browser.new_page()
    for attempt in range(3):
        try:
            print(f"  Connecting to Gemini (attempt {attempt+1}/3)...")
            page.goto("https://gemini.google.com/app",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(6)
            print("  Connected to Gemini")
            return p, browser, page
        except Exception as e:
            print(f"  Connection failed: {e}")
            if attempt < 2:
                time.sleep(10)
            else:
                raise RuntimeError("Cannot reach Gemini for keyword ranking.")

def _ask_gemini(page, prompt: str, wait_seconds: int = 18) -> str:
    """Type a prompt into Gemini and return the text response."""
    try:
        box = page.locator("div[contenteditable='true']").first
        box.click()
        box.fill("")
        box.type(prompt)
        page.keyboard.press("Enter")
        time.sleep(wait_seconds)
        responses = page.locator("message-content").all()
        return responses[-1].inner_text() if responses else ""
    except Exception as e:
        print(f"  Gemini interaction error: {e}")
        return ""

def _build_prompt(keywords: list, brand_name: str, category: str) -> str:
    numbered = "\n".join(f"{i+1}. {kw}" for i, kw in enumerate(keywords))
    return f"""Here is a list of keywords:

{numbered}

Can you rank these keywords in descending order of their relation with the category: {category}

Return only the ranked numbered list. Nothing else."""

def _parse_ranked_response(response: str, original_keywords: list) -> list:
    """
    Extract keywords from Gemini's ranked response.
    Tries to match each line back to an original keyword.
    """
    if not response:
        return original_keywords

    ranked = []
    seen   = set()

    # Split response into lines, strip numbering and bullets
    lines = response.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove leading numbers, dots, dashes, bullets
        cleaned = re.sub(r'^[\d]+[\.\)]\s*', '', line)
        cleaned = re.sub(r'^[-•*]\s*', '', cleaned).strip()
        cleaned = re.sub(r'\*+', '', cleaned).strip()

        if not cleaned or len(cleaned) < 2:
            continue

        # Try exact match with original keywords (case-insensitive)
        matched = None
        cleaned_lower = cleaned.lower()

        # Exact match
        for kw in original_keywords:
            if kw.lower() == cleaned_lower and kw not in seen:
                matched = kw
                break

        # Partial match — cleaned is contained in keyword or vice versa
        if not matched:
            for kw in original_keywords:
                kw_lower = kw.lower()
                if (cleaned_lower in kw_lower or kw_lower in cleaned_lower) \
                        and kw not in seen:
                    matched = kw
                    break

        if matched:
            ranked.append(matched)
            seen.add(matched)

    # If Gemini dropped some keywords or parsing missed them,
    # append any originals not yet in ranked (at the end = lower relevance)
    for kw in original_keywords:
        if kw not in seen:
            ranked.append(kw)
            seen.add(kw)

    return ranked

def rank_keywords(keywords: list, brand_name: str,
                  category: str) -> list:
    """
    Send keyword list to Gemini.
    Gemini ranks them by relevance to the category.
    Returns top 60% of the ranked list.

    These top keywords are the most valid signals for the category
    and will drive Reddit mining and query generation.
    """
    if not keywords:
        return keywords

    print(f"\n[Phase 3.5] Keyword ranking via Gemini")
    print(f"  Sending {len(keywords)} keywords to Gemini for ranking...")
    print(f"  Brand: {brand_name} | Category: {category}")

    prompt = _build_prompt(keywords, brand_name, category)

    p = browser = page = None
    response = ""
    try:
        p, browser, page = _open_gemini()
        response = _ask_gemini(page, prompt, wait_seconds=20)
        print(f"  Gemini response received ({len(response)} chars)")
    except Exception as e:
        print(f"  Gemini ranking error: {e}")
        print("  Falling back to original keyword order")
        return keywords[:int(len(keywords) * 0.6)]
    finally:
        if browser: browser.close()
        if p:       p.stop()

    if not response:
        print("  No response from Gemini — using original order")
        return keywords[:int(len(keywords) * 0.6)]

    # Parse ranked list from response
    ranked_all = _parse_ranked_response(response, keywords)

    # Descending order = most related first, least related last
    # So top 60% most relevant = first 60% of the ranked list
    top_60_pct = max(10, int(len(ranked_all) * 0.6))
    final      = ranked_all[:top_60_pct]

    print(f"\n  Original keywords : {len(keywords)}")
    print(f"  Ranked by Gemini  : {len(ranked_all)}")
    print(f"  Top 60% kept      : {len(final)}")
    print(f"\n  Top 10 most relevant keywords:")
    for i, kw in enumerate(final[:10], 1):
        print(f"    {i:2}. {kw}")

    return final
