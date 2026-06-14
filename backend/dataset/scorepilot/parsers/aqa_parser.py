import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
import pdfplumber

from scorepilot.config import Config

logger = logging.getLogger("scorepilot.parsers.aqa_parser")


class AQAQuestionExtractor:
    """Specialized parser for AQA past exam papers to extract structured questions."""

    def __init__(self, config: Config):
        self.config = config
        
        # Matches spaced question numbers: e.g. "0 1 . 1", "1 0 . 2"
        self.sub_q_pattern = re.compile(r'^\s*([0-9])\s+([0-9])\s*\.\s*([0-9]+)\s*$')
        
        # Matches spaced main questions: e.g. "0 1", "1 0"
        self.main_q_pattern = re.compile(r'^\s*([0-9])\s+([0-9])\s*$')
        
        # Matches marks annotation: e.g. "[2 marks]"
        self.marks_pattern = re.compile(r'\[\s*([0-9]+)\s*marks?\s*\]', re.IGNORECASE)

    def extract_questions(self, pdf_path: Path, subject: str) -> List[Dict[str, Any]]:
        """Extracts structured questions from an AQA exam paper PDF.
        
        Args:
            pdf_path: Absolute path to the PDF.
            subject: Name of the subject (e.g. Biology, Chemistry).
            
        Returns:
            List of dictionaries matching the requested flat schema.
        """
        logger.info(f"Extracting questions from AQA paper: {pdf_path}")
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            return []

        doc_fitz = fitz.open(str(pdf_path))
        
        try:
            doc_plumber = pdfplumber.open(str(pdf_path))
        except Exception as e:
            logger.warning(f"pdfplumber failed to open PDF {pdf_path.name}: {e}. Table extraction will be disabled.")
            doc_plumber = None

        questions: List[Dict[str, Any]] = []
        
        # Parser state variables
        current_main_q_num: Optional[str] = None
        current_main_q_intro: List[str] = []
        current_sub_q: Optional[Dict[str, Any]] = None

        for page_idx in range(len(doc_fitz)):
            page_num = page_idx + 1
            page_fitz = doc_fitz[page_idx]
            
            # 1. Extract raw text from page
            text = page_fitz.get_text("text")
            raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
            
            # 2. Extract tables for this page if enabled
            tables: List[str] = []
            if self.config.parsers.extract_tables and doc_plumber:
                try:
                    page_plumber = doc_plumber.pages[page_idx]
                    raw_tables = page_plumber.extract_tables()
                    for t in raw_tables:
                        if self._is_valid_table(t):
                            tables.append(self._table_to_markdown(t))
                except Exception as e:
                    logger.warning(f"Failed to extract tables on page {page_num}: {e}")

            # 3. Filter page numbers, barcodes, and turn overs
            filtered_lines: List[str] = []
            for line in raw_lines:
                # Skip barcodes/page numbers
                if re.match(r'^\d+$', line) or re.match(r'^\*[a-zA-Z0-9\s]+\*$', line):
                    continue
                # Skip blank pages / turn overs
                if re.search(r'blank\s+page', line, re.IGNORECASE) or "do not write" in line.lower():
                    continue
                if "[turn over]" in line.lower():
                    continue
                filtered_lines.append(line)

            # 4. Sequentially insert table markdown strings after reference lines containing "table"
            final_lines: List[str] = []
            table_idx = 0
            for line in filtered_lines:
                final_lines.append(line)
                if "table" in line.lower() and table_idx < len(tables):
                    table_md = tables[table_idx]
                    for tbl_line in table_md.split("\n"):
                        if tbl_line.strip():
                            final_lines.append(tbl_line.strip())
                    table_idx += 1
            
            # Append any leftover tables at the end of the page
            while table_idx < len(tables):
                table_md = tables[table_idx]
                for tbl_line in table_md.split("\n"):
                    if tbl_line.strip():
                        final_lines.append(tbl_line.strip())
                table_idx += 1

            # 5. Page Transition Rule: Close completed sub-question if it already has its marks parsed
            if current_sub_q and current_sub_q["max_marks"] > 0:
                questions.append(self._format_output_question(current_sub_q, subject))
                current_sub_q = None

            # 6. Process page lines
            for line in final_lines:
                sub_q_match = self.sub_q_pattern.match(line)
                main_q_match = self.main_q_pattern.match(line)
                
                if sub_q_match:
                    if current_sub_q:
                        questions.append(self._format_output_question(current_sub_q, subject))
                    
                    g1, g2, g3 = sub_q_match.group(1), sub_q_match.group(2), sub_q_match.group(3)
                    q_num_clean = f"{g1}{g2}.{g3}"
                    if q_num_clean.startswith("0"):
                        q_num_clean = q_num_clean[1:]
                        
                    main_part = f"{g1}{g2}"
                    if current_main_q_num != main_part:
                        current_main_q_num = main_part
                        current_main_q_intro = []
                        
                    current_sub_q = {
                        "question_number": q_num_clean,
                        "intro": " ".join(current_main_q_intro).strip(),
                        "body": [],
                        "max_marks": 0
                    }
                    
                elif main_q_match:
                    if current_sub_q:
                        questions.append(self._format_output_question(current_sub_q, subject))
                        current_sub_q = None
                    g1, g2 = main_q_match.group(1), main_q_match.group(2)
                    current_main_q_num = f"{g1}{g2}"
                    current_main_q_intro = []
                    
                else:
                    if current_sub_q:
                        current_sub_q["body"].append(line)
                        marks_match = self.marks_pattern.search(line)
                        if marks_match:
                            current_sub_q["max_marks"] = int(marks_match.group(1))
                    elif current_main_q_num:
                        current_main_q_intro.append(line)

        # Close final sub-question if any
        if current_sub_q:
            questions.append(self._format_output_question(current_sub_q, subject))

        doc_fitz.close()
        if doc_plumber:
            doc_plumber.close()

        logger.info(f"Successfully processed AQA paper {pdf_path.name}. Extracted {len(questions)} questions.")
        return questions

    def _is_valid_table(self, table: Optional[List[List[Optional[str]]]]) -> bool:
        """Heuristic filter to check if a table is valid data rather than layout boxes."""
        if not table or len(table) < 2:
            return False
        has_text = False
        for row in table:
            for cell in row:
                if cell and len(cell.strip()) > 3:
                    has_text = True
                    break
            if has_text:
                break
        return has_text

    def _table_to_markdown(self, table: List[List[Optional[str]]]) -> str:
        """Converts a parsed tabular grid representation to clean markdown formatting."""
        cleaned_table: List[List[str]] = []
        for row in table:
            cleaned_row = []
            for cell in row:
                cleaned_row.append(cell.strip().replace("\n", " ") if cell else "")
            if any(cleaned_row):
                cleaned_table.append(cleaned_row)
                
        if not cleaned_table:
            return ""
            
        cols = len(cleaned_table[0])
        markdown_lines = []
        
        # Header row
        header = cleaned_table[0]
        markdown_lines.append("| " + " | ".join(header) + " |")
        
        # Separator row
        markdown_lines.append("| " + " | ".join(["---"] * cols) + " |")
        
        # Body rows
        for row in cleaned_table[1:]:
            padded_row = row + [""] * (cols - len(row))
            markdown_lines.append("| " + " | ".join(padded_row) + " |")
            
        return "\n" + "\n".join(markdown_lines) + "\n"

    def _format_output_question(self, q: Dict[str, Any], subject: str) -> Dict[str, Any]:
        """Converts internal question structures to flat output schema format."""
        body_text = " ".join(q["body"]).strip()
        
        # Normalize double spacing
        body_text = " ".join(body_text.split())
        intro_text = " ".join(q["intro"].split()).strip()
        
        # Combine intro context with question body text
        if intro_text:
            question_text = f"{intro_text}\n\n{body_text}"
        else:
            question_text = body_text

        return {
            "board": "AQA",
            "subject": subject,
            "question_number": q["question_number"],
            "question_text": question_text,
            "max_marks": q["max_marks"]
        }
