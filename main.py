import os
import json

def run():
    try:
        from config            import OUTPUTS_PATH
        from competitor_finder import run_competitor_phase
        from website_scraper   import scrape
        from keyword_extractor import extract_keywords
        from chroma_memory     import ChromaMemory
        from keyword_intersection import get_intersection_keywords
        from keyword_ranker       import rank_keywords
        from context_miner        import mine_context
        from category_builder  import build_categories
        from query_generator   import generate_queries
        from confidence_engine import score_queries
        from gemini_auditor    import run_audit
        from response_parser   import parse_results
        from analytics         import calculate_scores
    except ImportError as e:
        print(f"Import error: {e}"); return

    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    print("=" * 60)
    print("   AI VISIBILITY AUDIT TOOL")
    print("=" * 60)

    brand_name = input("\nEnter your brand name: ").strip()
    brand_url  = input("Enter your brand website URL: ").strip()
    category   = input("Enter the category: ").strip()

    # ── Phase 1: Competitor discovery ─────────────────────────────────────────
    # Returns: all_scrape_urls (ALL discovered, for keyword mining)
    #          audit_companies ([brand] + selected, for Gemini tracking)
    #          audit_urls ({company: url} for brand + selected)
    all_scrape_urls, audit_companies, audit_urls = run_competitor_phase(
        brand_name, brand_url, category)

    audit_competitors = [c for c in audit_companies if c != brand_name]
    if not audit_competitors:
        print("  No competitors selected for audit. Exiting."); return

    memory = ChromaMemory()

    # ── Phase 2: Scrape ALL discovered sites for keywords ─────────────────────
    print(f"\n[Phase 2] Scraping {len(all_scrape_urls)} websites for keywords...")
    for company, url in all_scrape_urls.items():
        if not url:
            print(f"  Skipping {company} (no URL)")
            continue
        text = scrape(url, company)
        if len(text) > 100:
            kws = extract_keywords(text, company)
            memory.store_keywords(company, kws)
        else:
            print(f"  Warning: low content for {company}")

    # ── Phase 3: Keyword intersection ─────────────────────────────────────────
    keywords = get_intersection_keywords(memory, min_companies=2)
    if not keywords:
        print("  No intersection. Using brand keywords.")
        keywords = memory.get_keywords_by_company(brand_name) or []
    if not keywords:
        print("  No keywords found. Exiting."); return
    print(f"  Using {len(keywords)} intersection keywords")

    # ── Phase 3.5: Keyword ranking via Gemini ─────────────────────────────────
    # Gemini ranks keywords by category relevance, returns top 60%
    # These become the signals for Reddit mining and query generation
    keywords = rank_keywords(keywords, brand_name, category)
    if not keywords:
        print("  Keyword ranking returned nothing. Exiting."); return
    print(f"  Using {len(keywords)} Gemini-ranked keywords for mining")

    # ── Phase 5: Category builder ──────────────────────────────────────────────
    cat_data = build_categories(brand_name, keywords, category)
    industry = cat_data.get("industry") or category   # always use user category as fallback
    cat_data["industry"]  = industry                  # guarantee it is set for all downstream calls
    cat_data["category"]  = category                  # keep original user input too

    # ── Phase 4: Context mining + PAA ─────────────────────────────────────────
    # Use raw user 'category' for mining — it is always more precise than
    # whatever category_builder infers (e.g. user typed "beard grooming"
    # vs category_builder inferring "Personal Care")
    context_lines, paa_questions, keyword_patterns = mine_context(
        category, memory, keywords[:15])

    # ── Phase 6: Query generation (6 Groq calls, intent-labelled) ─────────────
    queries = generate_queries(
        brand_name, audit_competitors, keywords, memory, cat_data,
        paa_questions, keyword_patterns)
    if not queries:
        print("  No queries generated. Exiting."); return
    print(f"  Total queries to score: {len(queries)}")

    # Build intent_map from queries_sourced.json
    # Intent was assigned by Groq scoring in Phase 6 — no confidence engine needed
    intent_map = {}
    try:
        with open(f"{OUTPUTS_PATH}/queries_sourced.json", "r", encoding="utf-8") as f:
            qs_data = json.load(f)
        intent_map = {item["query"]: item.get("intent", "informational")
                      for item in qs_data}
        print(f"  Intent map built for {len(intent_map)} queries")
    except Exception as e:
        print(f"  Warning: could not build intent map — {e}")

    # ── Phase 7: Confidence scoring ────────────────────────────────────────────
    # SKIPPED — Groq already scored naturalness in Phase 6.
    # All queries returned by generate_queries have naturalness ≥ 2.
    validated_queries = queries
    print(f"  Passing {len(validated_queries)} queries to Gemini (pre-scored by Groq)")
    if not validated_queries:
        print("  No queries generated. Exiting."); return

    # ── Phase 9: Gemini audit (3 sessions, only audit_competitors tracked) ─────
    audit_records = run_audit(validated_queries, brand_name, audit_competitors)
    if not audit_records:
        print("  Audit returned no results. Exiting."); return

    # ── Phase 10: Parse results (intent attached via intent_map) ───────────────
    parsed = parse_results(audit_records, brand_name, audit_competitors, intent_map)
    if not parsed:
        print("  No parsed results. Exiting."); return

    # ── Phase 11: Analytics (organic vs comparison split) ─────────────────────
    scores = calculate_scores(parsed, brand_name, audit_competitors)

    # Save meta
    meta = {
        "brand_name":      brand_name,
        "brand_url":       brand_url,
        "category":        category,
        "industry":        industry,
        "brand_summary":   cat_data.get("brand_summary", ""),
        "competitors":     audit_competitors,
        "audit_urls":      audit_urls,
        "all_scrape_urls": {k: v for k, v in all_scrape_urls.items() if v},
        "keywords":        keywords[:200]
    }
    with open(f"{OUTPUTS_PATH}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── Phase 12: Dashboard ────────────────────────────────────────────────────
    try:
        from report_generator import generate_html_report
        generate_html_report()
        print(f"\n  Dashboard → outputs/report.html")
    except Exception as e:
        print(f"  Dashboard error: {e}")
        import traceback; traceback.print_exc()

    print("\n" + "="*60)
    print("  AUDIT COMPLETE")
    print(f"  Outputs saved to: {OUTPUTS_PATH}/")
    print("="*60)

if __name__ == "__main__":
    run()