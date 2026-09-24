import json
import time
from playwright.sync_api import sync_playwright
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, CHROME_PROFILE_PATH

client = Groq(api_key=GROQ_API_KEY)

def _google_search(query: str) -> str:
    url  = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en"
    text = ""
    p = browser = None
    try:
        p       = sync_playwright().start()
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH, headless=True)
        page    = browser.new_page()
        page.goto(url, timeout=20000)
        time.sleep(4)
        text = page.inner_text("body")[:6000]
    except Exception as e:
        print(f"  Google search error: {e}")
    finally:
        if browser: browser.close()
        if p:       p.stop()
    return text

def _groq_direct_search(brand_name: str, category: str) -> list:
    """Ask Groq from its own knowledge when Google scraping fails or returns nothing."""
    print(f"  Trying Groq direct knowledge search for {brand_name} competitors...")
    prompt = f"""You are a market research expert for the Indian market.
List the top 8 direct competitors of {brand_name} in the {category} industry in India.
These must be real, well-known brands that compete directly with {brand_name} in India.
Do NOT include {brand_name} itself.
Return ONLY valid json: {{"competitors": ["Brand 1", "Brand 2", ...]}}"""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(resp.choices[0].message.content)
        result = [c for c in data.get("competitors", [])
                  if c.lower() != brand_name.lower()]
        if result:
            print(f"  Groq found {len(result)} competitors directly.")
        return result
    except Exception as e:
        print(f"  Groq direct search error: {e}")
        return []

def _extract_competitors(brand_name: str, category: str, raw: str) -> list:
    prompt = f"""You are a market research expert.
Brand: {brand_name}
Category: {category}
Raw Google search results:
{raw[:3000]}

Extract top 8 direct competitor brand names. Do NOT include {brand_name}.
Return ONLY valid json: {{"competitors": ["Brand 1", "Brand 2", ...]}}"""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(resp.choices[0].message.content)
        return [c for c in data.get("competitors", [])
                if c.lower() != brand_name.lower()]
    except Exception as e:
        print(f"  Groq extraction error: {e}")
        return []


def discover_competitors_web(brand_name: str, category: str) -> list:
    """Discover competitor names for the FastAPI frontend without input().

    Returns a de-duplicated list of names. URL collection is intentionally
    optional in the web flow because competitor names are sufficient for
    Gemini tracking and the scraper can skip a missing URL.
    """
    raw_text = _google_search(f"{brand_name} {category} competitors India top brands")
    competitors = _extract_competitors(brand_name, category, raw_text) if raw_text.strip() else []
    if not competitors:
        competitors = _groq_direct_search(brand_name, category)

    clean = []
    seen = set()
    for c in competitors or []:
        name = str(c).strip()
        key = name.lower()
        if name and key != brand_name.strip().lower() and key not in seen:
            seen.add(key)
            clean.append(name)
    return clean[:8]

def _select_audit_competitors(competitors: list) -> list:
    """Client picks which competitors to TRACK IN GEMINI AUDIT.
    ALL discovered competitors will still be scraped for keywords."""
    print("\n  Discovered competitors (ALL will be scraped for keywords):")
    for i, c in enumerate(competitors, 1):
        print(f"    {i}. {c}")
    print(f"    A. Track All in audit")
    print("\n  Select competitors to TRACK IN AUDIT (e.g. 1 3) or A for all:")
    choice = input("  > ").strip().upper()
    if choice == "A" or choice == "":
        return competitors[:6]
    indices  = [int(x)-1 for x in choice.split() if x.isdigit()]
    selected = [competitors[i] for i in indices if i < len(competitors)]
    return selected[:6]

def _get_urls(names: list, label: str) -> dict:
    urls = {}
    print(f"\n  Enter URLs for {label} (Enter to skip):\n")
    for name in names:
        url = input(f"  {name} URL: ").strip()
        if url:
            if not url.startswith("http"):
                url = "https://" + url
            urls[name] = url
        else:
            print(f"    Skipping {name}")
    return urls

def run_competitor_phase(brand_name: str, brand_url: str,
                         category: str) -> tuple:
    """
    Returns:
      all_scrape_urls  — {company: url} for EVERY discovered site (keyword mining)
      audit_companies  — [brand_name] + audit-selected (Gemini tracking)
      audit_urls       — {company: url} for brand + audit-selected (reports)
    """
    print(f"\n[Phase 1] Searching Google for {brand_name} competitors...")
    raw_text        = _google_search(
        f"{brand_name} {category} competitors India top brands")
    all_competitors = _extract_competitors(brand_name, category, raw_text) if raw_text.strip() else []

    # Fallback 1: Groq direct knowledge search
    if not all_competitors:
        print("  Google scraping returned no usable data.")
        all_competitors = _groq_direct_search(brand_name, category)

    # Fallback 2: Manual entry
    if not all_competitors:
        print("  Auto-discovery failed completely.")
        raw             = input("  Enter competitors manually (comma separated): ")
        all_competitors = [c.strip() for c in raw.split(",") if c.strip()]

    # Client selects subset for Gemini audit tracking
    audit_selected = _select_audit_competitors(all_competitors)

    # URLs for audit-selected (confirmed by user)
    print("\n  Enter URLs for AUDIT-SELECTED competitors:")
    audit_comp_urls = _get_urls(audit_selected, "audit competitor")

    # URLs for remaining discovered (keyword scraping only)
    non_selected = [c for c in all_competitors if c not in audit_selected]
    if non_selected:
        print(f"\n  {len(non_selected)} additional competitor(s) for KEYWORD SCRAPING ONLY.")
        extra_urls = _get_urls(non_selected, "keyword-only competitor")
    else:
        extra_urls = {}

    # Build all_scrape_urls: brand + ALL competitors with URLs
    all_scrape_urls = {brand_name: brand_url}
    all_scrape_urls.update(audit_comp_urls)
    all_scrape_urls.update(extra_urls)

    # Audit scope
    audit_companies = [brand_name] + audit_selected
    audit_urls      = {brand_name: brand_url}
    audit_urls.update(audit_comp_urls)

    print(f"\n  Keyword scraping ({len(all_scrape_urls)} sites):")
    for name, url in all_scrape_urls.items():
        tag = " [AUDIT]" if name in audit_companies else " [keywords only]"
        print(f"    {name}{tag} → {url}")

    print(f"\n  Gemini audit tracking ({len(audit_companies)} brands):")
    for name in audit_companies:
        print(f"    {name}")

    return all_scrape_urls, audit_companies, audit_urls