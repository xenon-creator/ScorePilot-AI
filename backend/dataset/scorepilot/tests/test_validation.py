import pytest
from scorepilot.validators import (
    ExamPaper,
    MergedDataset,
    Question,
    SubQuestion,
    validate_exam_paper,
    validate_merged_dataset,
)


def test_subquestion_text_cleaning() -> None:
    """Verifies that sub-question text validator strips excess whitespace."""
    data = {
        "id": "test-q1-a",
        "sub_question_number": "a",
        "question_text": "   Solve for   x:  x + 2 =  5.   ",
        "marks": 3,
    }
    sub_q = SubQuestion(**data)
    assert sub_q.question_text == "Solve for x: x + 2 = 5."
    assert sub_q.marks == 3


def test_question_validation_success() -> None:
    """Verifies successful validation of a correctly structured exam paper."""
    paper_data = {
        "paper_id": "aqa-maths-2023",
        "board": "AQA",
        "subject": "Mathematics",
        "level": "GCSE",
        "year": 2023,
        "title": "GCSE Mathematics Past Paper",
        "questions": [
            {
                "id": "aqa-maths-2023-q1",
                "question_number": "1",
                "question_text": "What is the capital of France?",
                "marks": 1,
                "sub_questions": [],
            }
        ],
    }
    success, instance, error = validate_exam_paper(paper_data)
    assert success is True
    assert error is None
    assert isinstance(instance, ExamPaper)
    assert instance.questions[0].question_number == "1"


def test_question_validation_failure() -> None:
    """Verifies validation failure when required fields are missing."""
    malformed_paper = {
        "board": "AQA",
        "subject": "Mathematics",
        "year": "not-a-number",  # Wrong type
        # Missing total questions and other required properties
    }
    success, instance, error = validate_exam_paper(malformed_paper)
    assert success is False
    assert instance is None
    assert "ValidationError" in error or "validation error" in error.lower()


def test_merged_dataset_validation() -> None:
    """Verifies that a merged QA dataset validates correctly."""
    merged_data = {
        "paper_id": "cbse-science-2023",
        "board": "CBSE",
        "subject": "Science",
        "level": "Class 10",
        "year": 2023,
        "title": "Science Term 1",
        "pairs": [
            {
                "question_id": "cbse-science-2023-q1",
                "question_number": "1",
                "question_text": "Explain photosynthesis.",
                "marks": 5,
                "marking_guidelines": "Explain light reaction [2 marks] and dark reaction [3 marks].",
                "answer_key": None,
                "images": [],
                "metadata": {},
            }
        ],
    }
    success, instance, error = validate_merged_dataset(merged_data)
    assert success is True
    assert error is None
    assert isinstance(instance, MergedDataset)
