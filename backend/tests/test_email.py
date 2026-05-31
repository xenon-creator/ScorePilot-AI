import os
import sys
import pytest

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.email_service import send_score_notification

def test_send_score_notification_graceful_skip():
    # Verify that calling send_score_notification with SMTP unconfigured returns False without crashing
    res = send_score_notification(
        to_email="student_test@aegis.edu",
        student_name="Test Student",
        exam_title="Test Exam",
        total_score=8.5
    )
    assert res is False
