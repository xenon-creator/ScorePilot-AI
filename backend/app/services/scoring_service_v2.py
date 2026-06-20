import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple

from app.services.embedding_engine import get_similarity
from app.services.dataset_service import DatasetService
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

# Import the Dataset Engine structurer dynamically by appending its parent to path
try:
    from dataset.scorepilot.mark_scheme_structurer import MarkSchemeStructurer
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from dataset.scorepilot.mark_scheme_structurer import MarkSchemeStructurer

def _split_sentences(text: str) -> List[str]:
    """Helper to split text into sentences."""
    parts = re.split(r'[.?!]\s+', text.strip())
    return [s.strip() for s in parts if s.strip() and len(s.strip()) > 3]

def score_answer_v2(
    student_answer: str,
    question_text: str,
    model_answer: str,
    max_marks: float,
    marking_scheme: Any = None,
    question_id: str = None
) -> Dict[str, Any]:
    """
    Grades student answers using structured marking points from the Dataset Engine.
    Uses sentence-level similarity embeddings to compare marking points.
    """
    # Check 1: Verify OCR/extracted student answer before grading
    logger.info(f"student_answer: {student_answer}")
    print(f"student_answer: {student_answer}")

    if not student_answer or not student_answer.strip():
        return {
            "score": 0.0,
            "max_marks": max_marks,
            "matched_points": [],
            "partial_points": [],
            "missing_points": [],
            "confidence": 100.0,
            "feedback": "No answer provided.",
            "reasoning": "No answer provided.",
            "flagged_for_review": True,
            "evaluation_metadata": {"matched_points": [], "missing_points": []}
        }

    # 1. Resolve structured marking points
    marking_points = []
    
    # Try finding question in dataset first
    dataset_q = None
    if question_id:
        dataset_q = DatasetService.get_question(question_id)
    if not dataset_q and question_text:
        dataset_q = DatasetService.find_similar_question(question_text, threshold=0.85)

    if dataset_q and dataset_q.get("marking_points"):
        logger.info(f"Loaded structured marking scheme from Dataset Engine for: {dataset_q.get('question_id')}")
        marking_points = dataset_q["marking_points"]
    else:
        # Fall back to Question DB marking scheme
        parsed_scheme = None
        if marking_scheme:
            if isinstance(marking_scheme, dict):
                parsed_scheme = marking_scheme
            elif isinstance(marking_scheme, str):
                try:
                    parsed_scheme = json.loads(marking_scheme)
                except Exception:
                    pass
                    
        if parsed_scheme and "marking_points" in parsed_scheme:
            marking_points = parsed_scheme["marking_points"]
        elif model_answer:
            # Fall back to structuring model_answer using Dataset Engine structurer on-the-fly
            try:
                # Only try LLM structuring if OpenAI key is present
                if os.environ.get("OPENAI_API_KEY"):
                    logger.info("Structuring raw model answer on-the-fly using MarkSchemeStructurer.")
                    structurer = MarkSchemeStructurer()
                    res = structurer.structure(model_answer)
                    if res and "marking_points" in res:
                        marking_points = res["marking_points"]
            except Exception as e:
                logger.warning(f"On-the-fly structuring failed: {e}")

            if not marking_points:
                # Direct sentence split fallback
                logger.info("Falling back to sentence splitting of model answer.")
                sentences = _split_sentences(model_answer)
                if not sentences:
                    sentences = [model_answer.strip()]
                share = max_marks / len(sentences)
                for i, sent in enumerate(sentences):
                    marking_points.append({
                        "point": sent,
                        "marks": round(share, 2)
                    })

    # Check 2: Verify marking points loaded before scoring
    logger.info(f"marking_points: {marking_points}")
    print(f"marking_points: {marking_points}")

    # 2. Perform point-by-point semantic comparisons
    student_sentences = _split_sentences(student_answer)
    if not student_sentences:
        student_sentences = [student_answer.strip()]

    score_awarded = 0.0
    matched_pts = []
    partial_pts = []
    missing_pts = []
    similarities = []

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
        
        # Check 5: Verify thresholds: >= 0.75 full, 0.55 - 0.75 partial, < 0.55 missing
        if best_sim >= 0.75:
            score_awarded += mp_marks
            matched_pts.append(mp_text)
        elif best_sim >= 0.55:
            score_awarded += round(mp_marks * 0.5, 2)
            partial_pts.append(mp_text)
        else:
            missing_pts.append(mp_text)

    # Check 6: Verify score calculation
    raw_score = score_awarded
    score_awarded = max(0.0, min(round(score_awarded, 2), max_marks))
    print(f"Score calculation - Raw: {raw_score}, Capped: {score_awarded}")
    logger.info(f"Score calculation - Raw: {raw_score}, Capped: {score_awarded}")

    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

    # 3. Calculate confidence and compile feedback
    match_ratio = (score_awarded / max_marks) if max_marks > 0 else 1.0
    student_words = len(student_answer.split())
    expected_words = max(1, int(len(model_answer.split()) * 0.5)) if model_answer else 10
    len_ratio = min(student_words / expected_words, 1.0)
    
    confidence = (0.4 * avg_similarity * 100) + (0.4 * match_ratio * 100) + (0.2 * len_ratio * 100)
    
    # Check 7: Verify confidence calculation (0 <= confidence <= 100)
    confidence = max(0.0, min(round(confidence, 1), 100.0))
    print(f"Confidence calculation: {confidence}")
    logger.info(f"Confidence calculation: {confidence}")

    feedback_parts = []
    if score_awarded == max_marks:
        feedback_parts.append("Perfect score. All marking points successfully addressed.")
    else:
        feedback_parts.append(f"Awarded {score_awarded}/{max_marks} marks.")
        
    if matched_pts:
        matched_str = ", ".join(f'"{p}"' for p in matched_pts)
        feedback_parts.append(f"Matched points: {matched_str}.")
    if partial_pts:
        partial_str = ", ".join(f'"{p}"' for p in partial_pts)
        feedback_parts.append(f"Partially matched: {partial_str}.")
    if missing_pts:
        missing_str = ", ".join(f'"{p}"' for p in missing_pts)
        feedback_parts.append(f"Missing criteria: {missing_str}.")

    feedback = " ".join(feedback_parts)

    # Check 8: Return debugging output dictionary
    debug_dict = {
        "student_answer": student_answer,
        "marking_points": [mp.get("point", "") for mp in marking_points],
        "similarities": [round(s, 2) for s in similarities],
        "matched_points": matched_pts,
        "missing_points": missing_pts,
        "score": score_awarded,
        "confidence": confidence
    }

    return {
        "score": score_awarded,
        "max_marks": max_marks,
        "matched_points": matched_pts,
        "partial_points": partial_pts,
        "missing_points": missing_pts,
        "confidence": confidence,
        "feedback": feedback,
        "debug_output": debug_dict,
        
        # Compatibility keys for existing ScorePilot V1 pipelines
        "reasoning": feedback,
        "flagged_for_review": confidence < 70.0,
        "evaluation_metadata": {
            "matched_points": matched_pts,
            "partial_points": partial_pts,
            "missing_points": missing_pts,
            "confidence": confidence,
            "feedback": feedback,
            "debug_output": debug_dict
        }
    }


def score_answer(
    student_answer: str,
    model_answer: str,
    question_type: str,
    max_marks: float,
    marking_scheme: Any = None,
    question_text: str = "",
    question_id: str = None
) -> Dict[str, Any]:
    """
    Unified entry point for grading.
    Routes to V2 engine (point-by-point / dataset structured) or V1 engine (semantic similarity)
    based on USE_V2_GRADING environment variable/setting.
    """
    from app.core.config import settings

    if settings.USE_V2_GRADING:
        # V2 grading engine path
        if question_type == "mcq":
            res = ScoringService.evaluate_mcq(student_answer, model_answer, max_marks)
            return {
                "score": res.score,
                "max_marks": max_marks,
                "matched_points": [],
                "partial_points": [],
                "missing_points": [],
                "confidence": res.confidence,
                "feedback": res.reasoning,
                "reasoning": res.reasoning,
                "flagged_for_review": res.flagged_for_review,
                "evaluation_metadata": res.criteria_matched or {},
                "debug_output": res.debug_output if hasattr(res, "debug_output") else None
            }
        
        return score_answer_v2(
            student_answer=student_answer,
            question_text=question_text,
            model_answer=model_answer,
            max_marks=max_marks,
            marking_scheme=marking_scheme,
            question_id=question_id
        )
    else:
        # V1 grading engine path
        # Import dynamically to avoid circular references
        from app.services.scoring_service import score_answer as v1_score_answer
        return v1_score_answer(
            student_answer=student_answer,
            model_answer=model_answer,
            question_type=question_type,
            max_marks=max_marks,
            marking_scheme=marking_scheme,
            question_text=question_text
        )
