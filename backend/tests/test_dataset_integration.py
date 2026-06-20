import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.core.security import get_current_user_payload
from app.services.dataset_service import DatasetService
from app.services.scoring_service_v2 import score_answer
from app.core.config import settings

client = TestClient(app)

# Override auth dependency for testing endpoint authorization
@pytest.fixture(autouse=True)
def setup_mock_dataset():
    """Seed DatasetService in-memory cache with test questions."""
    app.dependency_overrides[get_current_user_payload] = lambda: {"sub": "test_teacher", "role": "Teacher"}
    test_questions = [
        {
            "board": "CBSE",
            "subject": "Chemistry",
            "question_id": "cbse-chem-1",
            "question": "What is the molecular formula of water?",
            "max_marks": 2,
            "mark_scheme": "The formula is H2O",
            "marking_points": [
                {"point": "Contains two Hydrogen atoms", "marks": 1.0},
                {"point": "Contains one Oxygen atom", "marks": 1.0}
            ]
        },
        {
            "board": "AQA",
            "subject": "Biology",
            "question_id": "aqa-bio-1",
            "question": "Explain photosynthesis.",
            "max_marks": 4,
            "mark_scheme": "Plants use light and carbon dioxide to produce glucose.",
            "marking_points": [
                {"point": "Plants absorb light/sunlight", "marks": 2.0},
                {"point": "Produce glucose/oxygen", "marks": 2.0}
            ]
        }
    ]
    DatasetService._questions_list = test_questions
    DatasetService._questions_by_id = {q["question_id"]: q for q in test_questions}
    DatasetService._is_loaded = True
    yield
    # Reset
    DatasetService._questions_list = []
    DatasetService._questions_by_id = {}
    DatasetService._is_loaded = False
    app.dependency_overrides.clear()


def test_dataset_service_lookups():
    # Exact lookup
    q = DatasetService.get_question("cbse-chem-1")
    assert q is not None
    assert q["subject"] == "Chemistry"

    # Mark scheme lookup
    ms = DatasetService.get_mark_scheme("aqa-bio-1")
    assert ms is not None
    assert len(ms["marking_points"]) == 2

    # Search lookup
    res = DatasetService.search_question(query="photosynthesis", subject="Biology", board="AQA")
    assert len(res) == 1
    assert res[0]["question_id"] == "aqa-bio-1"

    # Semantic similarity search fallback
    # We patch the similarity checker
    with patch("app.services.dataset_service.get_similarity") as mock_sim:
        mock_sim.side_effect = lambda a, b: 0.90 if "water" in a.lower() and "water" in b.lower() else 0.10
        similar = DatasetService.find_similar_question("What is water's formula?")
        assert similar is not None
        assert similar["question_id"] == "cbse-chem-1"


def test_score_answer_dispatch_v1():
    # With USE_V2_GRADING = False, it should invoke the old score_answer from scoring_service
    with patch("app.core.config.settings.USE_V2_GRADING", False):
        with patch("app.services.scoring_service.score_answer") as mock_v1_score:
            mock_v1_score.return_value = {"score": 2.0, "confidence": 95.0, "reasoning": "V1 Path"}
            
            res = score_answer(
                student_answer="H2O",
                model_answer="H2O is water",
                question_type="short",
                max_marks=2.0,
                question_text="Formula of water?",
                question_id="cbse-chem-1"
            )
            
            assert res["reasoning"] == "V1 Path"
            mock_v1_score.assert_called_once()


def test_score_answer_dispatch_v2_grading():
    # With USE_V2_GRADING = True, it should execute the point-by-point V2 engine
    with patch("app.core.config.settings.USE_V2_GRADING", True):
        # We mock embedding similarity to get predictable point matching
        # Match point 1 strongly (0.80 >= 0.75 -> full marks)
        # Match point 2 weakly (0.60 >= 0.50 -> partial marks)
        def mock_sim(a, b):
            if "hydrogen" in a.lower() and "hydrogen" in b.lower():
                return 0.85
            if "oxygen" in a.lower() and "oxygen" in b.lower():
                return 0.60
            return 0.20

        with patch("app.services.scoring_service_v2.get_similarity", side_effect=mock_sim):
            res = score_answer(
                student_answer="It contains hydrogen atoms and some oxygen.",
                model_answer="H2O contains two Hydrogen atoms and one Oxygen.",
                question_type="short",
                max_marks=2.0,
                question_text="Explain H2O components.",
                question_id="cbse-chem-1"
            )
            
            # Point 1: full marks (1.0)
            # Point 2: partial marks (0.5 * 1.0 = 0.5)
            # Total score = 1.5
            assert res["score"] == 1.5
            assert "hydrogen" in res["matched_points"][0].lower()
            assert "oxygen" in res["partial_points"][0].lower()


def test_api_dataset_endpoints():
    # Test GET /api/v1/datasets/search
    response = client.get("/api/v1/datasets/search?query=photosynthesis")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question_id"] == "aqa-bio-1"

    # Test GET /api/v1/datasets/questions/{question_id}
    response = client.get("/api/v1/datasets/questions/cbse-chem-1")
    assert response.status_code == 200
    assert response.json()["subject"] == "Chemistry"

    # Test GET /api/v1/datasets/questions/{question_id} (Not found)
    response = client.get("/api/v1/datasets/questions/invalid-id")
    assert response.status_code == 404

    # Test GET /api/v1/datasets/mark-schemes/{question_id}
    response = client.get("/api/v1/datasets/mark-schemes/aqa-bio-1")
    assert response.status_code == 200
    assert "marking_points" in response.json()


def test_debug_api_endpoint():
    from app.models.database import SessionLocal, Submission, Answer, Question, SubmissionStatus
    db = SessionLocal()
    try:
        # Create a test question
        q = Question(
            exam_id="dummy_exam_id",
            text="What is photosynthesis?",
            question_type="short",
            model_answer="Plants make food using sunlight.",
            max_marks=5.0
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        # Create a test submission
        sub = Submission(
            exam_id="dummy_exam_id",
            student_name="Test Student",
            status=SubmissionStatus.graded,
            ai_confidence=0.85
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

        # Create a test answer
        ans = Answer(
            submission_id=sub.id,
            question_id=q.id,
            student_answer="Plants make food.",
            ai_score=3.0,
            ai_confidence=0.85,
            evaluation_metadata={
                "debug_output": {
                    "marking_points": ["Plants make food", "using sunlight"],
                    "similarities": [0.95, 0.20],
                    "score": 3.0,
                    "confidence": 85.0
                }
            }
        )
        db.add(ans)
        db.commit()
        
        response = client.get(f"/api/v1/debug/submission/{sub.id}")
        assert response.status_code == 200
        res = response.json()
        assert res["student_answer"] == "Plants make food."
        assert res["score"] == 3.0
        assert res["confidence"] == 85.0
        assert res["question"] == "What is photosynthesis?"
        assert res["mark_scheme"] == ["Plants make food", "using sunlight"]
        
        db.delete(ans)
        db.delete(sub)
        db.delete(q)
        db.commit()
    finally:
        db.close()
