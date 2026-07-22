from typing import Dict, List, Tuple
import numpy as np
from models.keyword import KeywordItem


def classify_tail_type(word_count: int) -> str:
    """Rules from Section 1: short-tail 1-2 words, mid-tail 3-4 words, long-tail 5+ words."""
    if word_count <= 2:
        return "short-tail"
    elif word_count <= 4:
        return "mid-tail"
    else:
        return "long-tail"


def classify_intent(term: str) -> str:
    """Rule-based search intent classifier."""
    lower = term.lower().strip()

    # Informational question intent check (high priority for questions)
    info_prefixes = ("how ", "how to", "what ", "what is", "why ", "why does", "where ", "who ", "when ")
    if lower.startswith(info_prefixes) or lower.endswith("?"):
        return "informational"

    # Comparison intent
    comparison_signals = [" vs ", " versus ", "or ", "compare", "comparison", "alternative", "alternatives", " difference between "]
    if any(sig in lower for sig in comparison_signals) or lower.startswith("best "):
        return "comparison"

    # Transactional intent
    transactional_signals = ["buy", "order", "price", "pricing", "cost", "cheap", "coupon", "discount", "download", "hire", "sale"]
    words = lower.split()
    if any(sig in words for sig in transactional_signals):
        return "transactional"

    # Commercial intent
    commercial_signals = ["review", "reviews", "top", "software", "tool", "service", "app", "platform", "agency", "provider", "solution", "vendor"]
    if any(sig in lower for sig in commercial_signals):
        return "commercial"

    # Navigational intent
    navigational_signals = ["login", "log in", "sign in", "portal", "website", "official site", "account"]
    if any(sig in lower for sig in navigational_signals):
        return "navigational"

    # Default to informational
    return "informational"


def compute_relevance_scores(
    terms: List[str], seed_keyword: str
) -> Dict[str, float]:
    """
    Computes cosine similarity between each term's embedding and the seed keyword embedding.
    """
    all_texts = [seed_keyword] + terms
    scores: Dict[str, float] = {}

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        embeddings = model.encode(all_texts, show_progress_bar=False, convert_to_numpy=True)
        seed_emb = embeddings[0]
        term_embs = embeddings[1:]

        seed_norm = np.linalg.norm(seed_emb)
        if seed_norm > 0:
            seed_emb = seed_emb / seed_norm

        for idx, term in enumerate(terms):
            t_emb = term_embs[idx]
            t_norm = np.linalg.norm(t_emb)
            if t_norm > 0:
                t_emb = t_emb / t_norm
            score = float(np.dot(seed_emb, t_emb))
            scores[term] = round(max(0.0, min(1.0, score)), 3)

        return scores
    except Exception:
        pass

    # Fallback to TF-IDF cosine similarity
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(all_texts).toarray()
        seed_vec = matrix[0]
        seed_norm = np.linalg.norm(seed_vec)

        for idx, term in enumerate(terms):
            t_vec = matrix[1 + idx]
            t_norm = np.linalg.norm(t_vec)
            if seed_norm > 0 and t_norm > 0:
                sim = float(np.dot(seed_vec, t_vec) / (seed_norm * t_norm))
            else:
                sim = 0.5
            scores[term] = round(max(0.0, min(1.0, sim)), 3)

        return scores
    except Exception:
        # Heuristic fallback if ML libs fail
        for term in terms:
            seed_words = set(seed_keyword.lower().split())
            term_words = set(term.lower().split())
            overlap = len(seed_words.intersection(term_words))
            ratio = overlap / max(len(seed_words), 1)
            scores[term] = round(min(1.0, 0.4 + ratio * 0.6), 3)

        return scores


def classify_keywords(
    candidates_with_sources: Dict[str, List[str]],
    seed_keyword: str,
    min_relevance: float = 0.35,
) -> List[KeywordItem]:
    """Step 6 Pipeline function."""
    terms = list(candidates_with_sources.keys())
    if not terms:
        return []

    relevance_scores = compute_relevance_scores(terms, seed_keyword)

    classified_items: List[KeywordItem] = []

    for term, sources in candidates_with_sources.items():
        rel_score = relevance_scores.get(term, 0.5)

        # Drop keywords that fall below minimum relevance threshold
        if rel_score < min_relevance and seed_keyword.lower() not in term.lower():
            continue

        words = term.split()
        w_count = len(words)
        tail_type = classify_tail_type(w_count)
        intent = classify_intent(term)

        item = KeywordItem(
            term=term,
            type=tail_type,
            word_count=w_count,
            intent=intent,
            source=sources,
            volume=None,
            difficulty=None,
            relevance_score=rel_score,
        )
        classified_items.append(item)

    # Sort output by relevance score (descending) then word count
    classified_items.sort(key=lambda x: (x.relevance_score, x.word_count), reverse=True)
    return classified_items
