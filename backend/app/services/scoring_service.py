"""
AI Scoring Service — real semantic scoring using sentence-transformers.

Supports three question types:
  - MCQ:   exact match + semantic fallback
  - Short: semantic similarity + keyword coverage blend
  - Long:  sentence-level coverage + depth analysis
"""
import re
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

from app.services.embedding_engine import get_similarity

logger = logging.getLogger(__name__)

# Simple English stopwords (no NLTK needed)
_STOPWORDS = frozenset({
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "its",
    "they", "them", "their", "this", "that", "these", "those", "is", "am",
    "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "shall", "should", "may", "might", "can",
    "could", "a", "an", "the", "and", "but", "or", "nor", "not", "no", "so",
    "if", "then", "than", "too", "very", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "into", "about", "between", "through", "after",
    "before", "during", "above", "below", "up", "down", "out", "off", "over",
    "under", "again", "further", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "only", "own", "same", "just", "also",
    "how", "what", "which", "who", "whom", "when", "where", "why",
})


@dataclass
class ScoringResult:
    """Result object for a single answer scoring."""
    score: float
    confidence: float
    reasoning: str
    flagged_for_review: bool = False
    criteria_matched: Dict[str, Any] = None

    def __post_init__(self):
        if self.criteria_matched is None:
            self.criteria_matched = {}


def _extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """Extract top N meaningful words from text (no NLTK, simple split + filter)."""
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    keywords = [w for w in words if w not in _STOPWORDS]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:top_n]


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on . ? ! boundaries."""
    parts = re.split(r'[.?!]\s+', text.strip())
    return [s.strip() for s in parts if s.strip() and len(s.strip()) > 5]


class ScoringService:
    """AI-powered scoring using sentence-transformers for real semantic analysis."""

    @staticmethod
    def evaluate_mcq(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        negative_marking: float = 0.0,
    ) -> ScoringResult:
        """
        MCQ scoring:
        1. Exact match → full marks
        2. Semantic similarity fallback for text-based MCQs
        """
        s_norm = student_answer.strip().lower()
        m_norm = model_answer.strip().lower()

        if not s_norm:
            return ScoringResult(
                score=0.0,
                confidence=1.0,
                reasoning="No answer provided.",
            )

        # Exact match (case-insensitive)
        if s_norm == m_norm:
            return ScoringResult(
                score=max_marks,
                confidence=1.0,
                reasoning=f"Exact match: '{student_answer.strip()}' matches model answer.",
            )

        # Single-character option matching (A/B/C/D)
        s_char = s_norm[0] if len(s_norm) == 1 else None
        m_char = m_norm[0] if len(m_norm) <= 2 else None
        if s_char and m_char:
            if s_char == m_char:
                return ScoringResult(
                    score=max_marks,
                    confidence=1.0,
                    reasoning=f"Option match: '{s_char.upper()}' is correct.",
                )
            else:
                penalty = -abs(negative_marking) if negative_marking > 0 else 0.0
                return ScoringResult(
                    score=penalty,
                    confidence=1.0,
                    reasoning=f"Incorrect option: expected '{m_char.upper()}', got '{s_char.upper()}'.",
                )

        # Semantic similarity fallback for text-based MCQs
        similarity = get_similarity(s_norm, m_norm)

        if similarity >= 0.85:
            return ScoringResult(
                score=max_marks,
                confidence=0.95,
                reasoning=f"Near-exact semantic match ({similarity:.0%}). Full marks awarded.",
                criteria_matched={"semantic_similarity": round(similarity, 4)},
            )
        elif similarity >= 0.50:
            return ScoringResult(
                score=round(max_marks * 0.5, 2),
                confidence=round(similarity, 2),
                reasoning=f"Partial semantic match ({similarity:.0%}). Half marks awarded.",
                criteria_matched={"semantic_similarity": round(similarity, 4)},
            )
        else:
            penalty = -abs(negative_marking) if negative_marking > 0 else 0.0
            return ScoringResult(
                score=penalty,
                confidence=round(1.0 - similarity, 2),
                reasoning=f"Low semantic match ({similarity:.0%}). Answer does not match expected response.",
                criteria_matched={"semantic_similarity": round(similarity, 4)},
            )

    @staticmethod
    def evaluate_short_answer(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        keywords: List[str] = None,
    ) -> ScoringResult:
        """
        Short answer scoring:
        - 70% semantic similarity + 30% keyword coverage
        """
        if not student_answer or not student_answer.strip():
            return ScoringResult(
                score=0.0,
                confidence=1.0,
                reasoning="No answer provided.",
            )

        # Semantic similarity
        similarity = get_similarity(student_answer, model_answer)

        # Keyword extraction and coverage
        kw_list = keywords if keywords else _extract_keywords(model_answer, top_n=5)
        if not kw_list:
            kw_list = _extract_keywords(model_answer, top_n=5)

        student_lower = student_answer.lower()
        keyword_hits = sum(1 for kw in kw_list if kw.lower() in student_lower)
        keyword_coverage = keyword_hits / len(kw_list) if kw_list else 0.0

        # Blended score
        blended = (similarity * 0.7) + (keyword_coverage * 0.3)
        final_score = round(blended * max_marks, 2)
        final_score = max(0.0, min(final_score, max_marks))

        confidence = round(similarity, 2) if similarity > 0.5 else 0.3

        flagged = confidence < 0.5

        reasoning = (
            f"Semantic similarity: {similarity:.0%}. "
            f"Keyword coverage: {keyword_hits}/{len(kw_list)} ({keyword_coverage:.0%}). "
            f"Final blended score: {final_score}/{max_marks}."
        )

        return ScoringResult(
            score=final_score,
            confidence=confidence,
            reasoning=reasoning,
            flagged_for_review=flagged,
            criteria_matched={
                "semantic_similarity": round(similarity, 4),
                "keyword_hits": keyword_hits,
                "keyword_total": len(kw_list),
                "keyword_coverage": round(keyword_coverage, 4),
                "keywords_checked": kw_list,
            },
        )

    @staticmethod
    def evaluate_long_answer(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        rubrics: List[Dict[str, Any]] = None,
    ) -> ScoringResult:
        """
        Long answer scoring:
        - Sentence-level coverage matching (60%)
        - Depth/completeness ratio (40%)
        """
        if not student_answer or not student_answer.strip():
            return ScoringResult(
                score=0.0,
                confidence=1.0,
                reasoning="No answer provided. Score: 0.0.",
            )

        model_sentences = _split_sentences(model_answer)
        student_sentences = _split_sentences(student_answer)

        if not model_sentences:
            model_sentences = [model_answer.strip()]
        if not student_sentences:
            student_sentences = [student_answer.strip()]

        # For each model sentence, find best match in student answer
        best_matches = []
        for m_sent in model_sentences:
            best_sim = 0.0
            for s_sent in student_sentences:
                sim = get_similarity(m_sent, s_sent)
                if sim > best_sim:
                    best_sim = sim
            best_matches.append(best_sim)

        coverage_score = sum(best_matches) / len(best_matches) if best_matches else 0.0
        matched_count = sum(1 for s in best_matches if s >= 0.5)

        # Depth ratio
        depth_score = min(len(student_sentences) / len(model_sentences), 1.0)

        # Final score
        final_ratio = (coverage_score * 0.6) + (depth_score * 0.4)
        final_score = round(final_ratio * max_marks, 2)
        final_score = max(0.0, min(final_score, max_marks))

        confidence = round(coverage_score, 2)
        flagged = confidence < 0.65

        reasoning = (
            f"Coverage: {coverage_score:.0%} (matched {matched_count}/{len(model_sentences)} key points). "
            f"Depth ratio: {depth_score:.0%}. "
            f"Final: {final_score}/{max_marks}."
        )
        if flagged:
            reasoning += " [FLAGGED FOR REVIEW]"

        return ScoringResult(
            score=final_score,
            confidence=confidence,
            reasoning=reasoning,
            flagged_for_review=flagged,
            criteria_matched={
                "coverage_score": round(coverage_score, 4),
                "depth_score": round(depth_score, 4),
                "model_sentences": len(model_sentences),
                "student_sentences": len(student_sentences),
                "matched_key_points": matched_count,
                "per_sentence_scores": [round(s, 4) for s in best_matches],
            },
        )
