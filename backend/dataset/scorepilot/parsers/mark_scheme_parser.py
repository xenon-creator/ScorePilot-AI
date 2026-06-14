import logging
import re
from typing import Any, Dict, List, Optional
import pdfplumber
from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import ParsedDocument
from scorepilot.validators.schemas import MarkScheme, MarkSchemeItem

logger = logging.getLogger("scorepilot.parsers.mark_scheme_parser")


class MarkSchemeParser:
    """Parser to convert structured text blocks from mark scheme PDFs into MarkScheme models."""

    def __init__(self, config: Config):
        self.config = config
        
        # Matches question identifier prefixes in marking guidelines: e.g. "Q1", "01.2", "1(a)", "2a", "3.1"
        self.item_prefix_pattern = re.compile(
            r'^\s*(?:Question|Q)?\s*([0-9]+(?:\([a-z]\)|[a-z]|[0-9]+\.[0-9]+|\.[0-9]+)?)\s*(?:\.|\:|\-|\s+|$)',
            re.IGNORECASE
        )
        
        # Matches common step/bullet patterns in mark schemes: e.g. "- award 1 mark for...", "* correct calculation"
        self.step_pattern = re.compile(r'^\s*[\-\*\•\d\+\u2022]\s+(.*)$')

    def parse(
        self,
        doc: ParsedDocument,
        subject: str,
        level: str,
        year: int,
        board: str,
        paper_code: Optional[str] = None
    ) -> MarkScheme:
        """Parse a mark scheme PDF's ParsedDocument into a structured MarkScheme model."""
        if board.upper() == "AQA":
            return self._parse_aqa(doc, subject, level, year, board, paper_code)
            
        logger.info(f"Parsing Mark Scheme: board={board}, subject={subject}, year={year}")
        
        paper_id = f"{board.lower()}-{subject.lower()}-{year}"
        if paper_code:
            paper_id += f"-{paper_code.lower()}"

        full_text = doc.full_text
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        items: List[MarkSchemeItem] = []
        current_item: Optional[Dict[str, Any]] = None

        for line in lines:
            prefix_match = self.item_prefix_pattern.match(line)
            # Ensure it is a short line prefix, avoiding false positives on sentence-starting numbers
            is_new_item = False
            if prefix_match:
                prefix = prefix_match.group(1)
                if len(line.split()) <= 10:
                    is_new_item = True
                elif not current_item:
                    is_new_item = True

            if is_new_item and prefix_match:
                q_num_label = prefix_match.group(1)
                
                # Save previous mark scheme item
                if current_item:
                    items.append(MarkSchemeItem(**current_item))
                
                # Standardize question matching ID
                q_id = self._generate_item_id(paper_id, q_num_label)
                
                current_item = {
                    "question_id": q_id,
                    "question_number": q_num_label,
                    "answer_key": self._detect_answer_key(line),
                    "marking_guidelines": line,
                    "steps": [],
                    "metadata": {}
                }
                
                logger.debug(f"Detected Mark Scheme Item for Question/Sub: {q_num_label}")
                continue

            # Process line content
            if current_item:
                # Append to main guidelines text
                current_item["marking_guidelines"] += " " + line
                
                # Try to extract bullet steps
                step_match = self.step_pattern.match(line)
                if step_match:
                    current_item["steps"].append(step_match.group(1).strip())
                    
                # Try to identify answer key if not set
                if not current_item["answer_key"]:
                    current_item["answer_key"] = self._detect_answer_key(line)

        # Append final item
        if current_item:
            items.append(MarkSchemeItem(**current_item))

        ms_obj = MarkScheme(
            paper_id=paper_id,
            board=board,
            subject=subject,
            level=level,
            year=year,
            paper_code=paper_code,
            items=items,
            metadata={"source_pdf": str(doc.file_path)}
        )
        
        logger.info(f"Mark Scheme parsing complete. Extracted {len(items)} items.")
        return ms_obj

    def _generate_item_id(self, paper_id: str, label: str) -> str:
        """Helper to align mark scheme item labels with question IDs.
        
        Examples:
            '1(a)' -> '{paper_id}-q1-a'
            '1.1'  -> '{paper_id}-q1-1'
            '2'    -> '{paper_id}-q2'
        """
        clean_label = label.lower().replace("(", "").replace(")", "").replace(".", "-")
        # Split main question and sub-question parts if combined
        # Let's say label is '1a' -> '1-a'
        match = re.match(r'^([0-9]+)([a-z]+)$', clean_label)
        if match:
            clean_label = f"{match.group(1)}-{match.group(2)}"
            
        return f"{paper_id}-q{clean_label}"

    def _detect_answer_key(self, text: str) -> Optional[str]:
        """Simple heuristic to detect key answers (e.g. MCQ options or single words)."""
        # Look for indicators like "Correct answer: A", "Answer is B", "Key: C"
        mcq_patterns = [
            r'(?:correct\s+)?answer\s*(?:is)?\s*\:?\s*\b([A-D])\b',
            r'\b(?:key|option)\b\s*\:?\s*\b([A-D])\b'
        ]
        for pattern in mcq_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _parse_aqa(
        self,
        doc: ParsedDocument,
        subject: str,
        level: str,
        year: int,
        board: str,
        paper_code: Optional[str] = None
    ) -> MarkScheme:
        """Specialized parsing logic for AQA mark schemes."""
        pdf_path = doc.file_path
        raw_items = []
        current_q_num = None
        
        text_q_pattern = re.compile(r'\bQuestion\s+(\d+(?:\.\d+)?)\b', re.IGNORECASE)
        
        def clean_text(text):
            if not text:
                return ""
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
            
        def parse_marks(mark_str):
            if not mark_str:
                return 0
            mark_str = mark_str.strip()
            
            range_match = re.search(r'(\d+)\s*[–-]\s*(\d+)', mark_str)
            if range_match:
                return int(range_match.group(2))
                
            digits = re.findall(r'\b\d+\b', mark_str)
            if digits:
                return sum(int(d) for d in digits)
                
            return 0

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_idx in range(len(pdf.pages)):
                    page_num = page_idx + 1
                    page = pdf.pages[page_idx]
                    
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        match = text_q_pattern.search(line)
                        if match:
                            val = match.group(1)
                            if val.startswith("0") and len(val) > 1 and val[1] != '.':
                                val = val[1:]
                            elif val.startswith("0") and len(val) > 2 and val[1] == '.':
                                val = val[2:]
                            
                            if val.startswith("0"):
                                val = val.lstrip("0")
                            if val == ".1":
                                val = "6.1"
                            elif val == ".2":
                                val = "6.2"
                            
                            val = val.replace("06.", "6.")
                            current_q_num = val
                    
                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables):
                        if not table or len(table) == 0:
                            continue
                            
                        is_header = False
                        if len(table[0]) >= 2:
                            c0 = str(table[0][0]).strip().lower() if table[0][0] else ""
                            c1 = str(table[0][1]).strip().lower() if table[0][1] else ""
                            if "question" in c0 and ("answer" in c1 or "answers" in c1):
                                is_header = True
                        if is_header:
                            continue
                            
                        c0 = str(table[0][0]).lower() if table[0][0] else ""
                        if "total" in c0 or "to tal" in c0 or "ta tal" in c0 or "tot al" in c0:
                            continue
                            
                        cols = len(table[0])
                        if cols < 3:
                            continue
                            
                        q_num_raw = table[0][0]
                        if q_num_raw:
                            q_num_clean = "".join(str(q_num_raw).split())
                            if re.match(r'^\d\d\.\d+$', q_num_clean) or re.match(r'^\d\d$', q_num_clean):
                                if q_num_clean.startswith("0"):
                                    q_num_clean = q_num_clean[1:]
                                current_q_num = q_num_clean
                        
                        if not current_q_num:
                            continue
                        
                        mark_scheme_parts = []
                        row_marks_list = []
                        is_level_of_response = False
                        
                        for row in table:
                            row = row + [None] * (cols - len(row))
                            
                            for cell in row:
                                if cell and re.search(r'\bLevel\s+\d+\b', str(cell), re.IGNORECASE):
                                    is_level_of_response = True
                                    
                            if cols == 5:
                                ans = row[1]
                                extra = row[2]
                                mrk = row[3]
                                
                                if ans:
                                    part_text = f"Answer: {clean_text(ans)}"
                                    if extra:
                                        part_text += f" | Extra info: {clean_text(extra)}"
                                    if mrk:
                                        part_text += f" [{clean_text(mrk)} marks]"
                                        row_marks_list.append(parse_marks(mrk))
                                    mark_scheme_parts.append(part_text)
                                    
                            elif cols == 4:
                                ans = row[1]
                                mrk = row[2]
                                
                                if ans:
                                    ans_clean = ans.strip()
                                    if mrk:
                                        part_text = f"{ans_clean} [{clean_text(mrk)} marks]"
                                        row_marks_list.append(parse_marks(mrk))
                                    else:
                                        part_text = ans_clean
                                    mark_scheme_parts.append(part_text)
                                    
                            elif cols == 3:
                                mrk_range = row[0]
                                desc_name = row[1]
                                desc_detail = row[2]
                                
                                if desc_name or desc_detail:
                                    is_level_of_response = True
                                    part_text = ""
                                    if desc_name:
                                        part_text += f"{clean_text(desc_name)}: "
                                    if desc_detail:
                                        part_text += clean_text(desc_detail)
                                    if mrk_range:
                                        part_text += f" [{clean_text(mrk_range)} marks]"
                                        row_marks_list.append(parse_marks(mrk_range))
                                    mark_scheme_parts.append(part_text)
                        
                        if is_level_of_response:
                            total_marks = max(row_marks_list) if row_marks_list else 0
                        else:
                            total_marks = sum(row_marks_list)
                            
                        if mark_scheme_parts:
                            raw_items.append({
                                "question_number": current_q_num,
                                "mark_scheme": "\n".join(mark_scheme_parts),
                                "marks": total_marks
                            })
        except Exception as e:
            logger.error(f"Error opening AQA mark scheme with pdfplumber: {e}")
            
        grouped = {}
        for item in raw_items:
            q_num = item["question_number"]
            if q_num not in grouped:
                grouped[q_num] = []
            grouped[q_num].append(item)
            
        merged_results = []
        def sort_key(k):
            if k.replace('.', '', 1).isdigit():
                return [float(k), k]
            return [999.0, k]
            
        sorted_keys = sorted(grouped.keys(), key=sort_key)
        
        paper_id = f"{board.lower()}-{subject.lower()}-{year}"
        if paper_code:
            paper_id += f"-{paper_code.lower()}"
            
        items = []
        for q_num in sorted_keys:
            group = grouped[q_num]
            text_blocks = [item["mark_scheme"] for item in group]
            marks = max(item["marks"] for item in group)
            
            mark_scheme_text = "\n\n".join(text_blocks)
            q_id = self._generate_item_id(paper_id, q_num)
            
            steps = [line.strip() for line in mark_scheme_text.split("\n") if line.strip()]
            answer_key = self._detect_answer_key(mark_scheme_text)
            
            items.append(MarkSchemeItem(
                question_id=q_id,
                question_number=q_num,
                answer_key=answer_key,
                marking_guidelines=mark_scheme_text,
                steps=steps,
                metadata={"marks": marks}
            ))
            
        ms_obj = MarkScheme(
            paper_id=paper_id,
            board=board,
            subject=subject,
            level=level,
            year=year,
            paper_code=paper_code,
            items=items,
            metadata={"source_pdf": str(pdf_path)}
        )
        return ms_obj

