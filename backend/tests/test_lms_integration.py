import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app
from app.models.database import SessionLocal, User, LMSSettings, UserRole, AuditLog


from app.core.security import create_access_token


class TestLMSIntegration:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        db = SessionLocal()
        # Clean up any existing test user to keep tests isolated and repeatable
        db.query(LMSSettings).delete()
        teacher_rec = db.query(User).filter(User.email == "lms_teacher@aegis.edu").first()
        if teacher_rec:
            db.query(AuditLog).filter(AuditLog.user_id == teacher_rec.id).delete()
            db.query(User).filter(User.id == teacher_rec.id).delete()
        db.commit()
        
        # Create a mock teacher user
        teacher = User(
            name="lms_teacher",
            email="lms_teacher@aegis.edu",
            role=UserRole.teacher,
            password="hashedpassword123"
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        
        self.teacher_user = teacher
        db.close()
        
        yield
        
        # Final cleanup
        db = SessionLocal()
        db.query(LMSSettings).delete()
        if self.teacher_user:
            db.query(AuditLog).filter(AuditLog.user_id == self.teacher_user.id).delete()
            db.query(User).filter(User.id == self.teacher_user.id).delete()
        db.commit()
        db.close()

    def test_lms_settings_endpoints(self):
        client = TestClient(app)
        
        # Generate real signed JWT token for the teacher user
        token = create_access_token("lms_teacher", "Teacher")
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Test GET settings - should be unconfigured initially
        res = client.get("/api/v1/lms/settings", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == {"configured": False}
        
        # Test POST settings - save new credentials
        save_payload = {
            "lms_type": "canvas",
            "api_url": "https://mock-canvas.instructure.com/api/v1",
            "api_token": "canvas_developer_secret_token_abc123"
        }
        res_post = client.post("/api/v1/lms/settings", json=save_payload, headers=auth_headers)
        assert res_post.status_code == 200
        assert res_post.json()["status"] == "success"
        
        # Test GET settings again - should be configured now
        res_get = client.get("/api/v1/lms/settings", headers=auth_headers)
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["configured"] is True
        assert data["lms_type"] == "canvas"
        assert data["api_url"] == "https://mock-canvas.instructure.com/api/v1"
        assert data["api_token"] == "********"  # Token is masked for privacy

    def test_lms_course_sync_simulation(self):
        client = TestClient(app)
        token = create_access_token("lms_teacher", "Teacher")
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Configure mock LMS settings first
        save_payload = {
            "lms_type": "moodle",
            "api_url": "mock_moodle_url",
            "api_token": "moodle_token"
        }
        client.post("/api/v1/lms/settings", json=save_payload, headers=auth_headers)
        
        # Test sync courses endpoint
        res = client.get("/api/v1/lms/courses", headers=auth_headers)
        assert res.status_code == 200
        courses = res.json()
        assert len(courses) == 3
        assert courses[0]["id"] == "lms_c_1"
        assert "Advanced Biology" in courses[0]["name"]
        assert len(courses[0]["assignments"]) == 2
        assert courses[0]["assignments"][0]["id"] == "lms_a_11"
        assert courses[0]["assignments"][0]["name"] == "Cellular Respiration Lab Report"

    def test_lms_grades_batch_posting(self):
        # Test batch grade syncing routing inside lms_service
        from app.services.lms_service import LMSService
        
        grades_payload = [
            {"student_id": "std_101", "grade": 19.0, "feedback": "Superb presentation"},
            {"student_id": "std_102", "grade": 14.5, "feedback": "Good progress"}
        ]
        
        res = LMSService.sync_grades(
            lms_type="canvas",
            api_url="mock_url",
            api_token="mock_token",
            course_id="lms_c_1",
            assignment_id="lms_a_11",
            grades_data=grades_payload
        )
        
        assert res["status"] == "success"
        assert res["synced_count"] == 2
        assert res["details"]["course_id"] == "lms_c_1"
        assert res["details"]["assignment_id"] == "lms_a_11"
