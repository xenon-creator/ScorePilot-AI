import os
import sys
import pytest
from fastapi.testclient import TestClient

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.models.database import SessionLocal, User, UserRole, Exam, Question, Submission, SubmissionStatus, Answer
from app.services.export_service import ExportService

client = TestClient(app)

class TestResultsExporting:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        self.db = SessionLocal()
        
        # 1. Get or create a teacher and two students
        self.teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not self.teacher:
            self.teacher = User(
                email="teacher_test_export@aegis.edu",
                name="Prof. Sarah Export",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(self.teacher)
            self.db.commit()
            
        self.student_mine = self.db.query(User).filter(User.email == "student_mine@aegis.edu").first()
        if not self.student_mine:
            self.student_mine = User(
                email="student_mine@aegis.edu",
                name="Student Mine",
                role=UserRole.student,
                student_id="STUDENT_MINE_01",
                password="hashed_password",
            )
            self.db.add(self.student_mine)
            self.db.commit()

        self.student_other = self.db.query(User).filter(User.email == "student_other@aegis.edu").first()
        if not self.student_other:
            self.student_other = User(
                email="student_other@aegis.edu",
                name="Student Other",
                role=UserRole.student,
                student_id="STUDENT_OTHER_02",
                password="hashed_password",
            )
            self.db.add(self.student_other)
            self.db.commit()

        # 2. Create test exam with questions
        self.exam = Exam(
            title="Export Test Exam",
            description="Testing CSV and PDF Exports",
            created_by=self.teacher.id,
        )
        self.db.add(self.exam)
        self.db.commit()
        self.db.refresh(self.exam)
        
        self.q1 = Question(
            exam_id=self.exam.id,
            text="Describe cell structure.",
            question_type="short",
            model_answer="Cells contain nucleus and mitochondria.",
            max_marks=5.0
        )
        self.db.add(self.q1)
        self.db.commit()
        self.db.refresh(self.q1)

        # 3. Create submissions
        self.sub_mine = Submission(
            exam_id=self.exam.id,
            student_name="Student Mine",
            student_id="STUDENT_MINE_01",
            status=SubmissionStatus.graded,
            total_score=4.0,
            ai_confidence=0.92,
        )
        self.sub_other = Submission(
            exam_id=self.exam.id,
            student_name="Student Other",
            student_id="STUDENT_OTHER_02",
            status=SubmissionStatus.graded,
            total_score=4.5,
            ai_confidence=0.95,
        )
        self.db.add(self.sub_mine)
        self.db.add(self.sub_other)
        self.db.commit()
        self.db.refresh(self.sub_mine)
        self.db.refresh(self.sub_other)
        
        # 4. Create answers
        self.a1 = Answer(
            submission_id=self.sub_mine.id,
            question_id=self.q1.id,
            question_number=1,
            student_answer="Cells have a nucleus.",
            ai_score=4.0,
            final_score=4.0,
            ai_confidence=0.92,
            ai_reasoning="Partial scientific match."
        )
        self.a2 = Answer(
            submission_id=self.sub_other.id,
            question_id=self.q1.id,
            question_number=1,
            student_answer="Cells contain mitochondria.",
            ai_score=4.5,
            final_score=4.5,
            ai_confidence=0.95,
            ai_reasoning="High quality match."
        )
        self.db.add(self.a1)
        self.db.add(self.a2)
        self.db.commit()

        yield

        # Cleanup
        self.db.rollback()
        self.db.delete(self.a1)
        self.db.delete(self.a2)
        self.db.delete(self.sub_mine)
        self.db.delete(self.sub_other)
        self.db.delete(self.q1)
        self.db.delete(self.exam)
        self.db.delete(self.student_mine)
        self.db.delete(self.student_other)
        self.db.commit()
        self.db.close()

    def test_csv_generator_structure(self):
        generator = ExportService.generate_submissions_csv_generator(self.exam, [self.sub_mine, self.sub_other])
        csv_chunks = list(generator)
        csv_text = "".join(csv_chunks)
        
        assert "Submission ID" in csv_text
        assert "Q1 Score" in csv_text
        assert "Q1 Feedback" in csv_text
        assert "Student Mine" in csv_text
        assert "STUDENT_MINE_01" in csv_text
        assert "4.0" in csv_text
        assert "Partial scientific match." in csv_text
        assert "Student Other" in csv_text
        assert "High quality match." in csv_text

    def test_pdf_bytes_compilation(self):
        pdf_bytes = ExportService.generate_student_pdf_bytes(self.sub_mine, self.exam)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_api_csv_export_endpoint(self):
        # Signup and login a teacher
        teacher_signup = {
            "username": "teacher_export_test",
            "email": "teacher_export@aegis.edu",
            "password": "teacherpassword123",
            "role": "Teacher"
        }
        res = client.post("/api/v1/auth/signup", json=teacher_signup)
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Query CSV export endpoint
            response = client.get(f"/api/v1/exams/{self.exam.id}/export/csv", headers=headers)
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]
            assert f"exam_{self.exam.id}_grades.csv" in response.headers["content-disposition"]
            
            content = response.text
            assert "Submission ID" in content
            assert "Student Mine" in content
            assert "STUDENT_MINE_01" in content
            
        finally:
            # Cleanup user
            user = self.db.query(User).filter(User.email == "teacher_export@aegis.edu").first()
            if user:
                self.db.delete(user)
                self.db.commit()

    def test_api_pdf_student_ownership_isolation(self):
        # 1. Signup and login student_mine
        signup_data = {
            "username": "student_export_test",
            "email": "student_export_mine@aegis.edu",
            "password": "studentpassword123",
            "role": "Student",
            "student_id": "STUDENT_MINE_01" # matches self.sub_mine!
        }
        res = client.post("/api/v1/auth/signup", json=signup_data)
        assert res.status_code == 200
        token_mine = res.json()["access_token"]
        headers_mine = {"Authorization": f"Bearer {token_mine}"}
        
        try:
            # 2. Student should successfully download their own PDF
            response_mine = client.get(f"/api/v1/submissions/{self.sub_mine.id}/export/pdf", headers=headers_mine)
            assert response_mine.status_code == 200
            assert response_mine.headers["content-type"] == "application/pdf"
            assert response_mine.content.startswith(b"%PDF-")
            
            # 3. Student should be blocked from downloading other students' PDFs (403 Forbidden)
            response_other = client.get(f"/api/v1/submissions/{self.sub_other.id}/export/pdf", headers=headers_mine)
            assert response_other.status_code == 403
            assert "You can only export your own exam results" in response_other.json()["detail"]
            
        finally:
            user = self.db.query(User).filter(User.email == "student_export_mine@aegis.edu").first()
            if user:
                self.db.delete(user)
                self.db.commit()
