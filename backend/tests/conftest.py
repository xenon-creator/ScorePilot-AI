import os
import sys
import pytest

# Programmatically append the backend parent directory to sys.path during collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def pytest_collection_modifyitems(config, items):
    """Skip tests that need real services if services aren't available"""
    pass  # Services are now real in CI, no skipping needed

@pytest.fixture(scope="session")
def db_url():
    return (
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER', 'postgres')}:"
        f"{os.getenv('DB_PASSWORD', 'postgres')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'aegis_grading')}"
    )

@pytest.fixture(scope="session")
def minio_url():
    return os.getenv("S3_ENDPOINT", "localhost:9000")
