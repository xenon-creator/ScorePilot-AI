import os
import sys
import pytest

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import get_db, User, Exam, Question, Submission, Answer, AuditLog, LMSSettings

def test_database_models_importable():
    # Verify all models map to tables cleanly
    assert User.__tablename__ == "users"
    assert Exam.__tablename__ == "exams"
    assert Question.__tablename__ == "questions"
    assert Submission.__tablename__ == "submissions"
    assert Answer.__tablename__ == "answers"
    assert AuditLog.__tablename__ == "audit_logs"
    assert LMSSettings.__tablename__ == "lms_settings"

def test_get_db_generator():
    # Verify get_db works as a standard dependency generator
    db_gen = get_db()
    db_session = next(db_gen)
    assert db_session is not None
    
    try:
        next(db_gen)
    except StopIteration:
        pass
