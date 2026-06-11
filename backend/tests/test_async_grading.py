import os
import sys
import pytest
from datetime import datetime

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import SessionLocal, Exam, Question, QuestionType, Submission, Answer, SubmissionStatus, User, UserRole
from app.workers.tasks import process_and_score_submission


class TestAsyncGradingPipeline:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        self.db = SessionLocal()
        
        # Get or create a teacher user
        self.teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not self.teacher:
            self.teacher = User(
                email="teacher_test_async@aegis.edu",
                name="Prof. Sarah Async",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(self.teacher)
            self.db.commit()
            self.db.refresh(self.teacher)

        # Create a test exam
        self.exam = Exam(
            title="Async Test Exam",
            description="Testing Celery Asynchronous Integration",
            created_by=self.teacher.id,
        )
        self.db.add(self.exam)
        self.db.commit()
        self.db.refresh(self.exam)

        # Add questions matching simulated OCR text (Q1: A, Q2: C)
        self.q1 = Question(
            exam_id=self.exam.id,
            text="MCQ 1",
            question_type=QuestionType.mcq,
            model_answer="A",
            max_marks=1.0,
        )
        self.q2 = Question(
            exam_id=self.exam.id,
            text="MCQ 2",
            question_type=QuestionType.mcq,
            model_answer="C",
            max_marks=1.0,
        )
        self.db.add(self.q1)
        self.db.add(self.q2)
        self.db.commit()

        yield

        # Cleanup
        self.db.rollback()
        # Delete generated submissions and answers
        subs = self.db.query(Submission).filter(Submission.exam_id == self.exam.id).all()
        for s in subs:
            self.db.delete(s)
        self.db.delete(self.exam)
        self.db.commit()
        self.db.close()

    def test_async_task_grading_pipeline(self):
        # 1. Create a submission with status pending
        submission = Submission(
            exam_id=self.exam.id,
            student_name="Alice Async",
            student_id="STUDENT_ASYNC",
            status=SubmissionStatus.pending,
            total_score=0.0,
            ai_confidence=0.0,
            extracted_text="",
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)

        assert submission.status == SubmissionStatus.pending

        # 2. Simulate S3 uploads staging
        from app.services.storage_service import upload_file_content, ensure_bucket_exists
        ensure_bucket_exists()

        object_key = f"tests/test_async_{submission.id}.pdf"
        upload_file_content(b"Photosynthesis converts light energy into chemical energy. Option A.", object_key)

        # 3. Call Celery task synchronously via .apply()
        task_result = process_and_score_submission.apply(args=[submission.id, object_key, "biology_exam.pdf"])

        # 4. Verify task finished successfully
        assert task_result.status == "SUCCESS"
        res_data = task_result.result
        assert res_data["status"] == "success"
        assert res_data["submission_id"] == submission.id

        # 5. Refresh submission from DB and verify status was updated
        self.db.refresh(submission)
        assert submission.status in [SubmissionStatus.graded, SubmissionStatus.flagged]
        assert submission.total_score > 0
        assert submission.extracted_text != ""

        # 6. Verify Answer records were persisted in DB
        answers = self.db.query(Answer).filter(Answer.submission_id == submission.id).order_by(Answer.question_number).all()
        assert len(answers) == 2
        assert answers[0].ai_score is not None
        assert answers[0].flagged_for_review in [True, False]
        assert answers[0].scored_at is not None
