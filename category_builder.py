import json
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)

def build_categories(brand_name: str, keywords: list,
                     user_category: str = "") -> dict:
    print(f"\n[Phase 5] Building category framework...")
    kw_sample = ", ".join(keywords[:60]) if keywords else "no keywords"
    prompt = f"""
You are a market research expert.
Brand: {brand_name}
User-provided category: {user_category}
Keywords from website analysis: {kw_sample}

Return ONLY valid json:
- "industry": precise industry name
- "product_categories": list of 5-8 specific categories
- "query_types": list of 6-8 query types for Indian consumers
- "india_context": list of 3-4 India-specific angles
- "target_audience": who buys this in India
- "brand_summary": 2 sentence summary of what this brand offers
"""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(resp.choices[0].message.content)
        print(f"  Industry: {data.get('industry','unknown')}")
        return data
    except Exception as e:
        print(f"  Category builder error: {e}")
        return {"industry": user_category, "product_categories": [],
                "query_types": [], "india_context": [],
                "target_audience": "Indian consumers",
                "brand_summary": ""}