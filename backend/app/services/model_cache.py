"""
Model caching configuration for sentence-transformers.

On first import, sets SENTENCE_TRANSFORMERS_HOME to ./models/ directory
so the model is downloaded and cached locally (not in user home).
"""
import os

# Default cache directory: backend/models/
MODEL_CACHE_DIR = os.getenv(
    "MODEL_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "models"),
)
MODEL_CACHE_DIR = os.path.abspath(MODEL_CACHE_DIR)

# Ensure directory exists
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# Set env var BEFORE sentence-transformers is imported anywhere
os.environ["SENTENCE_TRANSFORMERS_HOME"] = MODEL_CACHE_DIR

print(f"[ModelCache] Cache directory: {MODEL_CACHE_DIR}")
