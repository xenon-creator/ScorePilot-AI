import unittest
from unittest.mock import patch
from app.services.scoring_service import ScoringService
from app.services.scoring_service_v2 import score_answer

class TestScoringV2(unittest.TestCase):
    def test_mcq_exact_match(self):
        res = ScoringService.evaluate_mcq("A", "A", 2.0)
        self.assertEqual(res.score, 2.0)
        self.assertEqual(res.confidence, 100.0)

    def test_mcq_option_character(self):
        res = ScoringService.evaluate_mcq("B) Carbon dioxide", "B", 4.0)
        self.assertEqual(res.score, 4.0)
        self.assertEqual(res.confidence, 100.0)

    def test_mcq_incorrect_option(self):
        res = ScoringService.evaluate_mcq("C", "A", 2.0, negative_marking=0.5)
        self.assertEqual(res.score, -0.5)
        self.assertEqual(res.confidence, 100.0)

    def test_short_answer_marking_scheme(self):
        # A simple marking scheme for "What is photosynthesis?"
        scheme = {
            "marking_points": [
                {"id": 1, "point": "plants use sunlight", "marks": 1.0},
                {"id": 2, "point": "make glucose and oxygen", "marks": 1.0}
            ]
        }
        
        # Student answer matches point 1 strongly, point 2 weakly
        student_answer = "Green plants capture sunlight to synthesize food."
        model_answer = "Photosynthesis is when plants use sunlight to make glucose and oxygen."
        
        # We mock get_similarity:
        # Match point 1: "plants use sunlight" vs "Green plants capture sunlight to synthesize food." -> high similarity
        # Match point 2: "make glucose and oxygen" vs "Green plants capture sunlight to synthesize food." -> low similarity
        def mock_similarity(a, b):
            if "sunlight" in a.lower() and "sunlight" in b.lower():
                return 0.80
            return 0.35
            
        with patch("app.services.scoring_service.get_similarity", side_effect=mock_similarity):
            res = ScoringService.evaluate_short_answer(
                student_answer=student_answer,
                model_answer=model_answer,
                max_marks=2.0,
                marking_scheme=scheme
            )
            
            # Point 1: 0.80 >= 0.75 -> awarded 1.0 mark
            # Point 2: 0.35 < 0.50 -> awarded 0.0 marks
            # Total expected score = 1.0
            self.assertEqual(res.score, 1.0)
            self.assertIn("plants use sunlight", res.criteria_matched["matched_points"])
            self.assertIn("make glucose and oxygen", res.criteria_matched["missing_points"])

    def test_short_answer_contradiction_penalty(self):
        scheme = {
            "marking_points": [
                {"id": 1, "point": "energy is conserved", "marks": 2.0}
            ]
        }
        # Student contradicts
        student_answer = "Energy is not conserved in thermodynamics."
        
        # Mock similarity to be high (sentence structure is very similar)
        with patch("app.services.scoring_service.get_similarity", return_value=0.85):
            res = ScoringService.evaluate_short_answer(
                student_answer=student_answer,
                model_answer="Energy is always conserved.",
                max_marks=2.0,
                marking_scheme=scheme
            )
            self.assertEqual(res.score, 2.0)
            self.assertTrue(res.criteria_matched["contradiction_detected"])
            # Penalty should reduce confidence score significantly
            self.assertLess(res.confidence, 70.0)

    def test_long_answer_rubric_dimensions(self):
        student_answer = "Photosynthesis is key. For example, plants use carbon dioxide and release oxygen. Therefore, ecosystems survive."
        model_answer = "Photosynthesis is the cellular process of producing chemical energy from light, carbon dioxide, and water. Oxygen is released as a byproduct."
        
        with patch("app.services.scoring_service.get_similarity", return_value=0.70):
            res = ScoringService.evaluate_long_answer(
                student_answer=student_answer,
                model_answer=model_answer,
                max_marks=10.0
            )
            
            # Check presence of rubric evaluation metrics
            rubric = res.criteria_matched["rubric_evaluation"]
            self.assertIn("coverage", rubric)
            self.assertIn("accuracy", rubric)
            self.assertIn("depth", rubric)
            # Example keywords ("for example") -> full points (2.0)
            self.assertEqual(rubric["examples"], 2.0)
            # Transition keywords ("therefore") -> partial points (0.67)
            self.assertEqual(rubric["structure"], 0.67)
            self.assertGreater(res.score, 0.0)

    @patch("app.services.scoring_service.review_answer_with_llm")
    def test_score_answer_trigger_llm_fallback(self, mock_llm):
        # Setup mock LLM return payload
        mock_llm.return_value = {
            "score": 4.5,
            "confidence": 90.0,
            "reasoning": "Excellent detailed response.",
            "matched_points": ["Point A", "Point B"],
            "missing_points": [],
            "rubric_evaluation": None
        }
        
        # We mock confidence to be < 70 by returning low similarities
        with patch("app.services.scoring_service.get_similarity", return_value=0.20):
            with patch("os.getenv", return_value="fake_hf_token"):
                result = score_answer(
                    student_answer="Very brief answer",
                    model_answer="Highly detailed expected model answer text containing key concepts.",
                    question_type="short",
                    max_marks=5.0,
                    question_text="Describe gravity."
                )
                
                # Check that LLM review was activated and overrode the low confidence score
                self.assertEqual(result["score"], 4.5)
                self.assertEqual(result["confidence"], 90.0)
                self.assertTrue(result["evaluation_metadata"]["llm_reviewed"])
                mock_llm.assert_called_once()

    def test_photosynthesis_grading(self):
        scheme = {
            "marking_points": [
                {"id": 1, "point": "carbon dioxide is absorbed", "marks": 1.0},
                {"id": 2, "point": "water is absorbed", "marks": 1.0},
                {"id": 3, "point": "light energy is utilized", "marks": 1.0},
                {"id": 4, "point": "glucose is produced", "marks": 1.0},
                {"id": 5, "point": "oxygen is released", "marks": 1.0}
            ]
        }
        student_answer = "Photosynthesis uses carbon dioxide and light energy to produce oxygen."
        
        # We mock get_similarity:
        # Match point 1: "carbon dioxide is absorbed" -> 0.85 (matched)
        # Match point 2: "water is absorbed" -> 0.20 (missing)
        # Match point 3: "light energy is utilized" -> 0.80 (matched)
        # Match point 4: "glucose is produced" -> 0.15 (missing)
        # Match point 5: "oxygen is released" -> 0.82 (matched)
        def mock_similarity(a, b):
            a_lower = a.lower()
            if "carbon dioxide" in a_lower:
                return 0.85
            if "light energy" in a_lower:
                return 0.80
            if "oxygen" in a_lower:
                return 0.82
            if "water" in a_lower:
                return 0.20
            if "glucose" in a_lower:
                return 0.15
            return 0.10

        with patch("app.services.scoring_service.get_similarity", side_effect=mock_similarity):
            res = ScoringService.evaluate_short_answer(
                student_answer=student_answer,
                model_answer="Photosynthesis requires carbon dioxide, water, and light energy to yield glucose and oxygen.",
                max_marks=5.0,
                marking_scheme=scheme
            )
            
            # Assertions
            self.assertEqual(res.score, 3.0)
            self.assertTrue(50.0 <= res.confidence <= 90.0)
            self.assertIn("carbon dioxide is absorbed", res.criteria_matched["matched_points"])
            self.assertIn("light energy is utilized", res.criteria_matched["matched_points"])
            self.assertIn("oxygen is released", res.criteria_matched["matched_points"])
            self.assertIn("water is absorbed", res.criteria_matched["missing_points"])
            self.assertIn("glucose is produced", res.criteria_matched["missing_points"])
            
            # Check debug output exists and is populated correctly
            self.assertIsNotNone(res.debug_output)
            self.assertEqual(res.debug_output["student_answer"], student_answer)
            self.assertEqual(len(res.debug_output["marking_points"]), 5)
            self.assertEqual(res.debug_output["score"], 3.0)
            self.assertTrue(50.0 <= res.debug_output["confidence"] <= 90.0)

    def test_empty_marking_scheme_raises_value_error(self):
        with patch("app.core.config.settings.USE_V2_GRADING", True):
            with patch("app.services.dataset_service.DatasetService.get_question", return_value={"question_id": "test", "marking_points": []}):
                with self.assertRaises(ValueError):
                    score_answer(
                        student_answer="Some answer",
                        model_answer="Some model answer",
                        question_type="short",
                        max_marks=5.0,
                        question_text="Some question",
                        question_id="test"
                    )

    def test_missing_dataset_record_returns_error(self):
        with patch("app.core.config.settings.USE_V2_GRADING", True):
            with patch("app.services.dataset_service.DatasetService.get_question", return_value=None):
                with patch("app.services.dataset_service.DatasetService.find_similar_question", return_value=None):
                    res = score_answer(
                        student_answer="Some answer",
                        model_answer="Some model answer",
                        question_type="short",
                        max_marks=5.0,
                        question_text="Some question",
                        question_id="nonexistent"
                    )
                    self.assertIn("error", res)
                    self.assertEqual(res["error"], "No dataset record found")
