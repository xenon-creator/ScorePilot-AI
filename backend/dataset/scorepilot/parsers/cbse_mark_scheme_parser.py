import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pdfplumber
from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import PDFParserEngine

logger = logging.getLogger("scorepilot.parsers.cbse_mark_scheme_parser")


class CBSEMarkSchemeExtractor:
    """Specialized parser for CBSE Class 12 Mark Schemes to extract structured marking guidelines."""

    def __init__(self, config: Config):
        self.config = config
        self.pdf_engine = PDFParserEngine(config)
        # Matches question numbers like '1', '20(I)', '31 (II)', '12.1', etc.
        self.q_num_pattern = re.compile(
            r'^\s*([0-9]+[A-Za-z0-9\.]*)\.?\s*$', re.IGNORECASE
        )

    def extract_mark_scheme(self, pdf_path: Path, subject: str) -> List[Dict[str, Any]]:
        """Parses a CBSE mark scheme PDF and extracts structured marking criteria.
        
        Args:
            pdf_path: Absolute path to the PDF.
            subject: Name of the subject.
            
        Returns:
            List of dictionaries matching the target output schema.
        """
        logger.info(f"Extracting mark schemes from CBSE document: {pdf_path}")
        items: List[Dict[str, Any]] = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                last_item: Optional[Dict[str, Any]] = None
                
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    tables = page.extract_tables()
                    extracted_from_tables = False
                    
                    for table in tables:
                        # Check if table fits the 3-column CBSE schema
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
                                
                                # Skip header row
                                clean_num_lower = q_num_clean.lower().replace(" ", "")
                                if clean_num_lower in ["q.no.", "q.no", "qno.", "qno", "q.no.?", "s.no.", "s.no"] or q_text_clean.lower() in ["answer", "answers", "questions", "question"]:
                                    continue
                                    
                                if q_num_clean:
                                    q_match = self.q_num_pattern.match(q_num_clean)
                                    if q_match:
                                        q_num = q_match.group(1)
                                        marks_val = self._parse_marks(q_marks_clean, q_text_clean)
                                        
                                        q_text_clean = self._normalize_text(q_text_clean)
                                        
                                        current_item = {
                                            "question_number": q_num,
                                            "mark_scheme": q_text_clean,
                                            "total_marks": marks_val
                                        }
                                        items.append(current_item)
                                        last_item = current_item
                                        extracted_from_tables = True
                                else:
                                    # Append subparts to the last active question
                                    if last_item and q_text_clean:
                                        q_text_clean = self._normalize_text(q_text_clean)
                                        last_item["mark_scheme"] += "\n" + q_text_clean
                                        
                                        if q_marks_clean:
                                            parsed_sub_marks = self._parse_marks(q_marks_clean, q_text_clean)
                                            # Accumulate and cap at CBSE maximum question weight
                                            last_item["total_marks"] = min(last_item["total_marks"] + parsed_sub_marks, 5)
                                            
                    # Fallback to text segmenter if no tables were parsed
                    if not extracted_from_tables:
                        logger.debug(f"Page {page_num} - falling back to text mark scheme segmenter.")
                        text_items = self._extract_from_text_fallback(page, page_num)
                        items.extend(text_items)
                        
            deduped_items = self._deduplicate_items(items)
            logger.info(f"Mark scheme extraction complete for {pdf_path.name}. Found {len(deduped_items)} items.")
            return deduped_items
            
        except Exception as e:
            logger.error(f"Error extracting CBSE mark scheme: {e}", exc_info=True)
            return []

    def _normalize_text(self, text: str) -> str:
        """Cleans whitespaces per line while preserving bullet points and layout structures."""
        lines = []
        for line in text.split("\n"):
            line_clean = " ".join(line.split()).strip()
            if line_clean:
                # Retain visual bullet formatting
                lines.append(line_clean)
        return "\n".join(lines)

    def _extract_from_text_fallback(self, page: pdfplumber.page.Page, page_num: int) -> List[Dict[str, Any]]:
        """Text-based segmenter for mark scheme guidelines when tables are absent."""
        text = page.extract_text()
        if not text:
            return []
            
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        items: List[Dict[str, Any]] = []
        
        current_item: Optional[Dict[str, Any]] = None
        
        q_start_regex = re.compile(r'^([0-9]+\s*(?:\(\s*[A-Za-z0-9_]+\s*\))?)\s*(?:\.|\-|\:|\))\s+', re.IGNORECASE)
        mark_regex = re.compile(r'[\(\[+]?\s*([0-9]+)\s*[\)\]+]$', re.IGNORECASE)
        
        for line in lines:
            if "marking scheme" in line.lower() or "class" in line.lower() or "assessment scheme" in line.lower():
                continue
                
            q_match = q_start_regex.match(line)
            if q_match and len(line.split()) <= 10:
                q_num = q_match.group(1)
                
                if current_item:
                    current_item["mark_scheme"] = self._normalize_text(current_item["mark_scheme"])
                    items.append(current_item)
                    
                current_item = {
                    "question_number": q_num,
                    "mark_scheme": line,
                    "total_marks": 0
                }
            elif current_item:
                current_item["mark_scheme"] += "\n" + line
                
                mark_match = mark_regex.match(line)
                if mark_match and len(line.split()) == 1:
                    current_item["total_marks"] = int(mark_match.group(1))

        if current_item:
            current_item["mark_scheme"] = self._normalize_text(current_item["mark_scheme"])
            items.append(current_item)
            
        return items

    def _deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates items keeping the longest text block for duplicate question numbers."""
        by_num: Dict[str, Dict[str, Any]] = {}
        for item in items:
            num = item["question_number"]
            
            # Filter likely page numbers
            try:
                num_val = int(num)
                if num_val > 40:
                    continue
            except ValueError:
                pass
                
            if num not in by_num:
                by_num[num] = item
            else:
                if len(item["mark_scheme"]) > len(by_num[num]["mark_scheme"]):
                    by_num[num] = item
                    
        def get_sort_key(d: Dict[str, Any]) -> Tuple[int, str]:
            num_str = d["question_number"]
            # Extract leading digit prefix
            match = re.match(r'^([0-9]+)', num_str)
            if match:
                return int(match.group(1)), num_str
            return 999, num_str
            
        return sorted(list(by_num.values()), key=get_sort_key)

    def _parse_marks(self, marks_str: str, text: str) -> int:
        """Parses marks values and sum expressions from CBSE documents."""
        marks_str = marks_str.strip().lower()
        if not marks_str:
            return self._estimate_marks_from_text(text)
            
        def parse_single(s: str) -> int:
            s = s.strip()
            if not s:
                return 0
            if s.isdigit():
                return int(s)
                
            s = re.sub(r'[\(\[\]\)]', '', s)
            if s.isdigit():
                return int(s)
                
            if '+' in s:
                return sum(parse_single(part) for part in s.split('+'))
                
            mul_match = re.match(r'^([0-9]+)\s*[x\*]\s*([0-9]+)$', s)
            if mul_match:
                return int(mul_match.group(1)) * int(mul_match.group(2))
                
            digit_match = re.search(r'([0-9]+)', s)
            if digit_match:
                return int(digit_match.group(1))
            return 0

        if '\n' in marks_str:
            lines = [line.strip() for line in marks_str.split('\n') if line.strip()]
            return max(parse_single(line) for line in lines)
            
        return parse_single(marks_str)

    def _estimate_marks_from_text(self, text: str) -> int:
        """Estimates marks from subparts listed in the mark scheme body text."""
        # Find all patterns of (1) or [2] etc.
        matches = re.findall(r'[\(\[]\s*([1-5])\s*[\)\]]', text)
        if matches:
            total = sum(int(m) for m in matches)
            return min(total, 5)
        return 0
