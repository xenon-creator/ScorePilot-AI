"""
Embedding engine: loads sentence-transformers model once at startup,
exposes cosine similarity functions for the scoring pipeline.

If the model fails to load (e.g. no internet on first deploy, missing
dependencies), scoring gracefully falls back to keyword-based similarity
instead of crashing.
"""
import os
import re
import time
import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Set model cache directory
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "models"))
os.environ["SENTENCE_TRANSFORMERS_HOME"] = os.path.abspath(MODEL_CACHE_DIR)
# Allow downloading the model on first run (don't set HF_HUB_OFFLINE)

# Module-level singleton — loaded once on first import
_model = None
_model_load_attempted = False
_model_load_failed = False

MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model():
    """Load model on first call, cache for all subsequent calls."""
    global _model, _model_load_attempted, _model_load_failed
    if _model is not None:
        return _model
    if _model_load_failed:
        return None

    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading sentence-transformer model '{MODEL_NAME}'...")
        start = time.time()
        _model = SentenceTransformer(MODEL_NAME)
        elapsed = round(time.time() - start, 2)
        logger.info(f"Model '{MODEL_NAME}' loaded in {elapsed}s")
        return _model
    except Exception as e:
        logger.error(f"Failed to load sentence-transformer model: {e}")
        _model_load_failed = True
        return None


def _keyword_fallback_similarity(text_a: str, text_b: str) -> float:
    """Simple keyword overlap similarity when the ML model is unavailable."""
    words_a = set(re.findall(r'[a-zA-Z]{3,}', text_a.lower()))
    words_b = set(re.findall(r'[a-zA-Z]{3,}', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def get_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two texts.
    Returns a float between 0.0 and 1.0.
    Returns 0.0 if either input is empty.
    Falls back to keyword overlap if the ML model is unavailable.
    """
    if not text_a or not text_a.strip() or not text_b or not text_b.strip():
        return 0.0

    model = _load_model()
    if model is None:
        # Fallback: keyword overlap similarity
        logger.warning("Using keyword fallback similarity (ML model unavailable)")
        return _keyword_fallback_similarity(text_a, text_b)

    embeddings = model.encode([text_a.strip(), text_b.strip()], convert_to_numpy=True)

    # Cosine similarity
    a, b = embeddings[0], embeddings[1]
    dot = float(np.dot(a, b))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm == 0:
        return 0.0

    sim = dot / norm
    return max(0.0, min(float(sim), 1.0))


def get_batch_similarity(pairs: List[Tuple[str, str]]) -> List[float]:
    """
    Compute cosine similarities for multiple (text_a, text_b) pairs in one batch.
    Returns list of floats between 0.0 and 1.0.
    Falls back to keyword overlap if the ML model is unavailable.
    """
    if not pairs:
        return []

    model = _load_model()
    if model is None:
        # Fallback: keyword overlap for each pair
        return [_keyword_fallback_similarity(a or "", b or "") for a, b in pairs]

    # Separate texts, encoding all at once for efficiency
    all_a = [p[0].strip() if p[0] else "" for p in pairs]
    all_b = [p[1].strip() if p[1] else "" for p in pairs]

    # Encode in a single batch
    all_texts = all_a + all_b
    embeddings = model.encode(all_texts, convert_to_numpy=True, batch_size=64)

    n = len(pairs)
    emb_a = embeddings[:n]
    emb_b = embeddings[n:]

    results = []
    for i in range(n):
        if not all_a[i] or not all_b[i]:
            results.append(0.0)
            continue
        a, b = emb_a[i], emb_b[i]
        dot = float(np.dot(a, b))
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        if norm == 0:
            results.append(0.0)
        else:
            results.append(max(0.0, min(float(dot / norm), 1.0)))

    return results
