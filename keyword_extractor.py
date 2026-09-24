import json
import os
import re
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from config import OUTPUTS_PATH

nlp = spacy.load("en_core_web_sm")

NOISE_WORDS = {
    "add","cart","shop","order","payment","payments","fraud","alert",
    "click","subscribe","newsletter","login","signup","account","address",
    "checkout","coupon","discount","sale","cod","delivery","return",
    "refund","copyright","wishlist","track","cancel","pin","mobile",
    "email","password","proceed","apply","remove","update","continue",
    "home","page","menu","search","filter","sort","view","load","share",
    "follow","contact","support","help","faq","about","career","press",
    "rating","star","sold","stock","color","size","quantity","total",
    "subtotal","shipping","cash","arrival","arrivals","ball",
    "all","any","get","check","know","find","explore","discover",
    "browse","read","see","look","want","need","try","make","take",
    "give","keep","set","put","come","go","work","tell","show","let",
    "think","use","new","good","best","http","www","com",
    "alcohol","adventure","drug","drugs","tobacco","smoke",
    "beer","wine","party","club","fun","game","play","sport","gym",
    "food","recipe","cook","diet","weight","fitness","travel","trip",
    "irdai","irda","cin","llpin","grievance","redressal","regulator",
    "registered","registration","ombudsman","prospectus","disclaimer",
    "advertisement","statutory","ckyc","fatca","aml","kyc","pml",
    "fema","sebi","amfi","gstin","pan","llp","plc","pvt","ltd",
    "january","february","march","april","may","june","july","august",
    "september","october","november","december","monday","tuesday",
    "wednesday","thursday","friday","saturday","sunday","today",
    "tomorrow","yesterday","week","month","year","annual","quarterly",
    "one","two","three","four","five","six","seven","eight","nine","ten",
    "first","second","third","fourth","fifth",
    "company","business","service","services","product","products",
    "brand","brands","option","options","choice","choices","solution",
    "solutions","offer","offers","deal","deals","scheme","schemes",
}

def _clean(text: str) -> str:
    text = re.sub(r'#{1,6}\s*', ' ', text)
    text = re.sub(r'\[.*?\]\(.*?\)', ' ', text)
    text = re.sub(r'[₹\$][\d,\.]+', ' ', text)
    text = re.sub(r'[a-f0-9\-]{15,}', ' ', text)
    text = re.sub(r'http\S+', ' ', text)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    text = re.sub(r'\b\w{1,3}\b', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _valid(phrase: str) -> bool:
    words = phrase.lower().split()
    if not phrase.replace(" ","").isalpha():
        return False
    if len(words) > 3:
        return False
    if len(words) == 1 and len(phrase) < 5:
        return False
    if any(w in NOISE_WORDS for w in words):
        return False
    return True

def extract_keywords(text: str, brand_name: str) -> list:
    """
    Extract keywords sorted by TF-IDF importance score.
    Returns up to 200 keywords (increased from 60).
    """
    cleaned = _clean(text)
    doc     = nlp(cleaned[:100000])

    # collect noun/propn tokens and phrases
    candidates = set()
    for token in doc:
        if (token.pos_ in ("NOUN","PROPN")
                and token.is_alpha
                and len(token.text) > 4
                and token.lemma_.lower() not in NOISE_WORDS
                and brand_name.lower() not in token.lemma_.lower()):
            candidates.add(token.lemma_.lower())

    for chunk in doc.noun_chunks:
        phrase = chunk.text.lower().strip()
        if _valid(phrase) and brand_name.lower() not in phrase:
            candidates.add(phrase)

    # TF-IDF scoring — sorted by importance
    sentences    = [s.strip() for s in cleaned.split(".") if len(s.strip()) > 20]
    tfidf_scored = {}
    if sentences:
        try:
            vec = TfidfVectorizer(
                max_features=500, ngram_range=(1,3),
                stop_words="english", min_df=1
            )
            tfidf_matrix = vec.fit_transform(sentences)
            feature_names= vec.get_feature_names_out()
            # get mean TF-IDF score per term
            import numpy as np
            mean_scores  = tfidf_matrix.mean(axis=0).A1
            for term, score in zip(feature_names, mean_scores):
                if _valid(term) and brand_name.lower() not in term:
                    tfidf_scored[term] = score
        except Exception:
            pass

    # combine: all candidates with their TF-IDF score
    all_keywords = {}
    for kw in candidates:
        all_keywords[kw] = tfidf_scored.get(kw, 0.001)
    for kw, score in tfidf_scored.items():
        if kw not in all_keywords:
            all_keywords[kw] = score

    # sort by TF-IDF score (most important first)
    sorted_kws = sorted(all_keywords.items(), key=lambda x: x[1], reverse=True)
    keywords   = [kw for kw, _ in sorted_kws[:200]]  # return top 200

    print(f"  Extracted {len(keywords)} keywords for {brand_name}")
    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    return keywords