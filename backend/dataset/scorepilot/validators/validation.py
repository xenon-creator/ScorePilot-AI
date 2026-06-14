import logging
from typing import Any, Dict, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("scorepilot.validators")


class DatasetValidationError(ValueError):
    """Custom exception raised when dataset schema validation fails."""
    pass


def validate_model(data: Dict[str, Any], model_cls: Type[BaseModel]) -> Tuple[bool, Optional[BaseModel], Optional[str]]:
    """Generic helper to validate data against a Pydantic model.
    
    Returns:
        A tuple of (success, validated_model_instance, error_message)
    """
    try:
        instance = model_cls(**data)
        return True, instance, None
    except ValidationError as e:
        error_msg = str(e)
        logger.error(f"Validation failed for {model_cls.__name__}. Errors:\n{error_msg}")
        return False, None, error_msg


def validate_exam_paper(data: Dict[str, Any]) -> Tuple[bool, Optional[Any], Optional[str]]:
    """Validate a parsed question paper against the ExamPaper Pydantic model."""
    from .schemas import ExamPaper
    return validate_model(data, ExamPaper)


def validate_mark_scheme(data: Dict[str, Any]) -> Tuple[bool, Optional[Any], Optional[str]]:
    """Validate a parsed mark scheme against the MarkScheme Pydantic model."""
    from .schemas import MarkScheme
    return validate_model(data, MarkScheme)


def validate_merged_dataset(data: Dict[str, Any]) -> Tuple[bool, Optional[Any], Optional[str]]:
    """Validate a combined question-answer merged dataset against the MergedDataset model."""
    from .schemas import MergedDataset
    return validate_model(data, MergedDataset)
