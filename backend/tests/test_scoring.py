"""
Test suite for the real AI scoring engine.
Run: pytest backend/tests/test_scoring.py -v
"""
import pytest
from app.services.scoring_service import ScoringService


class TestMCQScoring:
    def test_mcq_exact_match(self):
        result = ScoringService.evaluate_mcq("photosynthesis", "photosynthesis", 2.0)
        assert result.score == 2.0
        assert result.confidence in [1.0, 100.0]

    def test_mcq_semantic_match(self):
        result = ScoringService.evaluate_mcq(
            "the process by which plants make food",
            "photosynthesis",
            2.0,
        )
        # Semantic match should score something > 0
        assert result.score > 0


class TestShortAnswerScoring:
    def test_short_answer_partial(self):
        result = ScoringService.evaluate_short_answer(
            "plants use sunlight to make glucose",
            "photosynthesis converts light energy into chemical energy stored as glucose using chlorophyll",
            5.0,
        )
        assert 1.0 <= result.score <= 4.5


class TestLongAnswerScoring:
    def test_long_answer_empty(self):
        result = ScoringService.evaluate_long_answer(
            "",
            "any model answer text here",
            10.0,
        )
        assert result.score == 0.0

    def test_confidence_flagging(self):
        result = ScoringService.evaluate_long_answer(
            "unclear rambling text xyz abc",
            "precise scientific explanation of cellular respiration including glycolysis and krebs cycle. "
            "The electron transport chain produces ATP through oxidative phosphorylation. "
            "NADH and FADH2 serve as electron carriers in the process.",
            10.0,
        )
        assert result.flagged_for_review is True


class TestScoringEdgeCases:
    def test_empty_student_answer_short(self):
        result = ScoringService.evaluate_short_answer("", "model answer", 5.0)
        assert result.score == 0.0

    def test_perfect_similarity_short(self):
        answer = "photosynthesis converts light energy into chemical energy stored as glucose using chlorophyll"
        result = ScoringService.evaluate_short_answer(answer, answer, 5.0)
        assert result.score >= 4.0

    def test_mcq_option_letters(self):
        result = ScoringService.evaluate_mcq("B", "B", 1.0)
        assert result.score == 1.0

    def test_mcq_wrong_option(self):
        result = ScoringService.evaluate_mcq("A", "C", 1.0)
        assert result.score <= 0.0
