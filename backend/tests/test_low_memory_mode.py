import unittest
from unittest.mock import patch
from app.services.embedding_engine import get_similarity, get_batch_similarity

class TestLowMemoryMode(unittest.TestCase):
    @patch("app.services.embedding_engine.LOW_MEMORY_MODE", True)
    @patch("app.services.embedding_engine._hf_inference_similarity")
    def test_get_similarity_hf_success(self, mock_hf):
        mock_hf.return_value = 0.85
        sim = get_similarity("hello world", "hello earth")
        self.assertEqual(sim, 0.85)
        mock_hf.assert_called_once_with("hello world", "hello earth")

    @patch("app.services.embedding_engine.LOW_MEMORY_MODE", True)
    @patch("app.services.embedding_engine._hf_inference_similarity")
    def test_get_similarity_hf_failure_keyword_fallback(self, mock_hf):
        mock_hf.return_value = None  # API fails
        # Keyword similarity between "photosynthesis" and "photosynthesis" should be 1.0
        sim = get_similarity("photosynthesis", "photosynthesis")
        self.assertEqual(sim, 1.0)
        mock_hf.assert_called_once_with("photosynthesis", "photosynthesis")

    @patch("app.services.embedding_engine.LOW_MEMORY_MODE", True)
    @patch("app.services.embedding_engine._hf_inference_similarity")
    def test_get_batch_similarity_hf_success(self, mock_hf):
        mock_hf.return_value = 0.75
        sims = get_batch_similarity([("apple", "banana")])
        self.assertEqual(sims, [0.75])
        mock_hf.assert_called_once_with("apple", "banana")
