import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import PDFParserEngine
from scorepilot.parsers.question_parser import QuestionParser
from scorepilot.parsers.mark_scheme_parser import MarkSchemeParser
from scorepilot.validators.validation import validate_merged_dataset
from scorepilot.validators.schemas import (
    ExamPaper,
    MarkScheme,
    MergedDataset,
    MergedQuestionAnswer,
    Question,
    SubQuestion,
)

logger = logging.getLogger("scorepilot.processors.orchestrator")


class PipelineOrchestrator:
    """Orchestrates PDF ingestion, parsing, matching, validation, and dataset generation."""

    def __init__(self, config: Config):
        self.config = config
        self.pdf_engine = PDFParserEngine(config)
        self.question_parser = QuestionParser(config)
        self.mark_scheme_parser = MarkSchemeParser(config)

    def process_pair(
        self,
        qp_pdf_path: Path,
        ms_pdf_path: Path,
        subject: str,
        level: str,
        year: int,
        board: str,
        paper_code: Optional[str] = None
    ) -> Tuple[bool, Optional[MergedDataset], Optional[str]]:
        """Parses a matching pair of Question Paper and Mark Scheme PDFs and merges them.
        
        Args:
            qp_pdf_path: Path to the Question Paper PDF file.
            ms_pdf_path: Path to the Mark Scheme PDF file.
            subject: Name of the subject.
            level: Exam level.
            year: Year of the exam.
            board: Exam board.
            paper_code: Code identifier.
            
        Returns:
            A tuple of (success_status, merged_dataset_instance, error_message)
        """
        logger.info(f"Processing paper pair: QP={qp_pdf_path.name}, MS={ms_pdf_path.name}")
        
        try:
            # 1. Parse PDFs to intermediate parsed page documents
            logger.info("Parsing Question Paper PDF...")
            qp_doc = self.pdf_engine.parse_pdf(qp_pdf_path)
            
            logger.info("Parsing Mark Scheme PDF...")
            ms_doc = self.pdf_engine.parse_pdf(ms_pdf_path)
            
            # 2. Parse structural text representations
            exam_paper: ExamPaper = self.question_parser.parse(
                qp_doc, subject, level, year, board, paper_code=paper_code
            )
            
            mark_scheme: MarkScheme = self.mark_scheme_pattern_parse(
                ms_doc, subject, level, year, board, paper_code=paper_code
            )
            
            # 3. Merge structures
            merged_dataset = self.merge(exam_paper, mark_scheme)
            
            # 4. Validate output schema
            success, validated_data, error_msg = validate_merged_dataset(merged_dataset.model_dump())
            if not success:
                logger.error(f"Merged dataset schema validation failed: {error_msg}")
                return False, None, f"Schema validation failure: {error_msg}"
                
            logger.info(f"Successfully merged and validated {qp_pdf_path.name} + {ms_pdf_path.name}")
            return True, validated_data, None  # type: ignore
            
        except Exception as e:
            logger.error(f"Failed to process pair: {e}", exc_info=True)
            return False, None, str(e)

    def mark_scheme_pattern_parse(
        self,
        doc: Any,
        subject: str,
        level: str,
        year: int,
        board: str,
        paper_code: Optional[str] = None
    ) -> MarkScheme:
        """Parse mark scheme from document."""
        return self.mark_scheme_parser.parse(
            doc, subject, level, year, board, paper_code=paper_code
        )

    def merge(self, paper: ExamPaper, ms: MarkScheme) -> MergedDataset:
        """Merges an ExamPaper and MarkScheme into a single validated MergedDataset structure."""
        logger.info(f"Merging exam paper questions with marking guidelines for {paper.paper_id}")
        
        # Build lookup table of marking items by question ID
        ms_lookup = {item.question_id: item for item in ms.items}
        
        merged_pairs: List[MergedQuestionAnswer] = []
        
        for q in paper.questions:
            # Case A: Question has sub-questions
            if q.sub_questions:
                for sq in q.sub_questions:
                    # Match sub-question directly
                    guidelines, answer_key = self._find_matching_guideline(sq.id, ms_lookup)
                    
                    merged_pairs.append(
                        MergedQuestionAnswer(
                            question_id=sq.id,
                            question_number=f"{q.question_number}({sq.sub_question_number})",
                            section=q.section,
                            question_text=f"{q.question_text} \nSub-Question: {sq.question_text}",
                            marks=sq.marks or q.marks,
                            images=sq.images or q.images,
                            marking_guidelines=guidelines,
                            answer_key=answer_key,
                            metadata={
                                "parent_question_id": q.id,
                                "is_sub_question": True
                            }
                        )
                    )
            else:
                # Case B: Standard main question with no children
                guidelines, answer_key = self._find_matching_guideline(q.id, ms_lookup)
                
                merged_pairs.append(
                    MergedQuestionAnswer(
                        question_id=q.id,
                        question_number=q.question_number,
                        section=q.section,
                        question_text=q.question_text,
                        marks=q.marks,
                        images=q.images,
                        marking_guidelines=guidelines,
                        answer_key=answer_key,
                        metadata={
                            "is_sub_question": False
                        }
                    )
                )

        # Build merged dataset
        dataset = MergedDataset(
            paper_id=paper.paper_id,
            board=paper.board,
            subject=paper.subject,
            level=paper.level,
            year=paper.year,
            title=paper.title,
            pairs=merged_pairs,
            metadata={
                "question_paper_pdf": paper.metadata.get("source_pdf"),
                "mark_scheme_pdf": ms.metadata.get("source_pdf"),
                "total_matched_questions": len(merged_pairs)
            }
        )
        return dataset

    def _find_matching_guideline(self, q_id: str, lookup: dict) -> Tuple[str, Optional[str]]:
        """Looks up guideline for a question ID, returning fallback string if missing."""
        if q_id in lookup:
            item = lookup[q_id]
            return item.marking_guidelines, item.answer_key
            
        # Try a fuzzy lookup (sometimes ID formatting differs slightly, e.g. q1a vs q1-a)
        # We replace hyphens and compare
        flat_id = q_id.replace("-", "")
        for k, item in lookup.items():
            if k.replace("-", "") == flat_id:
                logger.debug(f"Fuzzy matched {q_id} to mark scheme key {k}")
                return item.marking_guidelines, item.answer_key
                
        logger.warning(f"No mark scheme item found matching question ID: {q_id}")
        return "[Marking guidelines not found in mark scheme document]", None
