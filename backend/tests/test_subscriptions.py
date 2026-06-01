import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import SessionLocal, User, UserRole, Subscription, PlanType, SubscriptionStatus
from app.services.subscription_service import (
    get_or_create_subscription, check_usage_limit, increment_usage, activate_subscription
)
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def setup_user():
    db = SessionLocal()
    
    # Create a teacher user
    user = db.query(User).filter(User.email == "sub_teacher@aegis.edu").first()
    if not user:
        user = User(
            email="sub_teacher@aegis.edu",
            name="Teacher Sub",
            role=UserRole.teacher,
            password="hashed_password",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    db.close()
    
    yield user
    
    # Cleanup
    db = SessionLocal()
    db.query(Subscription).filter(Subscription.user_id == user.id).delete()
    db.query(User).filter(User.id == user.id).delete()
    db.commit()
    db.close()

def test_free_user_gets_subscription_on_first_login(setup_user):
    db = SessionLocal()
    try:
        user = setup_user
        
        # Ensure no subscription exists yet
        db.query(Subscription).filter(Subscription.user_id == user.id).delete()
        db.commit()
        
        # Calling get_or_create_subscription should initialize a Free trial subscription
        sub = get_or_create_subscription(user.id, db)
        assert sub is not None
        assert sub.plan == PlanType.free
        assert sub.status == SubscriptionStatus.trial
        assert sub.papers_used == 0
        assert sub.papers_limit == 5
    finally:
        db.close()

def test_usage_limit_check_returns_correct_status(setup_user):
    db = SessionLocal()
    try:
        user = setup_user
        sub = get_or_create_subscription(user.id, db)
        
        # Force usage parameters
        sub.papers_used = 3
        sub.papers_limit = 5
        db.commit()
        
        usage = check_usage_limit(user.id, db)
        assert usage["can_grade"] is True
        assert usage["upgrade_required"] is False
        assert usage["papers_used"] == 3
        assert usage["papers_limit"] == 5
        
        # Exceed limit
        sub.papers_used = 5
        db.commit()
        
        usage = check_usage_limit(user.id, db)
        assert usage["can_grade"] is False
        assert usage["upgrade_required"] is True
    finally:
        db.close()

def test_increment_usage_updates_count(setup_user):
    db = SessionLocal()
    try:
        user = setup_user
        sub = get_or_create_subscription(user.id, db)
        initial_used = sub.papers_used
        
        increment_usage(user.id, db)
        
        # Re-fetch
        db.refresh(sub)
        assert sub.papers_used == initial_used + 1
    finally:
        db.close()

@patch('app.services.storage_service.upload_file_content')
def test_upload_blocked_when_limit_reached_returns_402(mock_upload, setup_user):
    db = SessionLocal()
    try:
        user = setup_user
        sub = get_or_create_subscription(user.id, db)
        
        # Set limit exceeded
        sub.papers_used = 5
        sub.papers_limit = 5
        db.commit()
        
        # Mock storage upload
        mock_upload.return_value = "uploads/mock_s3_key.pdf"
        
        client = TestClient(app)
        from app.core.security import create_access_token
        token = create_access_token(user.name, "Teacher")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Attempt to upload a paper
        response = client.post(
            "/api/v1/uploads",
            data={
                "student_name": "John Doe",
                "student_id": "STUDENT-123",
                "exam_id": "mock-exam-id"
            },
            files={"file": ("sheet.pdf", b"pdf contents", "application/pdf")},
            headers=headers
        )
        
        # Should return 402 Payment Required
        assert response.status_code == 402
        res_data = response.json()
        assert res_data["detail"]["error"] == "usage_limit_reached"
    finally:
        db.close()

def test_verify_payment_activates_subscription(setup_user):
    db = SessionLocal()
    try:
        user = setup_user
        sub = get_or_create_subscription(user.id, db)
        
        # Set a mock razorpay subscription id and target upgrade plan
        sub.razorpay_sub_id = "sub_mock_12345"
        sub.plan = PlanType.starter
        sub.status = SubscriptionStatus.trial
        db.commit()
        
        # Call activate_subscription directly
        activate_subscription("sub_mock_12345", "pay_mock_999", db)
        
        db.refresh(sub)
        assert sub.status == SubscriptionStatus.active
        assert sub.papers_limit == 200
    finally:
        db.close()
