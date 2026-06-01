import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.question_paper_service import parse_questions_from_text, QuestionPaperService
from fastapi.testclient import TestClient
from app.main import app

def test_extract_questions_from_text():
    raw_text = (
        "1. What is machine learning? [5]\n"
        "Question 2. Describe the difference between classification and regression. [10 marks]\n"
        "Q3. Write short notes on clustering algorithms.\n"
    )
    questions = parse_questions_from_text(raw_text)
    assert len(questions) == 3
    
    assert questions[0]["question_number"] == 1
    assert "machine learning" in questions[0]["question_text"]
    
    assert questions[1]["question_number"] == 2
    assert "classification and regression" in questions[1]["question_text"]
    
    assert questions[2]["question_number"] == 3
    assert "clustering algorithms" in questions[2]["question_text"]

def test_marks_hint_parsing():
    raw_text_with_marks = (
        "Q1. Solve 2x + 3 = 7. (5 marks)\n"
        "Q2. Explain Newton's laws. [12 pts]\n"
        "Q3. Define gravity.\n"
    )
    questions = parse_questions_from_text(raw_text_with_marks)
    assert len(questions) == 3
    
    assert questions[0]["marks_hint"] == 5
    assert questions[1]["marks_hint"] == 12
    assert questions[2]["marks_hint"] == 10  # default fallback

@patch('app.services.ocr_service.OCRService.simulate_scanning_pipeline')
def test_question_paper_upload_endpoint(mock_pipeline):
    # Setup mock ocr pipeline response
    mock_pipeline.return_value = {
        "status": "Success",
        "ocr_version": "Simulation-Fallback-Active",
        "raw_text": "1. What is AI? (5 marks)\nQ2. What is deep learning? [15 marks]"
    }
    
    client = TestClient(app)
    # Generate mock jwt token
    from app.core.security import create_access_token
    token = create_access_token("test_teacher", "Teacher")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/api/v1/exams/upload-paper",
        files={"file": ("paper.pdf", b"pdf contents", "application/pdf")},
        headers=headers
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert "questions" in res_data
    assert len(res_data["questions"]) == 2
    assert res_data["questions"][0]["number"] == 1
    assert res_data["questions"][0]["marks_hint"] == 5
    assert "AI" in res_data["questions"][0]["text"]
