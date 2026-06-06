import os
import sys
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user_payload

# Setup dependency override for auth
@pytest.fixture(autouse=True)
def setup_auth_override():
    app.dependency_overrides[get_current_user_payload] = lambda: {"sub": "test_user", "role": "Teacher"}
    yield
    app.dependency_overrides.clear()

@patch('razorpay.Client')
def test_create_standard_order_success(mock_razorpay_client):
    # Setup mock order return value
    mock_order_instance = MagicMock()
    mock_order_instance.order.create.return_value = {
        "id": "order_mock_12345",
        "amount": 50000,
        "currency": "INR"
    }
    mock_razorpay_client.return_value = mock_order_instance

    client = TestClient(app)

    # Request body
    payload = {
        "amount": 50000,
        "currency": "INR",
        "receipt": "rcpt_test_123"
    }

    # Set mock environments with non-sensitive keys
    with patch.dict(os.environ, {"RAZORPAY_KEY_ID": "mock_rzp_key_id", "RAZORPAY_KEY_SECRET": "mock_rzp_key_secret"}):
        response = client.post(
            "/api/create-order",
            json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == "order_mock_12345"
        assert data["amount"] == 50000
        assert data["currency"] == "INR"

def test_create_standard_order_validation_fails():
    client = TestClient(app)

    # Amount too low (< 100 paise)
    payload = {
        "amount": 50,
        "currency": "INR"
    }

    response = client.post(
        "/api/create-order",
        json=payload
    )

    assert response.status_code == 400
    assert "Amount must be at least 100 paise" in response.json()["detail"]

def test_verify_standard_payment_success():
    client = TestClient(app)

    order_id = "order_mock_12345"
    payment_id = "pay_mock_67890"
    secret = "mock_rzp_key_secret"

    # Compute valid signature using the mock secret
    msg = f"{order_id}|{payment_id}"
    signature = hmac.new(
        secret.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature
    }

    with patch.dict(os.environ, {"RAZORPAY_KEY_SECRET": secret}):
        response = client.post(
            "/api/verify-payment",
            json=payload
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

def test_verify_standard_payment_signature_mismatch():
    client = TestClient(app)

    payload = {
        "razorpay_order_id": "order_mock_12345",
        "razorpay_payment_id": "pay_mock_67890",
        "razorpay_signature": "invalid_signature_here"
    }

    with patch.dict(os.environ, {"RAZORPAY_KEY_SECRET": "mock_rzp_key_secret"}):
        response = client.post(
            "/api/verify-payment",
            json=payload
        )

        assert response.status_code == 400
        assert "Signature verification failed" in response.json()["detail"]
