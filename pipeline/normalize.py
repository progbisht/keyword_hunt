import re
from typing import Dict, List, Set, Tuple
import numpy as np


def clean_term(term: str) -> str:
    """Lowercases, strips leading/trailing punctuation and extra whitespace."""
    text = term.lower().strip()
    # Strip bullet numbers like '1. ', '2)', etc.
    text = re.sub(r"^[0-9]+[\.\)\-]\s*", "", text)
    # Replace multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Strip enclosing quotes or trailing odd symbols
    text = text.strip("'\"` .,;:-!?")
    return text


def exact_dedupe(candidates_with_sources: Dict[str, Set[str]]) -> Dict[str, List[str]]:
    """
    Cleans strings and performs exact deduplication, combining sources.
    Returns dict mapping cleaned_term -> list of sorted source names.
    """
    deduped: Dict[str, Set[str]] = {}
    for raw_term, sources in candidates_with_sources.items():
        cleaned = clean_term(raw_term)
        if cleaned:
            if cleaned not in deduped:
                deduped[cleaned] = set()
            deduped[cleaned].update(sources)

    return {term: sorted(list(sources)) for term, sources in deduped.items()}


def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    normalized = embeddings / norms
    return np.dot(normalized, normalized.T)


def semantic_dedupe(
    candidates_with_sources: Dict[str, List[str]], threshold: float = 0.92
) -> Dict[str, List[str]]:
    """
    Merges semantically redundant keyword pairs with cosine similarity > threshold.
    Uses sentence-transformers if available, falling back to TF-IDF cosine similarity.
    """
    if len(candidates_with_sources) <= 1:
        return candidates_with_sources

    terms = list(candidates_with_sources.keys())
    embeddings = None

    # Try sentence-transformers first
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        embeddings = model.encode(terms, show_progress_bar=False, convert_to_numpy=True)
    except Exception:
        # Fallback to TF-IDF
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(ngram_range=(1, 3))
            embeddings = vectorizer.fit_transform(terms).toarray()
        except Exception:
            pass

    if embeddings is None:
        return candidates_with_sources

    sim_matrix = _cosine_similarity_matrix(embeddings)

    merged_sources: Dict[str, Set[str]] = {
        term: set(sources) for term, sources in candidates_with_sources.items()
    }
    eliminated: Set[int] = set()
    n = len(terms)

    for i in range(n):
        if i in eliminated:
            continue
        for j in range(i + 1, n):
            if j in eliminated:
                continue
            if sim_matrix[i, j] >= threshold:
                # Keep the longer / more explicit phrase as representative, or term i
                term_i, term_j = terms[i], terms[j]
                if len(term_j.split()) > len(term_i.split()):
                    # j becomes primary, absorb i
                    merged_sources[term_j].update(merged_sources[term_i])
                    eliminated.add(i)
                    break
                else:
                    # i remains primary, absorb j
                    merged_sources[term_i].update(merged_sources[term_j])
                    eliminated.add(j)

    result: Dict[str, List[str]] = {}
    for idx, term in enumerate(terms):
        if idx not in eliminated:
            result[term] = sorted(list(merged_sources[term]))

    return result


def normalize_and_dedupe(
    candidates_with_sources: Dict[str, Set[str]],
    semantic: bool = True,
    similarity_threshold: float = 0.92,
) -> Dict[str, List[str]]:
    """Step 5 Pipeline function."""
    exact_result = exact_dedupe(candidates_with_sources)
    if semantic:
        return semantic_dedupe(exact_result, threshold=similarity_threshold)
    return exact_result
