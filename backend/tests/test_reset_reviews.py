import os
import sys
import pytest
from datetime import datetime
from unittest.mock import patch

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import SessionLocal, Exam, Question, QuestionType, Submission, Answer, SubmissionStatus, User, UserRole
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

class TestResetReviews:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        self.db = SessionLocal()
        
        # Get or create a teacher user
        self.teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not self.teacher:
            self.teacher = User(
                email="teacher_reset@aegis.edu",
                name="Prof. Reset",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(self.teacher)
            self.db.commit()
            self.db.refresh(self.teacher)

        # Get or create an admin user
        self.admin = self.db.query(User).filter(User.role == UserRole.admin).first()
        if not self.admin:
            self.admin = User(
                email="admin_reset@aegis.edu",
                name="Admin Reset",
                role=UserRole.admin,
                password="hashed_password",
            )
            self.db.add(self.admin)
            self.db.commit()
            self.db.refresh(self.admin)

        # Create a test exam
        self.exam = Exam(
            title="Reset Test Exam",
            description="Testing Review resets",
            created_by=self.teacher.id,
        )
        self.db.add(self.exam)
        self.db.commit()
        self.db.refresh(self.exam)

        # Add a question
        self.q = Question(
            exam_id=self.exam.id,
            text="Explain Photosynthesis",
            question_type=QuestionType.short,
            model_answer="Plants convert light energy to food.",
            max_marks=5.0,
        )
        self.db.add(self.q)
        self.db.commit()

        yield

        # Cleanup
        self.db.rollback()
        subs = self.db.query(Submission).filter(Submission.exam_id == self.exam.id).all()
        for s in subs:
            self.db.delete(s)
        self.db.delete(self.exam)
        self.db.commit()
        self.db.close()

    def test_reset_submission_review(self):
        # 1. Create a submission
        submission = Submission(
            exam_id=self.exam.id,
            student_name="Alice Reset",
            status=SubmissionStatus.graded,
            total_score=3.0,
            ai_confidence=0.90,
            confidence_score=90,
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)

        # Create an Answer
        answer = Answer(
            submission_id=submission.id,
            question_id=self.q.id,
            question_number=1,
            student_answer="Green plants use sunlight to make food.",
            ai_score=3.0,
            final_score=3.0,
            ai_confidence=0.90,
            ai_reasoning="Good answer."
        )
        self.db.add(answer)
        self.db.commit()

        # 2. Call the review override endpoint
        client = TestClient(app)
        token = create_access_token(self.teacher.name, "Teacher")
        headers = {"Authorization": f"Bearer {token}"}

        override_payload = {
            "submission_id": submission.id,
            "overrides": [
                {
                    "question_number": 1,
                    "override_score": 5.0,
                    "override_reason": "Excellent answer."
                }
            ]
        }
        res_override = client.post("/api/v1/review/override", json=override_payload, headers=headers)
        assert res_override.status_code == 200
        
        # Verify status is reviewed and score is updated
        self.db.refresh(submission)
        self.db.refresh(answer)
        assert submission.status == SubmissionStatus.reviewed
        assert submission.total_score == 5.0
        assert answer.final_score == 5.0
        assert "Override:" in answer.ai_reasoning

        # 3. Call the reset review endpoint
        reset_payload = {
            "submission_id": submission.id
        }
        res_reset = client.post("/api/v1/review/reset", json=reset_payload, headers=headers)
        assert res_reset.status_code == 200

        # Verify status is back to graded and score is reverted
        self.db.refresh(submission)
        self.db.refresh(answer)
        assert submission.status == SubmissionStatus.graded
        assert submission.total_score == 3.0
        assert answer.final_score == 3.0
        assert "Override:" not in answer.ai_reasoning

    def test_reset_all_reviews(self):
        # 1. Create a submission
        submission = Submission(
            exam_id=self.exam.id,
            student_name="Bob Reset",
            status=SubmissionStatus.graded,
            total_score=2.0,
            ai_confidence=0.85,
            confidence_score=85,
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)

        # Create an Answer
        answer = Answer(
            submission_id=submission.id,
            question_id=self.q.id,
            question_number=1,
            student_answer="Answer.",
            ai_score=2.0,
            final_score=4.0,  # Pre-override
            overridden_by=self.teacher.id,
            ai_confidence=0.85,
            ai_reasoning="Good. [Override: Good job]"
        )
        self.db.add(answer)
        submission.status = SubmissionStatus.reviewed
        self.db.commit()

        # 2. Call reset all reviews as Admin
        client = TestClient(app)
        token = create_access_token(self.admin.name, "Admin")
        headers = {"Authorization": f"Bearer {token}"}

        res_reset = client.post("/api/v1/admin/reset-all-reviews", headers=headers)
        assert res_reset.status_code == 200
        assert res_reset.json()["reset_count"] >= 1

        # Verify status is back to graded and score is reverted
        self.db.refresh(submission)
        self.db.refresh(answer)
        assert submission.status == SubmissionStatus.graded
        assert submission.total_score == 2.0
        assert answer.final_score == 2.0
        assert answer.overridden_by is None
        assert "Override:" not in answer.ai_reasoning
