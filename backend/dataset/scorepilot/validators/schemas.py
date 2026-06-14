from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SubQuestion(BaseModel):
    """Pydantic model representing a sub-question under a main exam question."""
    id: str = Field(..., description="Unique sub-question ID, e.g., 'AQA-MATH-2023-P1-Q1a'")
    sub_question_number: str = Field(..., description="Sub-question identifier, e.g., 'a', 'ii', 'A'")
    question_text: str = Field(..., description="Cleaned text of the sub-question")
    marks: Optional[int] = Field(None, description="Marks allocated to this sub-question")
    images: List[str] = Field(default_factory=list, description="Relative paths to extracted diagrams/images")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")

    @field_validator("question_text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        """Strip leading/trailing whitespaces and reduce multiple spaces."""
        if not v:
            return v
        return " ".join(v.split())


class Question(BaseModel):
    """Pydantic model representing a main exam question."""
    id: str = Field(..., description="Unique question ID, e.g., 'AQA-MATH-2023-P1-Q1'")
    question_number: str = Field(..., description="Question identifier, e.g., '1', '2', 'Part A'")
    section: Optional[str] = Field(None, description="Section of the paper, e.g., 'Section A'")
    question_text: str = Field(..., description="Cleaned main text of the question")
    marks: Optional[int] = Field(None, description="Marks allocated to the main question (excluding sub-questions)")
    sub_questions: List[SubQuestion] = Field(default_factory=list, description="Nested list of sub-questions")
    images: List[str] = Field(default_factory=list, description="Relative paths to extracted diagrams/images")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")

    @field_validator("question_text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        if not v:
            return v
        return " ".join(v.split())


class ExamPaper(BaseModel):
    """Pydantic model representing a complete Question Paper."""
    paper_id: str = Field(..., description="Unique identifier for the paper")
    board: str = Field(..., description="Exam board name, e.g., 'AQA', 'CBSE'")
    subject: str = Field(..., description="Subject name, e.g., 'Mathematics', 'Physics'")
    level: str = Field(..., description="Exam level, e.g., 'GCSE', 'A-Level', 'Class 10', 'Class 12'")
    year: int = Field(..., description="Year of the examination")
    series: Optional[str] = Field(None, description="Series/session, e.g., 'June', 'November', 'Main Exam'")
    paper_code: Optional[str] = Field(None, description="Code printed on the paper")
    title: str = Field(..., description="Title of the paper")
    instructions: Optional[str] = Field(None, description="Instructions printed on the exam paper")
    total_marks: Optional[int] = Field(None, description="Total maximum marks for the paper")
    questions: List[Question] = Field(..., description="List of questions in this paper")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")


class MarkSchemeItem(BaseModel):
    """Pydantic model representing an individual mark scheme item corresponding to a question."""
    question_id: str = Field(..., description="Target question/sub-question ID to link to")
    question_number: str = Field(..., description="Identifier matching the question, e.g., '1(a)'")
    answer_key: Optional[str] = Field(None, description="Direct answer key (MCQ options, short numeric values)")
    marking_guidelines: str = Field(..., description="Text details on how marks are awarded")
    steps: List[str] = Field(default_factory=list, description="Specific steps to get full/partial marks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")


class MarkScheme(BaseModel):
    """Pydantic model representing a complete Mark Scheme document."""
    paper_id: str = Field(..., description="Unique identifier of the matching Question Paper")
    board: str = Field(..., description="Exam board name, e.g., 'AQA', 'CBSE'")
    subject: str = Field(..., description="Subject name, e.g., 'Mathematics', 'Physics'")
    level: str = Field(..., description="Exam level, e.g., 'GCSE', 'A-Level', 'Class 10', 'Class 12'")
    year: int = Field(..., description="Year of the examination")
    series: Optional[str] = Field(None, description="Series/session, e.g., 'June', 'November', 'Main Exam'")
    paper_code: Optional[str] = Field(None, description="Code printed on the mark scheme")
    items: List[MarkSchemeItem] = Field(..., description="List of marking guidelines mapped to questions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")


class MergedQuestionAnswer(BaseModel):
    """Unified representation of a Question paired with its Mark Scheme guidelines (AI-Training schema)."""
    question_id: str = Field(..., description="ID matching the question node")
    question_number: str = Field(..., description="Question number label")
    section: Optional[str] = Field(None, description="Section of the paper")
    question_text: str = Field(..., description="Cleaned question text")
    marks: Optional[int] = Field(None, description="Maximum marks for this node")
    images: List[str] = Field(default_factory=list, description="Relative paths to extracted diagrams/images")
    marking_guidelines: str = Field(..., description="Guidelines / solutions from the Mark Scheme")
    answer_key: Optional[str] = Field(None, description="Optional parsed concrete answer key")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Combined metadata for training ingestion")


class MergedDataset(BaseModel):
    """Pydantic model representing the final exportable structured dataset for a paper."""
    paper_id: str = Field(..., description="Unique identifier of the paper")
    board: str = Field(..., description="Exam board, e.g., 'AQA', 'CBSE'")
    subject: str = Field(..., description="Subject name")
    level: str = Field(..., description="Exam level")
    year: int = Field(..., description="Year of the exam")
    title: str = Field(..., description="Title of the paper")
    pairs: List[MergedQuestionAnswer] = Field(..., description="List of matched Question-Answer pairs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for arbitrary attributes")
