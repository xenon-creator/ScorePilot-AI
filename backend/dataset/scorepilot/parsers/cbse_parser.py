import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import fitz
import pdfplumber
from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import PDFParserEngine

logger = logging.getLogger("scorepilot.parsers.cbse_parser")


class CBSEQuestionExtractor:
    """Specialized parser for CBSE Class 12 Question Papers to extract structured questions."""

    def __init__(self, config: Config):
        self.config = config
        self.pdf_engine = PDFParserEngine(config)
        self.q_num_pattern = re.compile(
            r'^\s*([0-9]+[A-Za-z0-9\.]*)\.?\s*$', re.IGNORECASE
        )
        self.marks_pattern = re.compile(r'^\s*[\(\[+]?\s*([0-9]+)\s*[\)\]+]?\s*$', re.IGNORECASE)

    def extract_questions(self, pdf_path: Path, subject: str) -> List[Dict[str, Any]]:
        """Extracts structured questions from a CBSE question paper PDF.
        
        Args:
            pdf_path: Absolute path to the PDF.
            subject: Name of the subject.
            
        Returns:
            List of dictionaries matching the requested schema.
        """
        logger.info(f"Extracting questions from CBSE paper: {pdf_path}")
        questions: List[Dict[str, Any]] = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                last_q: Optional[Dict[str, Any]] = None
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    
                    # 1. Try Table extraction first (extremely high accuracy for CBSE)
                    tables = page.extract_tables()
                    extracted_from_tables = False
                    
                    for table in tables:
                        # Validate if this looks like the main CBSE question table (usually 3 columns)
                        if table and len(table) >= 1 and len(table[0]) == 3:
                            extracted_from_tables = True
                            for row in table:
                                if not row or len(row) < 3:
                                    continue
                                    
                                q_num_raw = row[0]
                                q_text_raw = row[1]
                                q_marks_raw = row[2]
                                
                                if q_num_raw:
                                    q_num_clean = q_num_raw.replace("'", "").replace('"', "").replace("(", "").replace(")", "")
                                    q_num_clean = "".join(q_num_clean.split())
                                    # Remove dots followed by letters (e.g. 20.I -> 20I)
                                    q_num_clean = re.sub(r'\.(?=[A-Za-z])', '', q_num_clean)
                                else:
                                    q_num_clean = ""
                                q_text_clean = q_text_raw.strip() if q_text_raw else ""
                                q_marks_clean = q_marks_raw.strip() if q_marks_raw else ""
                                
                                # Skip header row using exact matches
                                clean_num_lower = q_num_clean.lower().replace(" ", "")
                                if clean_num_lower in ["q.no.", "q.no", "qno.", "qno", "q.no.?", "s.no.", "s.no"] or q_text_clean.lower() in ["question", "questions"]:
                                    continue
                                    
                                if q_num_clean:
                                    # Verify if column 0 contains a valid question number
                                    q_match = self.q_num_pattern.match(q_num_clean)
                                    if q_match:
                                        q_num = q_match.group(1)
                                        
                                        # Extract marks using helper
                                        marks_val = self._parse_marks(q_marks_clean, q_text_clean)
                                                
                                        # Filter visually impaired alternative duplicates
                                        q_text_clean = self._clean_question_text(q_text_clean)
                                        
                                        current_q = {
                                            "board": "CBSE",
                                            "subject": subject,
                                            "question_number": q_num,
                                            "question_text": q_text_clean,
                                            "max_marks": marks_val
                                        }
                                        questions.append(current_q)
                                        last_q = current_q
                                        extracted_from_tables = True
                                else:
                                    # Append subparts or options to the previous main question
                                    if last_q and q_text_clean:
                                        q_text_clean = self._clean_question_text(q_text_clean)
                                        last_q["question_text"] += " \n" + q_text_clean
                                        
                                        if q_marks_clean:
                                            parsed_sub_marks = self._parse_marks(q_marks_clean, q_text_clean)
                                            # If main question marks are 0 or less than the sum, accumulate
                                            last_q["max_marks"] = min(last_q["max_marks"] + parsed_sub_marks, 5)
                                    
                    # 2. Fallback to Regex layout parsing if tables did not extract main questions
                    if not extracted_from_tables:
                        logger.debug(f"No questions found via tables on page {page_num}. Falling back to text segmenter.")
                        text_questions = self._extract_from_text_fallback(page, subject, page_num)
                        questions.extend(text_questions)
                        
            # Deduplicate by question number (keep the first occurrence or longest text)
            deduped_questions = self._deduplicate_questions(questions)
            logger.info(f"Extraction complete for {pdf_path.name}. Found {len(deduped_questions)} questions.")
            return deduped_questions
            
        except Exception as e:
            logger.error(f"Error during CBSE PDF extraction for {pdf_path.name}: {e}", exc_info=True)
            return []

    def _clean_question_text(self, text: str) -> str:
        """Removes visually impaired student text blocks and cleans spaces."""
        # Split on visually impaired student separator
        parts = re.split(r'for\s+visually\s+impaired\s+students', text, flags=re.IGNORECASE)
        main_text = parts[0].strip()
        
        # Clean extra spaces
        main_text = " ".join(main_text.split())
        
        # Remove trailing hyphens/lines
        main_text = re.sub(r'[-\s_]{5,}$', '', main_text).strip()
        return main_text

    def _extract_from_text_fallback(self, page: pdfplumber.page.Page, subject: str, page_num: int) -> List[Dict[str, Any]]:
        """Fallback method using page layout text to segment questions via regex."""
        text = page.extract_text()
        if not text:
            return []
            
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        questions: List[Dict[str, Any]] = []
        
        current_q: Optional[Dict[str, Any]] = None
        
        # Matches question start lines: e.g. "25.", "25 - ", "25)" (requires trailing punctuation + space)
        q_start_regex = re.compile(r'^([0-9]+)\s*(?:\.|\-|\:|\))\s+', re.IGNORECASE)
        # Matches mark allocations at end of lines or sections: e.g. "3", "(3)", "[3]"
        mark_regex = re.compile(r'[\(\[+]?\s*([0-9]+)\s*[\)\]+]?$', re.IGNORECASE)
        
        for line in lines:
            # Skip page headers/footers
            if "sample question paper" in line.lower() or "class" in line.lower() or "assessment scheme" in line.lower():
                continue
                
            q_match = q_start_regex.match(line)
            # Avoid short matches or standard lines
            if q_match and len(line.split()) <= 10:
                q_num = q_match.group(1)
                
                # Save previous
                if current_q:
                    current_q["question_text"] = self._clean_question_text(current_q["question_text"])
                    questions.append(current_q)
                    
                current_q = {
                    "board": "CBSE",
                    "subject": subject,
                    "question_number": q_num,
                    "question_text": line,
                    "max_marks": 0
                }
            elif current_q:
                # Add to current question
                current_q["question_text"] += " " + line
                
                # Check if marks are specified on a line
                mark_match = mark_regex.match(line)
                if mark_match and len(line.split()) == 1:
                    current_q["max_marks"] = int(mark_match.group(1))

        if current_q:
            current_q["question_text"] = self._clean_question_text(current_q["question_text"])
            questions.append(current_q)
            
        return questions

    def _deduplicate_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates questions keeping the longest text block for duplicate question numbers."""
        by_num: Dict[str, Dict[str, Any]] = {}
        for q in questions:
            num = q["question_number"]
            # Exclude numbers that are likely page numbers
            try:
                num_val = int(num)
                if num_val > 40:  # CBSE papers usually have up to 33-35 questions
                    continue
            except ValueError:
                pass
                
            if num not in by_num:
                by_num[num] = q
            else:
                # Keep the one with longer text
                if len(q["question_text"]) > len(by_num[num]["question_text"]):
                    by_num[num] = q
                    
        # Sort by question number numerically
        def get_sort_key(q_dict: Dict[str, Any]) -> Tuple[int, str]:
            num_str = q_dict["question_number"]
            try:
                return int(num_str), ""
            except ValueError:
                return 999, num_str
                
        return sorted(list(by_num.values()), key=get_sort_key)

    def _parse_marks(self, marks_str: str, text: str) -> int:
        """Parses complex marks strings (e.g. '3+2', '2x1') or estimates them from text."""
        marks_str = marks_str.strip().lower()
        if not marks_str:
            return self._estimate_marks_from_text(text)
            
        def parse_single(s: str) -> int:
            s = s.strip()
            if not s:
                return 0
            if s.isdigit():
                return int(s)
            
            # Remove brackets/parentheses
            s = re.sub(r'[\(\[\]\)]', '', s)
            if s.isdigit():
                return int(s)
                
            # Handle addition '3+2'
            if '+' in s:
                return sum(parse_single(part) for part in s.split('+'))
                
            # Handle multiplication '2x1' or '2*1'
            mul_match = re.match(r'^([0-9]+)\s*[x\*]\s*([0-9]+)$', s)
            if mul_match:
                return int(mul_match.group(1)) * int(mul_match.group(2))
                
            # Fallback to first digit found
            digit_match = re.search(r'([0-9]+)', s)
            if digit_match:
                return int(digit_match.group(1))
            return 0

        if '\n' in marks_str:
            lines = [line.strip() for line in marks_str.split('\n') if line.strip()]
            # Take the maximum of alternative choices (e.g. Option A vs Option B)
            return max(parse_single(line) for line in lines)
            
        return parse_single(marks_str)

    def _estimate_marks_from_text(self, text: str) -> int:
        """Finds numbers in parentheses/brackets inside text and sums them to estimate marks."""
        # Find all patterns of (1) or [2] etc.
        matches = re.findall(r'[\(\[]\s*([1-5])\s*[\)\]]', text)
        if matches:
            total = sum(int(m) for m in matches)
            return min(total, 5)  # Cap at CBSE max question mark weight
        return 0

