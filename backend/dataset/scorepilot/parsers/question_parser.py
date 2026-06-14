import logging
import re
from typing import Any, Dict, List, Optional
from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import ParsedDocument
from scorepilot.validators.schemas import ExamPaper, Question, SubQuestion

logger = logging.getLogger("scorepilot.parsers.question_parser")


class QuestionParser:
    """Parser to convert structured text blocks from PDFs into structured ExamPaper representations."""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Regex patterns to detect section headers
        self.section_pattern = re.compile(
            r'^\s*(SECTION|Section|PART|Part)\s+([A-Z0-9\-\b]+)', re.IGNORECASE
        )
        
        # Regex to detect question starts (e.g. "Q1", "1.", "01 ", "Question 5:")
        self.question_start_pattern = re.compile(
            r'^\s*(?:Question|Q)?\s*([0-9]+)\s*(?:\.|\:|\-|\s+|$)', re.IGNORECASE
        )
        
        # Regex to detect sub-questions (e.g. "(a)", "1.1", "1(a)", "ii)", "a)")
        self.sub_question_pattern = re.compile(
            r'^\s*(?:\()?([a-z]|[i|x|v]+|[0-9]+\.[0-9]+)\s*(?:\)|\.|\-|\s+|$)', re.IGNORECASE
        )
        
        # Regex to detect mark distributions: e.g. "[3 marks]", "(4)", "[5]", "3 marks"
        self.marks_pattern = re.compile(
            r'\[\s*([0-9]+)\s*(?:marks|mark)?\s*\]|\(\s*([0-9]+)\s*(?:marks|mark)?\s*\)', re.IGNORECASE
        )

    def parse(
        self,
        doc: ParsedDocument,
        subject: str,
        level: str,
        year: int,
        board: str,
        paper_code: Optional[str] = None,
        title: Optional[str] = None
    ) -> ExamPaper:
        """Parse the full text of a ParsedDocument into an ExamPaper model."""
        logger.info(f"Parsing Exam Paper: board={board}, subject={subject}, year={year}")
        
        paper_id = f"{board.lower()}-{subject.lower()}-{year}"
        if paper_code:
            paper_id += f"-{paper_code.lower()}"
            
        full_text = doc.full_text
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        
        questions: List[Question] = []
        current_section: Optional[str] = None
        current_question: Optional[Dict[str, Any]] = None
        current_sub_question: Optional[Dict[str, Any]] = None
        
        instructions_lines: List[str] = []
        parsing_instructions = True
        
        for line in lines:
            # Check for Section header
            sec_match = self.section_pattern.match(line)
            if sec_match:
                current_section = line
                parsing_instructions = False
                logger.debug(f"Detected Section: {current_section}")
                continue

            # Check if this line starts a new main question
            q_match = self.question_start_pattern.match(line)
            # Avoid matching decimal numbers inside standard sentences
            is_q_start = False
            if q_match:
                q_num_str = q_match.group(1)
                # Verify that it is not matching sub-questions or standard page text
                if len(line.split()) <= 15:  # Main questions starting headings are usually short
                    is_q_start = True
                elif not current_question:
                    is_q_start = True
            
            if is_q_start and q_match:
                q_num = q_match.group(1)
                parsing_instructions = False
                
                # Save previous question
                if current_question:
                    if current_sub_question:
                        current_question["sub_questions"].append(SubQuestion(**current_sub_question))
                        current_sub_question = None
                    questions.append(Question(**current_question))
                
                # Detect marks in this line
                marks = self._extract_marks(line)
                
                # Start new question context
                current_question = {
                    "id": f"{paper_id}-q{q_num}",
                    "question_number": q_num,
                    "section": current_section,
                    "question_text": line,
                    "marks": marks,
                    "sub_questions": [],
                    "images": [],
                    "metadata": {}
                }
                current_sub_question = None
                logger.debug(f"Parsing Question {q_num}")
                continue

            # Check for sub-question starts
            sub_match = self.sub_question_pattern.match(line)
            if sub_match and current_question:
                sub_num = sub_match.group(1)
                
                # If we were building a sub-question, save it
                if current_sub_question:
                    current_question["sub_questions"].append(SubQuestion(**current_sub_question))
                
                marks = self._extract_marks(line)
                
                current_sub_question = {
                    "id": f"{current_question['id']}-{sub_num}",
                    "sub_question_number": sub_num,
                    "question_text": line,
                    "marks": marks,
                    "images": [],
                    "metadata": {}
                }
                logger.debug(f"Parsing Sub-Question {sub_num} for Question {current_question['question_number']}")
                continue

            # Append text to appropriate node
            if parsing_instructions:
                instructions_lines.append(line)
            elif current_sub_question:
                current_sub_question["question_text"] += " " + line
                # Look for marks if not found yet
                if not current_sub_question["marks"]:
                    current_sub_question["marks"] = self._extract_marks(line)
            elif current_question:
                current_question["question_text"] += " " + line
                if not current_question["marks"]:
                    current_question["marks"] = self._extract_marks(line)

        # Save final remaining questions
        if current_question:
            if current_sub_question:
                current_question["sub_questions"].append(SubQuestion(**current_sub_question))
            questions.append(Question(**current_question))

        # Build paper object
        paper_title = title or f"{board} {subject} {year} Past Paper"
        paper = ExamPaper(
            paper_id=paper_id,
            board=board,
            subject=subject,
            level=level,
            year=year,
            paper_code=paper_code,
            title=paper_title,
            instructions=" ".join(instructions_lines) if instructions_lines else None,
            total_marks=sum((q.marks or 0) + sum(sq.marks or 0 for sq in q.sub_questions) for q in questions),
            questions=questions,
            metadata={"source_pdf": str(doc.file_path)}
        )
        
        logger.info(f"Parsing complete. Found {len(questions)} main questions, total marks: {paper.total_marks}")
        return paper

    def _extract_marks(self, text: str) -> Optional[int]:
        """Extract mark allocations from text strings."""
        match = self.marks_pattern.search(text)
        if match:
            # We check both capture groups since we support brackets and parentheses
            mark_val = match.group(1) or match.group(2)
            if mark_val:
                try:
                    return int(mark_val)
                except ValueError:
                    return None
        return None
