import os
import sys
import pytest
from fastapi.testclient import TestClient

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.models.database import SessionLocal, User, UserRole, Exam, Submission, SubmissionStatus
from app.core.security import hash_password

client = TestClient(app)

class TestStudentPortal:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.db = SessionLocal()
        
        # 1. Clean up any existing test student user
        self.test_email = "alice_test_student@aegis.edu"
        existing_user = self.db.query(User).filter(User.email == self.test_email).first()
        if existing_user:
            self.db.delete(existing_user)
            self.db.commit()
            
        yield
        
        # Cleanup after tests
        self.db.rollback()
        user = self.db.query(User).filter(User.email == self.test_email).first()
        if user:
            self.db.delete(user)
            self.db.commit()
        self.db.close()

    def test_student_signup_and_me_flow(self):
        # 1. Test student signup with student_id
        signup_data = {
            "username": "alice_test_student",
            "email": self.test_email,
            "password": "studentpassword123",
            "role": "Student",
            "student_id": "STUDENT_TEST_99"
        }
        
        response = client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == 200
        res_json = response.json()
        assert "access_token" in res_json
        assert res_json["user"]["role"] == "Student"
        assert res_json["user"]["student_id"] == "STUDENT_TEST_99"
        
        token = res_json["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Test /auth/me returns student_id
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        me_json = me_response.json()
        assert me_json["role"] == "Student"
        assert me_json["student_id"] == "STUDENT_TEST_99"

    def test_student_submissions_isolation(self):
        # 1. Create a test student and token
        signup_data = {
            "username": "alice_test_student",
            "email": self.test_email,
            "password": "studentpassword123",
            "role": "Student",
            "student_id": "STUDENT_TEST_99"
        }
        
        response = client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create some submissions in DB: one for this student, one for another
        # Find or create a teacher to create exam
        teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not teacher:
            teacher = User(
                email="teacher_test_portal@aegis.edu",
                name="Prof. Sarah Portal",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(teacher)
            self.db.commit()
            self.db.refresh(teacher)

        exam = Exam(
            title="Portal Test Exam",
            description="Testing Student Submissions Filter",
            created_by=teacher.id,
        )
        self.db.add(exam)
        self.db.commit()
        self.db.refresh(exam)
        
        sub_mine = Submission(
            exam_id=exam.id,
            student_name="alice_test_student",
            student_id="STUDENT_TEST_99",
            status=SubmissionStatus.graded,
            total_score=8.5,
            ai_confidence=0.92,
        )
        sub_other = Submission(
            exam_id=exam.id,
            student_name="Bob Other",
            student_id="STUDENT_BOB_77",
            status=SubmissionStatus.graded,
            total_score=9.0,
            ai_confidence=0.88,
        )
        
        self.db.add(sub_mine)
        self.db.add(sub_other)
        self.db.commit()
        
        try:
            # 3. Query the student submissions endpoint
            sub_response = client.get("/api/v1/student/submissions", headers=headers)
            assert sub_response.status_code == 200
            subs_list = sub_response.json()
            
            # Verify only the current student's submissions are returned
            assert len(subs_list) == 1
            assert subs_list[0]["student_id"] == "STUDENT_TEST_99"
            assert subs_list[0]["student_name"] == "alice_test_student"
            assert subs_list[0]["total_score"] == 8.5
            
        finally:
            # Cleanup created exam and submissions
            self.db.delete(sub_mine)
            self.db.delete(sub_other)
            self.db.delete(exam)
            self.db.commit()

    def test_student_results_query_unauthenticated(self):
        # 1. Create a submission in DB for a specific student name
        teacher = self.db.query(User).filter(User.role == UserRole.teacher).first()
        if not teacher:
            teacher = User(
                email="teacher_test_portal2@aegis.edu",
                name="Prof. Sarah Portal 2",
                role=UserRole.teacher,
                password="hashed_password",
            )
            self.db.add(teacher)
            self.db.commit()
            self.db.refresh(teacher)

        exam = Exam(
            title="Results Query Test Exam",
            description="Testing Student Results unauthenticated API",
            created_by=teacher.id,
        )
        self.db.add(exam)
        self.db.commit()
        self.db.refresh(exam)
        
        sub = Submission(
            exam_id=exam.id,
            student_name="Charlie Test Results",
            student_id="STUDENT_CHARLIE",
            status=SubmissionStatus.graded,
            total_score=9.5,
            ai_confidence=0.95,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        
        try:
            # Query the unauthenticated results endpoint
            response = client.get("/api/v1/student/results?student_name=Charlie Test Results")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["student_name"] == "Charlie Test Results"
            assert data[0]["total_score"] == 9.5
            assert data[0]["exam_title"] == "Results Query Test Exam"
            
            # Query case-insensitively
            response_lc = client.get("/api/v1/student/results?student_name=charlie test results")
            assert response_lc.status_code == 200
            assert len(response_lc.json()) == 1
        finally:
            self.db.delete(sub)
            self.db.delete(exam)
            self.db.commit()

