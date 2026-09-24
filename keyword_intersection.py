from chroma_memory import ChromaMemory

def get_intersection_keywords(memory: ChromaMemory,
                              min_companies: int = 2) -> list:
    """
    Find keywords appearing across 2+ company websites.
    Returns up to 200 keywords sorted by occurrence count.
    Increased from previous 80-keyword limit.
    """
    print(f"\n[Phase 3] Finding intersection keywords...")
    companies   = memory.get_all_companies()
    print(f"  Companies stored: {companies}")

    keyword_map = {}
    for company in companies:
        kws = memory.get_keywords_by_company(company)
        for kw in kws:
            keyword_map.setdefault(kw.lower(), set()).add(company)

    # keywords that appear in 2+ company sites
    # sorted by number of companies they appear in (most common first)
    intersection = sorted(
        [kw for kw, comps in keyword_map.items()
         if len(comps) >= min_companies],
        key=lambda kw: len(keyword_map[kw]),
        reverse=True
    )

    # cap at 200 keywords
    intersection = intersection[:200]

    print(f"  Total unique keywords : {len(keyword_map)}")
    print(f"  Intersection keywords : {len(intersection)}")
    if intersection:
        print(f"  Top 10: {intersection[:10]}")
    return intersection