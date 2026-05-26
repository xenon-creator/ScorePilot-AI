import pytest
from app.services.scoring_service import ScoringService

def test_mcq_scorer_correct():
    result = ScoringService.evaluate_mcq(
        student_answer="A",
        model_answer="A",
        max_marks=2.0
    )
    assert result["is_correct"] is True
    assert result["score"] == 2.0
    assert result["confidence"] == 1.0

def test_mcq_scorer_incorrect():
    result = ScoringService.evaluate_mcq(
        student_answer="B",
        model_answer="A",
        max_marks=2.0,
        negative_marking=0.25
    )
    assert result["is_correct"] is False
    assert result["score"] == -0.25

def test_semantic_similarity_overlap():
    sim_exact = ScoringService.calculate_semantic_similarity(
        "Mitochondria is the powerhouse of the cell.",
        "Mitochondria is the powerhouse of the cell."
    )
    assert sim_exact == 1.0

    sim_partial = ScoringService.calculate_semantic_similarity(
        "Mitochondria generates ATP power inside cells.",
        "Mitochondria generates energy through cellular respiration."
    )
    assert 0.3 < sim_partial < 0.9

def test_short_answer_evaluator():
    result = ScoringService.evaluate_short_answer(
        student_answer="Mitochondria makes ATP during cellular respiration.",
        model_answer="Mitochondria generates ATP through cellular respiration in double membranes.",
        max_marks=6.0,
        keywords=["ATP", "respiration", "mitochondria"]
    )
    assert result["score"] > 3.0
    assert len(result["criteria_matched"]["matched_keywords"]) >= 2
    assert "mitochondria" in result["criteria_matched"]["matched_keywords"]

def test_long_answer_rubric_weighting():
    rubrics = [
        {"criterion": "Light reactions", "weight": 0.5, "keywords": ["light", "thylakoid", "oxygen"]},
        {"criterion": "Calvin cycle", "weight": 0.5, "keywords": ["dark", "stroma", "glucose"]}
    ]
    result = ScoringService.evaluate_long_answer(
        student_answer="Light dependent reactions occur in thylakoids generating oxygen. The dark Calvin cycle occurs in stroma to assemble glucose.",
        model_answer="Photosynthesis occurs in thylakoids splitting water to release oxygen, and stroma fixes carbon into glucose sugars.",
        max_marks=10.0,
        rubrics=rubrics
    )
    assert result["score"] >= 7.0
    assert result["confidence"] >= 0.6
    assert len(result["criteria_matched"]["criteria_details"]) == 2
