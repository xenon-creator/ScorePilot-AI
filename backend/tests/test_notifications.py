import os
import sys
import shutil
import pytest
from unittest.mock import patch, MagicMock

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import SessionLocal, User, UserRole, Exam, Submission, SubmissionStatus
from app.services.notification_service import NotificationService
from app.workers.tasks import send_score_release_email_task

class TestScoreReleaseNotifications:
    @pytest.fixture(autouse=True)
    def setup_sandbox(self):
        # 1. Ensure sandboxed mailboxes directory is clean for testing
        self.test_mailbox_dir = os.path.join("mailboxes", "score_releases")
        if os.path.exists(self.test_mailbox_dir):
            shutil.rmtree(self.test_mailbox_dir)
            
        self.db = SessionLocal()
        
        # 2. Get or create a teacher and student
        self.teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not self.teacher:
            self.teacher = User(
                email="teacher_test_notify@aegis.edu",
                name="Prof. Sarah Notify",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(self.teacher)
            self.db.commit()
            
        self.student = self.db.query(User).filter(User.role == UserRole.student).first()
        if not self.student:
            self.student = User(
                email="student_test_notify@aegis.edu",
                name="student_bob",
                role=UserRole.student,
                student_id="STUDENT_BOB_99",
                password="hashed_password",
            )
            self.db.add(self.student)
            self.db.commit()
            
        # 3. Create test exam and submission
        self.exam = Exam(
            title="Notification Test Exam",
            description="Testing Email Releases",
            created_by=self.teacher.id,
        )
        self.db.add(self.exam)
        self.db.commit()
        self.db.refresh(self.exam)
        
        self.submission = Submission(
            exam_id=self.exam.id,
            student_name="student_bob",
            student_id="STUDENT_BOB_99",
            status=SubmissionStatus.graded,
            total_score=15.5,
            ai_confidence=0.89,
        )
        self.db.add(self.submission)
        self.db.commit()
        self.db.refresh(self.submission)

        yield

        # Cleanup
        self.db.rollback()
        self.db.delete(self.submission)
        self.db.delete(self.exam)
        self.db.commit()
        self.db.close()
        
        # Clean sandbox mailboxes
        if os.path.exists(self.test_mailbox_dir):
            shutil.rmtree(self.test_mailbox_dir)

    def test_email_html_generation(self):
        breakdown = [
            {"question_number": 1, "question_text": "Explain cells", "score": 4.5, "max_marks": 5.0, "feedback": "Good description."}
        ]
        html = NotificationService.generate_html_email(
            student_name="student_bob",
            exam_title="Biology Final",
            total_score=4.5,
            max_marks=5.0,
            breakdown=breakdown
        )
        
        assert "student_bob" in html
        assert "Biology Final" in html
        assert "4.5" in html
        assert "Explain cells" in html
        assert "Good description." in html
        assert "ScorePilot" in html

    def test_send_email_sandbox_fallback(self):
        breakdown = [
            {"question_number": 1, "question_text": "Explain cells", "score": 4.5, "max_marks": 5.0, "feedback": "Good description."}
        ]
        # Verify that sending without SMTP details creates local HTML sandbox file
        success = NotificationService.send_score_release_email(
            student_name="student_bob",
            student_email="student_bob@aegis.edu",
            exam_title="Biology Final",
            total_score=4.5,
            max_marks=5.0,
            breakdown=breakdown
        )
        
        assert success is True
        assert os.path.exists(self.test_mailbox_dir)
        files = os.listdir(self.test_mailbox_dir)
        assert len(files) == 1
        assert files[0].startswith("student_bob_")
        assert files[0].endswith(".html")
        
        # Read the file and verify content
        with open(os.path.join(self.test_mailbox_dir, files[0]), "r", encoding="utf-8") as f:
            content = f.read()
            assert "student_bob" in content
            assert "Biology Final" in content

    def test_celery_task_notifications_dispatch(self):
        # Trigger the celery task synchronously using .apply()
        task_result = send_score_release_email_task.apply(args=[self.submission.id])
        
        assert task_result.status == "SUCCESS"
        res_data = task_result.result
        assert res_data["status"] == "success"
        assert res_data["recipient"] == self.student.email
        
        # Check that file was written inside the sandbox
        assert os.path.exists(self.test_mailbox_dir)
        files = os.listdir(self.test_mailbox_dir)
        assert len(files) == 1
        assert files[0].startswith("student_bob_")
