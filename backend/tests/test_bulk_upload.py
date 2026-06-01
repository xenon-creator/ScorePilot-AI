import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.bulk_upload_service import extract_student_name, parse_answers_from_text
from app.models.database import SessionLocal, Exam, User, UserRole, Submission, SubmissionStatus
from fastapi.testclient import TestClient
from app.main import app, BULK_JOBS

def test_extract_student_name_from_text():
    text_with_name = (
        "Name: Sarah Jenkins\n"
        "Class: Physics 101\n"
        "Answer 1: mitochondria is cell powerhouse\n"
    )
    name = extract_student_name(text_with_name, "phys_exam.pdf")
    assert name == "Sarah Jenkins"
    
    text_with_student = (
        "Student: David Miller\n"
        "Subject: Chemistry\n"
    )
    name = extract_student_name(text_with_student, "chem_exam.pdf")
    assert name == "David Miller"

def test_extract_student_name_from_filename():
    text_no_name = "Subject: History\nAnswer 1: French Revolution"
    name = extract_student_name(text_no_name, "charles_darwin_history.pdf")
    assert name == "charles darwin history"

def test_parse_answers_from_text():
    raw_text = (
        "Ans 1: Mitochondria is the powerhouse of the cell.\n"
        "Answer 2: Photosynthesis is the process used by plants to convert solar energy.\n"
        "Q3: Gravity pulls things down.\n"
    )
    parsed = parse_answers_from_text(raw_text, [])
    assert len(parsed) == 3
    assert parsed[1] == "Mitochondria is the powerhouse of the cell."
    assert parsed[2] == "Photosynthesis is the process used by plants to convert solar energy."
    assert parsed[3] == "Gravity pulls things down."

@pytest.fixture
def setup_teacher_and_exam():
    db = SessionLocal()
    
    # 1. Create a teacher
    teacher = db.query(User).filter(User.role == UserRole.teacher).first()
    if not teacher:
        teacher = User(
            email="bulk_teacher@aegis.edu",
            name="Teacher Bulk",
            role=UserRole.teacher,
            password="hashed_password",
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        
    # 2. Create an exam
    exam = Exam(
        title="Bulk Test Exam",
        description="Bulk integration test",
        created_by=teacher.id,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    db.close()
    
    yield exam.id
    
    # Cleanup
    db = SessionLocal()
    db.query(Submission).filter(Submission.exam_id == exam.id).delete()
    db.query(Exam).filter(Exam.id == exam.id).delete()
    db.commit()
    db.close()

@patch('app.services.storage_service.upload_file_content')
@patch('app.services.ocr_service.OCRService.simulate_scanning_pipeline')
def test_bulk_upload_endpoint_returns_job_status(mock_ocr, mock_upload, setup_teacher_and_exam):
    exam_id = setup_teacher_and_exam
    
    # Mock S3 upload
    mock_upload.return_value = "uploads/mock_s3_key.pdf"
    
    # Mock OCR
    mock_ocr.return_value = {
        "status": "Success",
        "ocr_version": "Simulation-Fallback-Active",
        "raw_text": "Name: Rahul Sharma\nAns 1: cell powerhouse is mitochondria"
    }
    
    client = TestClient(app)
    from app.core.security import create_access_token
    token = create_access_token("test_teacher_bulk", "Teacher")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Hit bulk upload endpoint
    response = client.post(
        "/api/v1/uploads/bulk",
        data={"exam_id": exam_id},
        files=[("files", ("rahul_sharma.pdf", b"pdf contents", "application/pdf"))],
        headers=headers
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert "job_id" in res_data
    assert res_data["total"] == 1
    assert res_data["processed"] == 1
    assert len(res_data["submission_ids"]) == 1
    
    job_id = res_data["job_id"]
    
    # Check status endpoint
    status_response = client.get(
        f"/api/v1/uploads/bulk/status/{job_id}",
        headers=headers
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert "status" in status_data
    assert status_data["total"] == 1
    
    # Verify job id is in global BULK_JOBS map
    assert job_id in BULK_JOBS
