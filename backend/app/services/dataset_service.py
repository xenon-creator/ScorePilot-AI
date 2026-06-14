import os
import json
import logging
from typing import Dict, Any, List, Optional

from app.services.embedding_engine import get_similarity

logger = logging.getLogger(__name__)

# Resolve path relative to app/ directory to reach dataset/scorepilot/datasets/processed/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINED_DATASET_PATH = os.getenv(
    "COMBINED_DATASET_PATH",
    os.path.join(BASE_DIR, "dataset", "scorepilot", "datasets", "processed", "combined_dataset.json")
)

class DatasetService:
    """Service to load, cache, and search processed questions and mark schemes from the Dataset Engine."""
    
    _questions_by_id: Dict[str, Dict[str, Any]] = {}
    _questions_list: List[Dict[str, Any]] = []
    _is_loaded: bool = False

    @classmethod
    def load_dataset(cls) -> None:
        """Loads and caches combined_dataset.json in memory."""
        if cls._is_loaded:
            return

        logger.info(f"Loading Dataset Engine questions from: {COMBINED_DATASET_PATH}")
        if not os.path.exists(COMBINED_DATASET_PATH):
            logger.error(f"Dataset file not found at: {COMBINED_DATASET_PATH}")
            cls._questions_by_id = {}
            cls._questions_list = []
            cls._is_loaded = True
            return

        try:
            with open(COMBINED_DATASET_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if isinstance(data, list):
                cls._questions_list = data
                cls._questions_by_id = {q.get("question_id"): q for q in data if q.get("question_id")}
                logger.info(f"Successfully loaded and cached {len(cls._questions_list)} questions from Dataset Engine.")
            else:
                logger.error("Loaded dataset is not a JSON list format.")
                cls._questions_list = []
                cls._questions_by_id = {}
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            cls._questions_list = []
            cls._questions_by_id = {}
            
        cls._is_loaded = True

    @classmethod
    def get_question(cls, question_id: str) -> Optional[Dict[str, Any]]:
        """Finds a question by its exact question_id."""
        cls.load_dataset()
        return cls._questions_by_id.get(question_id)

    @classmethod
    def get_mark_scheme(cls, question_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured marking points and raw mark schemes for a question."""
        cls.load_dataset()
        q = cls.get_question(question_id)
        if not q:
            return None
        return {
            "mark_scheme": q.get("mark_scheme", ""),
            "marking_points": q.get("marking_points", [])
        }

    @classmethod
    def search_question(
        cls,
        query: str,
        subject: Optional[str] = None,
        board: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Filters cached questions by substring matching, board, and subject."""
        cls.load_dataset()
        results = []
        query_lower = query.lower().strip()
        
        for q in cls._questions_list:
            # Filter by board if provided
            if board and q.get("board", "").lower() != board.lower():
                continue
            # Filter by subject if provided
            if subject and q.get("subject", "").lower() != subject.lower():
                continue
                
            # Perform query match
            q_text = q.get("question", "").lower()
            if query_lower in q_text:
                results.append(q)
                if len(results) >= limit:
                    break
                    
        return results

    @classmethod
    def find_similar_question(
        cls,
        question_text: str,
        threshold: float = 0.75
    ) -> Optional[Dict[str, Any]]:
        """Semantically compares the question_text against all cached questions, returning the highest match."""
        cls.load_dataset()
        if not question_text or not cls._questions_list:
            return None

        best_match = None
        best_sim = 0.0

        for q in cls._questions_list:
            q_text = q.get("question", "")
            if not q_text:
                continue
                
            sim = get_similarity(question_text, q_text)
            if sim > best_sim:
                best_sim = sim
                best_match = q

        if best_sim >= threshold:
            logger.info(f"Found semantically similar question match: {best_match.get('question_id')} (Sim: {best_sim:.2f})")
            return best_match
            
        return None
