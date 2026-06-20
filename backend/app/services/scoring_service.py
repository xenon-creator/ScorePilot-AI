"""
ScorePilot AI V2 Grading Engine — Mark Scheme & Rubric Evaluator.

Features:
- Point-by-point marking scheme matching (CBSE/AQA-style).
- Rubric-based evaluation for subjective long answers.
- Dynamic Confidence Engine with contradiction and length penalties.
- Proactive Flagging System for uncertain or boundary scores.
- Seamless LLM Reviewer fallback integrations.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from app.services.embedding_engine import get_similarity
from app.services.llm_reviewer import review_answer_with_llm

logger = logging.getLogger(__name__)

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
    debug_output: Dict[str, Any] = None

    def __post_init__(self):
        if self.criteria_matched is None:
            self.criteria_matched = {}


def _extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """Extract top N meaningful words from text."""
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    keywords = [w for w in words if w not in _STOPWORDS]
    seen = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:top_n]


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on punctuation boundaries."""
    parts = re.split(r'[.?!]\s+', text.strip())
    return [s.strip() for s in parts if s.strip() and len(s.strip()) > 3]


def _detect_contradictions(student_answer: str, target_keywords: List[str]) -> bool:
    """
    Detects if negations like 'not', 'no', 'never', 'fail' are used in close proximity
    to target keywords inside the student answer.
    """
    negations = r"\b(not|no|never|cannot|cant|fails|doesnt|isnt|wasnt)\b"
    student_lower = student_answer.lower()
    for kw in target_keywords:
        kw_lower = kw.lower()
        if kw_lower in student_lower:
            # Check a window of 30 characters before the keyword for negations
            kw_index = student_lower.find(kw_lower)
            start_window = max(0, kw_index - 30)
            window = student_lower[start_window:kw_index]
            if re.search(negations, window):
                return True
    return False


def _parse_marking_scheme(marking_scheme: Any) -> Dict[str, Any] | None:
    """Safely parses a marking scheme from string or dict/list format."""
    if not marking_scheme:
        return None
    if isinstance(marking_scheme, dict):
        return marking_scheme
    if isinstance(marking_scheme, str):
        try:
            parsed = json.loads(marking_scheme)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


class ScoringService:
    """AI-powered scoring with point-by-point marking, rubrics, and LLM fallbacks."""

    @staticmethod
    def calculate_confidence(
        avg_similarity: float,
        marks_awarded: float,
        max_marks: float,
        student_words_count: int,
        model_words_count: int,
        contradiction_detected: bool,
        question_type: str
    ) -> float:
        """
        Confidence engine calculating score confidence from 0 to 100 based on similarity,
        matches, contradiction penalties, and length.
        """
        # Match ratio (0.0 to 1.0)
        match_ratio = (marks_awarded / max_marks) if max_marks > 0 else 1.0
        
        # Length ratio score (0.0 to 1.0)
        expected_len = max(1, int(model_words_count * 0.5))
        len_ratio = min(student_words_count / expected_len, 1.0)

        # Base Formula: 40% similarity, 40% matches, 20% length coverage
        confidence = (0.4 * avg_similarity * 100) + (0.4 * match_ratio * 100) + (0.2 * len_ratio * 100)

        # Apply Penalties
        if contradiction_detected:
            confidence -= 30.0  # High penalty for potential incorrect/negated answers
            
        if question_type == "long" and student_words_count < 15:
            confidence -= 25.0  # Essay length penalty
        elif question_type == "short" and student_words_count < 3:
            confidence -= 25.0  # Short length penalty

        return max(0.0, min(confidence, 100.0))

    @staticmethod
    def evaluate_mcq(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        negative_marking: float = 0.0,
    ) -> ScoringResult:
        """Grades MCQ questions with exact or semantic options matching."""
        s_norm = student_answer.strip().lower()
        m_norm = model_answer.strip().lower()

        if not s_norm:
            return ScoringResult(
                score=0.0,
                confidence=100.0,
                reasoning="No answer provided.",
            )

        # Exact match (case-insensitive)
        if s_norm == m_norm:
            return ScoringResult(
                score=max_marks,
                confidence=100.0,
                reasoning=f"Exact match: '{student_answer.strip()}' matches model answer.",
            )

        # Match option letters like "A", "B", "A.", "B)", "Option A"
        def extract_option_char(text: str) -> str | None:
            match = re.match(r'^(?:option\s+)?([a-d])(?:\b|[.)]|$)', text.strip())
            return match.group(1) if match else None

        s_char = extract_option_char(s_norm)
        m_char = extract_option_char(m_norm)

        if s_char and m_char:
            if s_char == m_char:
                return ScoringResult(
                    score=max_marks,
                    confidence=100.0,
                    reasoning=f"Option match: '{s_char.upper()}' is correct.",
                )
            else:
                penalty = -abs(negative_marking) if negative_marking > 0 else 0.0
                return ScoringResult(
                    score=penalty,
                    confidence=100.0,
                    reasoning=f"Incorrect option: expected '{m_char.upper()}', got '{s_char.upper()}'.",
                )

        # Semantic option description similarity fallback
        similarity = get_similarity(s_norm, m_norm)
        if similarity >= 0.85:
            return ScoringResult(
                score=max_marks,
                confidence=95.0,
                reasoning=f"Near-exact semantic option match ({similarity:.0%}). Full marks awarded.",
            )
        elif similarity >= 0.50:
            return ScoringResult(
                score=round(max_marks * 0.5, 2),
                confidence=round(similarity * 100, 1),
                reasoning=f"Partial semantic match ({similarity:.0%}). Half marks awarded.",
            )
        else:
            penalty = -abs(negative_marking) if negative_marking > 0 else 0.0
            return ScoringResult(
                score=penalty,
                confidence=round((1.0 - similarity) * 100, 1),
                reasoning=f"Low semantic match ({similarity:.0%}). Answer is incorrect.",
            )

    @staticmethod
    def evaluate_short_answer(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        marking_scheme: Dict[str, Any] | None = None
    ) -> ScoringResult:
        """Point-by-point marking scheme evaluations for CBSE/AQA short answers."""
        # Check 1: Verify student_answer before grading
        logger.info(f"student_answer: {student_answer}")
        print(f"student_answer: {student_answer}")

        student_sentences = _split_sentences(student_answer)
        if not student_sentences:
            student_sentences = [student_answer.strip()]

        # 1. Parse or generate marking points list
        scheme = _parse_marking_scheme(marking_scheme)
        marking_points = []
        if scheme and "marking_points" in scheme:
            marking_points = scheme["marking_points"]
        else:
            # Auto-generate marking points from model answer sentences
            model_sents = _split_sentences(model_answer)
            if not model_sents:
                model_sents = [model_answer.strip()]
            share = max_marks / len(model_sents)
            for i, sent in enumerate(model_sents):
                marking_points.append({
                    "id": i + 1,
                    "point": sent,
                    "marks": round(share, 2)
                })

        # Check 2: Verify marking points loaded before scoring
        logger.info(f"marking_points: {marking_points}")
        print(f"marking_points: {marking_points}")

        # 2. Evaluate each marking point independently
        score_awarded = 0.0
        matched_points = []
        missing_points = []
        similarities = []
        contradiction_flag = False

        for mp in marking_points:
            mp_text = mp.get("point", "")
            mp_marks = float(mp.get("marks", 1.0))
            best_sim = 0.0
            
            for s_sent in student_sentences:
                sim = get_similarity(mp_text, s_sent)
                if sim > best_sim:
                    best_sim = sim

            similarities.append(best_sim)
            
            # Check 4: Verify cosine similarity values for every marking point
            sim_data = {"point": mp_text, "similarity": round(best_sim, 2)}
            print(json.dumps(sim_data, indent=2))
            logger.info(f"Cosine similarity: {sim_data}")

            keywords = _extract_keywords(mp_text, top_n=3)
            
            # Check for negation/contradiction of this point's keywords
            if _detect_contradictions(student_answer, keywords):
                contradiction_flag = True

            # Check 5: Verify thresholds: >=0.75 full, 0.55 - 0.75 partial, < 0.55 missing
            if best_sim >= 0.75:
                score_awarded += mp_marks
                matched_points.append(mp_text)
            elif best_sim >= 0.55:
                score_awarded += round(mp_marks * 0.5, 2)
                matched_points.append(f"{mp_text} (Partial)")
            else:
                missing_points.append(mp_text)

        # Check 6: Verify score calculation
        raw_score = score_awarded
        score_awarded = max(0.0, min(score_awarded, max_marks))
        print(f"Score calculation - Raw: {raw_score}, Capped: {score_awarded}")
        logger.info(f"Score calculation - Raw: {raw_score}, Capped: {score_awarded}")

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

        # Calculate confidence
        student_words = len(student_answer.split())
        model_words = len(model_answer.split())
        confidence = ScoringService.calculate_confidence(
            avg_similarity=avg_similarity,
            marks_awarded=score_awarded,
            max_marks=max_marks,
            student_words_count=student_words,
            model_words_count=model_words,
            contradiction_detected=contradiction_flag,
            question_type="short"
        )
        
        # Check 7: Verify confidence calculation (0 <= confidence <= 100)
        confidence = max(0.0, min(confidence, 100.0))
        print(f"Confidence calculation: {confidence}")
        logger.info(f"Confidence calculation: {confidence}")

        reasoning = (
            f"Awarded {score_awarded}/{max_marks} marks based on mark scheme. "
            f"Matched {len(matched_points)}/{len(marking_points)} grading criteria points. "
            f"Average points similarity: {avg_similarity:.0%}."
        )

        flagged = confidence < 70.0 or contradiction_flag or student_words < 3

        # Check 8: Return debugging output dictionary
        debug_dict = {
            "student_answer": student_answer,
            "marking_points": [mp.get("point", "") for mp in marking_points],
            "similarities": [round(s, 2) for s in similarities],
            "matched_points": matched_points,
            "missing_points": missing_points,
            "score": score_awarded,
            "confidence": confidence
        }

        return ScoringResult(
            score=score_awarded,
            confidence=confidence,
            reasoning=reasoning,
            flagged_for_review=flagged,
            criteria_matched={
                "matched_points": matched_points,
                "missing_points": missing_points,
                "contradiction_detected": contradiction_flag,
                "average_similarity": avg_similarity,
                "debug_output": debug_dict
            },
            debug_output=debug_dict
        )

    @staticmethod
    def evaluate_long_answer(
        student_answer: str,
        model_answer: str,
        max_marks: float,
        marking_scheme: Dict[str, Any] | None = None
    ) -> ScoringResult:
        # Check 1: Verify OCR output is not empty
        logger.info(f"student_answer: {student_answer}")
        print(f"student_answer: {student_answer}")

        model_sentences = _split_sentences(model_answer)
        if not model_sentences:
            model_sentences = [model_answer.strip()]

        if not student_answer or not student_answer.strip():
            debug_dict = {
                "student_answer": student_answer or "",
                "marking_points": model_sentences,
                "similarities": [0.0] * len(model_sentences),
                "matched_points": [],
                "missing_points": model_sentences,
                "score": 0.0,
                "confidence": 100.0
            }
            return ScoringResult(
                score=0.0,
                confidence=100.0,
                reasoning="No answer provided.",
                flagged_for_review=True,
                criteria_matched={
                    "matched_points": [],
                    "missing_points": model_sentences,
                    "contradiction_detected": False,
                    "debug_output": debug_dict
                },
                debug_output=debug_dict
            )

        student_sentences = _split_sentences(student_answer)
        if not student_sentences:
            student_sentences = [student_answer.strip()]

        # Check 2: Verify mark scheme points are loaded
        logger.info(f"marking_points (model sentences): {model_sentences}")
        print(f"marking_points (model sentences): {model_sentences}")

        # 1. Rubric evaluations (Coverage, Accuracy, Depth, Examples, Structure)
        # Coverage: keyword overlap ratio
        model_kws = _extract_keywords(model_answer, top_n=10)
        student_lower = student_answer.lower()
        matched_kws = [kw for kw in model_kws if kw.lower() in student_lower]
        coverage_ratio = len(matched_kws) / len(model_kws) if model_kws else 1.0
        coverage_score = round(min(coverage_ratio * 2.0, 2.0), 2)

        # Accuracy: check negations in matched keywords
        contradiction_detected = _detect_contradictions(student_answer, matched_kws)
        accuracy_score = 0.5 if contradiction_detected else 2.0

        # Depth: sentence count completeness ratio
        depth_ratio = min(len(student_sentences) / len(model_sentences), 1.0)
        depth_score = round(depth_ratio * 2.0, 2)

        # Examples: check illustrations ("e.g.", "for example", "such as")
        example_markers = [r"\bexample(s)?\b", r"\be\.g\.\b", r"\bsuch as\b", r"\bfor instance\b", r"\billustrat(e|ion)\b"]
        has_example = any(re.search(pat, student_lower) for pat in example_markers)
        examples_score = 2.0 if has_example else 0.5

        # Structure: check transitions ("therefore", "however", "consequently", "finally")
        transition_markers = [r"\btherefore\b", r"\bhowever\b", r"\bconsequently\b", r"\bfinally\b", r"\bfurthermore\b", r"\bsecondly\b"]
        transition_hits = sum(1 for pat in transition_markers if re.search(pat, student_lower))
        structure_score = round(min((transition_hits / 3) * 2.0, 2.0), 2)

        rubric_totals = coverage_score + accuracy_score + depth_score + examples_score + structure_score
        
        # Scale to max marks (rubric totals are out of 10 max points)
        score_awarded = round((rubric_totals / 10.0) * max_marks, 2)
        score_awarded = max(0.0, min(score_awarded, max_marks))

        # Check sentence similarities for confidence avg
        best_similarities = []
        for m_sent in model_sentences:
            best_sim = 0.0
            for s_sent in student_sentences:
                sim = get_similarity(m_sent, s_sent)
                if sim > best_sim:
                    best_sim = sim
            best_similarities.append(best_sim)
            
            # Check 4: Verify cosine similarity values for every marking point
            sim_data = {"point": m_sent, "similarity": round(best_sim, 2)}
            print(json.dumps(sim_data, indent=2))
            logger.info(f"Cosine similarity: {sim_data}")

        avg_similarity = sum(best_similarities) / len(best_similarities) if best_similarities else 0.0

        # Calculate confidence
        student_words = len(student_answer.split())
        model_words = len(model_answer.split())
        confidence = ScoringService.calculate_confidence(
            avg_similarity=avg_similarity,
            marks_awarded=score_awarded,
            max_marks=max_marks,
            student_words_count=student_words,
            model_words_count=model_words,
            contradiction_detected=contradiction_detected,
            question_type="long"
        )

        reasoning = (
            f"Long Answer rubric score: {score_awarded}/{max_marks} (Coverage: {coverage_score}/2, "
            f"Accuracy: {accuracy_score}/2, Depth: {depth_score}/2, Examples: {examples_score}/2, "
            f"Structure: {structure_score}/2)."
        )

        # Check 5: Verify thresholds: >=0.75 full, 0.55 - 0.75 partial, < 0.55 missing
        matched_points = []
        missing_points = []
        for idx, m_sent in enumerate(model_sentences):
            if idx < len(best_similarities):
                best_sim = best_similarities[idx]
                if best_sim >= 0.75:
                    matched_points.append(m_sent)
                elif best_sim >= 0.55:
                    matched_points.append(f"{m_sent} (Partial)")
                else:
                    missing_points.append(m_sent)

        # Check 7: Verify confidence calculation (0 <= confidence <= 100)
        confidence = max(0.0, min(confidence, 100.0))
        print(f"Confidence calculation: {confidence}")
        logger.info(f"Confidence calculation: {confidence}")

        flagged = confidence < 70.0 or contradiction_detected or student_words < 15

        # Check 8: Return debugging output dictionary
        debug_dict = {
            "student_answer": student_answer,
            "marking_points": model_sentences,
            "similarities": [round(s, 2) for s in best_similarities],
            "matched_points": matched_points,
            "missing_points": missing_points,
            "score": score_awarded,
            "confidence": confidence
        }

        # Check 6: Verify score calculation
        print(f"Score calculation - Raw: {rubric_totals / 10.0 * max_marks}, Capped: {score_awarded}")
        logger.info(f"Score calculation - Raw: {rubric_totals / 10.0 * max_marks}, Capped: {score_awarded}")

        return ScoringResult(
            score=score_awarded,
            confidence=confidence,
            reasoning=reasoning,
            flagged_for_review=flagged,
            criteria_matched={
                "matched_points": matched_points,
                "missing_points": missing_points,
                "rubric_evaluation": {
                    "coverage": coverage_score,
                    "accuracy": accuracy_score,
                    "depth": depth_score,
                    "examples": examples_score,
                    "structure": structure_score
                },
                "contradiction_detected": contradiction_detected,
                "debug_output": debug_dict
            },
            debug_output=debug_dict
        )


def score_answer(
    student_answer: str,
    model_answer: str,
    question_type: str,
    max_marks: float,
    marking_scheme: Any = None,
    question_text: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for V2 grading. Computes rule-based score, calculates confidence,
    and fallback-triggers LLM review for uncertain or boundary evaluations.
    """
    # 1. Run Initial Rule-Based / Sentence-Transformer Scorer
    if question_type == "mcq":
        res = ScoringService.evaluate_mcq(student_answer, model_answer, max_marks)
    elif question_type == "short":
        res = ScoringService.evaluate_short_answer(student_answer, model_answer, max_marks, marking_scheme)
    else:
        res = ScoringService.evaluate_long_answer(student_answer, model_answer, max_marks, marking_scheme)

    score = res.score
    confidence = res.confidence
    reasoning = res.reasoning
    flagged = res.flagged_for_review
    evaluation_metadata = res.criteria_matched or {}
    evaluation_metadata["llm_reviewed"] = False

    # 2. Flagging check
    # Check boundary scores (within 5% of 0 or max_marks)
    is_boundary = False
    if max_marks > 0:
        ratio = score / max_marks
        if ratio <= 0.05 or ratio >= 0.95:
            is_boundary = True

    words_count = len((student_answer or "").split())
    is_very_short = False
    if question_type == "long" and words_count < 15:
        is_very_short = True
    elif question_type == "short" and words_count < 3:
        is_very_short = True

    # Force flagging when confidence is low
    if confidence < 70.0 or evaluation_metadata.get("contradiction_detected") or is_very_short:
        flagged = True

    # 3. LLM Fallback triggers if:
    # - Confidence < 70
    # - OR Score is near a boundary and confidence is not 100
    # - OR contradictions detected
    need_llm_review = (
        confidence < 70.0 or
        (is_boundary and confidence < 95.0) or
        evaluation_metadata.get("contradiction_detected", False)
    )

    if need_llm_review:
        # Avoid running API loops during offline testing
        # Only run LLM if a key/token is present in environment
        llm_key = os.getenv("LLM_API_KEY") or os.getenv("HF_TOKEN") or os.getenv("HF_API_KEY")
        is_testing = os.getenv("TESTING", "false").lower() in ("true", "1", "yes")
        if llm_key and not is_testing:
            logger.info("Confidence threshold breached. Activating LLM Reviewer...")
            parsed_scheme = _parse_marking_scheme(marking_scheme)
            llm_result = review_answer_with_llm(
                question=question_text or f"Explain the question related to model answer: {model_answer[:100]}...",
                model_answer=model_answer,
                marking_scheme=parsed_scheme,
                student_answer=student_answer,
                max_marks=max_marks,
                question_type=question_type
            )
            
            if llm_result:
                score = llm_result["score"]
                confidence = llm_result["confidence"]
                reasoning = llm_result["reasoning"] + " (LLM Reviewed)"
                evaluation_metadata = {
                    "matched_points": llm_result["matched_points"],
                    "missing_points": llm_result["missing_points"],
                    "rubric_evaluation": llm_result["rubric_evaluation"],
                    "llm_reviewed": True,
                    "contradiction_detected": evaluation_metadata.get("contradiction_detected", False)
                }
                # Create debug output for LLM review path
                debug_dict = {
                    "student_answer": student_answer,
                    "marking_points": list(llm_result["matched_points"]) + list(llm_result["missing_points"]),
                    "similarities": [],
                    "matched_points": llm_result["matched_points"],
                    "missing_points": llm_result["missing_points"],
                    "score": score,
                    "confidence": confidence
                }
                evaluation_metadata["debug_output"] = debug_dict
                # If LLM confidence is still low, keep flagged
                flagged = confidence < 70.0 or flagged

    debug_val = evaluation_metadata.get("debug_output") or (res.debug_output if hasattr(res, "debug_output") else None)
    return {
        "score": score,
        "confidence": confidence,
        "reasoning": reasoning,
        "flagged_for_review": flagged,
        "evaluation_metadata": evaluation_metadata,
        "debug_output": debug_val
    }
