import re

STRIP_SUFFIXES = [
    "life insurance", "general insurance", "insurance company",
    "insurance", "life", "limited", "ltd", "pvt", "private",
    "india", "financial services", "finance", "capital",
    "group", "holdings", "company", "corp", "corporation"
]

def _normalize(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    for suffix in STRIP_SUFFIXES:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name.strip()

def _core_words(name: str) -> list:
    return [w for w in _normalize(name).split() if len(w) > 2]

def brand_matches(brand: str, text: str) -> bool:
    text_lower  = text.lower()
    brand_lower = brand.lower()
    if brand_lower in text_lower:
        return True
    brand_norm = _normalize(brand)
    if brand_norm and brand_norm in text_lower:
        return True
    core = _core_words(brand)
    if core and all(w in text_lower for w in core):
        return True
    if core and len(core[0]) >= 4 and core[0] in text_lower:
        return True
    parts = brand_lower.split()
    if len(parts) >= 2:
        abbr = "".join(p[0] for p in parts if len(p) > 1)
        if len(abbr) >= 2 and abbr in text_lower:
            return True
    return False

def find_brand_position(brand: str, text: str) -> int:
    text_lower  = text.lower()
    brand_lower = brand.lower()
    if brand_lower in text_lower:
        return text_lower.find(brand_lower)
    brand_norm = _normalize(brand)
    if brand_norm and brand_norm in text_lower:
        return text_lower.find(brand_norm)
    core = _core_words(brand)
    if core:
        for word in core:
            if word in text_lower:
                return text_lower.find(word)
    return -1

def extract_known_brands(response: str, all_brands: list) -> list:
    found = []
    for brand in all_brands:
        pos = find_brand_position(brand, response)
        if pos != -1:
            found.append((brand, pos))
    found.sort(key=lambda x: x[1])
    return [b for b, _ in found]