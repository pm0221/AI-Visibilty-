"""
web_runner.py
Runs the full audit pipeline without any input() calls.
Accepts brand name, URL, category, and competitors from the web form.
Reports progress via update_state and add_log callbacks.
"""
import json
import os


def run_pipeline(brand_name: str, brand_url: str, category: str,
                 competitors: list,          # list of {"name": str, "url": str}
                 update_state,               # callback(current_phase=N, phase_name="...")
                 add_log):                   # callback(message: str)
    try:
        from config               import OUTPUTS_PATH
        from website_scraper      import scrape
        from keyword_extractor    import extract_keywords
        from chroma_memory        import ChromaMemory
        from keyword_intersection import get_intersection_keywords
        from keyword_ranker       import rank_keywords
        from context_miner        import mine_context
        from category_builder     import build_categories
        from query_generator      import generate_queries
        from gemini_auditor       import run_audit
        from response_parser      import parse_results
        from analytics            import calculate_scores
        from report_generator     import generate_html_report
    except ImportError as e:
        raise RuntimeError(f"Import error: {e}")

    os.makedirs(OUTPUTS_PATH, exist_ok=True)

    # Build URL dicts from competitor list
    audit_competitors  = [c["name"] for c in competitors if c.get("name")]
    audit_urls         = {brand_name: brand_url}
    all_scrape_urls    = {brand_name: brand_url}
    for c in competitors:
        if c.get("name") and c.get("url"):
            audit_urls[c["name"]]      = c["url"]
            all_scrape_urls[c["name"]] = c["url"]

    if not audit_competitors:
        raise RuntimeError("No competitors provided.")

    memory = ChromaMemory()

    # ── Phase 1: Already done (competitors provided by form) ──────────────────
    update_state(current_phase=1, phase_name="Competitor Discovery")
    add_log(f"Brand: {brand_name} | Category: {category}")
    add_log(f"Competitors: {', '.join(audit_competitors)}")

    # ── Phase 2: Website scraping ─────────────────────────────────────────────
    update_state(current_phase=2, phase_name="Website Scraping")
    add_log(f"Scraping {len(all_scrape_urls)} websites...")
    for company, url in all_scrape_urls.items():
        if not url:
            add_log(f"  Skipping {company} (no URL)")
            continue
        add_log(f"  Scraping {company}...")
        try:
            text = scrape(url, company)
            if len(text) > 100:
                kws = extract_keywords(text, company)
                memory.store_keywords(company, kws)
                add_log(f"  {company}: {len(kws)} keywords extracted")
            else:
                add_log(f"  Warning: low content for {company}")
        except Exception as e:
            add_log(f"  Error scraping {company}: {e}")

    # ── Phase 3: Keyword intersection ─────────────────────────────────────────
    update_state(current_phase=3, phase_name="Keyword Extraction")
    keywords = get_intersection_keywords(memory, min_companies=2)
    if not keywords:
        add_log("  No intersection found. Using brand keywords.")
        keywords = memory.get_keywords_by_company(brand_name) or []
    if not keywords:
        raise RuntimeError("No keywords found after scraping.")
    add_log(f"  {len(keywords)} keywords from intersection")

    # ── Phase 3.5: Keyword ranking via Gemini ─────────────────────────────────
    update_state(current_phase=4, phase_name="Keyword Ranking (Gemini)")
    add_log(f"  Sending {len(keywords)} keywords to Gemini for ranking...")
    try:
        keywords = rank_keywords(keywords, brand_name, category)
        add_log(f"  Top 60% kept: {len(keywords)} keywords after ranking")
    except Exception as e:
        add_log(f"  Keyword ranking failed ({e}) — using original order")
        keywords = keywords[:int(len(keywords) * 0.6)]

    if not keywords:
        raise RuntimeError("No keywords after ranking.")

    # ── Phase 4: Context mining ────────────────────────────────────────────────
    update_state(current_phase=5, phase_name="Context Mining")
    add_log(f"  Mining Reddit + Google for top {min(len(keywords), 10)} keywords...")
    try:
        context_lines, paa_questions, keyword_patterns = mine_context(
            category, memory, keywords[:15])
        add_log(f"  {len(paa_questions)} PAA questions found")
        add_log(f"  {len(keyword_patterns)} keyword patterns collected")
    except Exception as e:
        add_log(f"  Context mining error: {e}")
        context_lines = paa_questions = keyword_patterns = []

    # ── Phase 5: Category builder ──────────────────────────────────────────────
    update_state(current_phase=6, phase_name="Category Analysis")
    add_log(f"  Analysing category: {category}")
    try:
        cat_data = build_categories(brand_name, keywords, category)
    except Exception as e:
        add_log(f"  Category builder error: {e}")
        cat_data = {}
    industry = cat_data.get("industry") or category
    cat_data["industry"] = industry
    cat_data["category"] = category
    add_log(f"  Industry detected: {industry}")

    # ── Phase 6: Query generation ──────────────────────────────────────────────
    update_state(current_phase=7, phase_name="Query Generation")
    add_log("  Generating queries (free generation + Groq scoring)...")
    queries = generate_queries(
        brand_name, audit_competitors, keywords, memory,
        cat_data, paa_questions, keyword_patterns)
    if not queries:
        raise RuntimeError("No queries generated.")
    add_log(f"  {len(queries)} queries selected for Gemini audit (target 90, minimum 60)")

    # Build intent map
    intent_map = {}
    try:
        with open(f"{OUTPUTS_PATH}/queries_sourced.json", "r", encoding="utf-8") as f:
            qs_data = json.load(f)
        intent_map = {item["query"]: item.get("intent", "informational")
                      for item in qs_data}
    except Exception:
        pass

    # ── Phase 7: Gemini audit ─────────────────────────────────────────────────
    update_state(current_phase=8, phase_name="Gemini Audit")
    add_log(f"  Running {len(queries)} queries × 3 sessions through Gemini...")
    add_log("  This is the longest phase — please wait...")
    audit_records = run_audit(queries, brand_name, audit_competitors)
    if not audit_records:
        raise RuntimeError("Gemini audit returned no results.")
    add_log(f"  Audit complete: {len(audit_records)} records")

    # ── Phase 8: Scoring & Analytics ─────────────────────────────────────────
    update_state(current_phase=9, phase_name="Scoring & Analytics")
    add_log("  Parsing results and calculating scores...")
    parsed = parse_results(audit_records, brand_name, audit_competitors, intent_map)
    scores = calculate_scores(parsed, brand_name, audit_competitors)
    add_log(f"  Scoring complete")
    for brand in [brand_name] + audit_competitors:
        s = scores.get(brand, {})
        add_log(f"  {brand}: {s.get('points',0)} pts | "
                f"{s.get('mention_rate',0):.1f}% | SOV {s.get('share_of_voice',0):.1f}%")

    # Save meta
    meta = {
        "brand_name":    brand_name,
        "brand_url":     brand_url,
        "category":      category,
        "industry":      industry,
        "brand_summary": cat_data.get("brand_summary", ""),
        "competitors":   audit_competitors,
        "audit_urls":    audit_urls,
        "all_scrape_urls": {k: v for k, v in all_scrape_urls.items() if v},
        "keywords":      keywords[:200],
        "queries_generated_for_audit": len(queries),
        "audit_query_target": 90,
        "audit_query_minimum": 60
    }
    with open(f"{OUTPUTS_PATH}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── Phase 9: Dashboard ─────────────────────────────────────────────────────
    update_state(current_phase=10, phase_name="Dashboard Generation")
    add_log("  Generating dashboard report...")
    generate_html_report()
    add_log("  Report saved to outputs/report.html")
