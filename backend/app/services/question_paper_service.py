import re
from app.services.ocr_service import OCRService

class QuestionPaperService:
    @staticmethod
    def extract_questions_from_paper(file_bytes: bytes, file_type: str) -> list[dict]:
        filename = f"question_paper.{file_type}"
        # Use existing simulate_scanning_pipeline which falls back gracefully if Tesseract is missing
        ocr_result = OCRService.simulate_scanning_pipeline(file_bytes, filename)
        text = ocr_result.get("raw_text") or ocr_result.get("extracted_text") or ""
        
        # Parse questions from the extracted text
        return parse_questions_from_text(text)

def parse_questions_from_text(text: str) -> list[dict]:
    # Look for question identifiers like Q1., 1., Question 1:, Q.1, Q 1
    # Matches lines starting with optional Question/Q prefix, followed by digits, then period, colon, hyphen, or spaces.
    pattern = re.compile(
        r'(?:^|\n)\s*(?:Question|Q\.?)\s*(\d+)(?:\b|[:.\-\s])|(?:^|\n)\s*(\d+)(?:\.|\s+)',
        re.IGNORECASE
    )
    
    matches = list(pattern.finditer(text))
    
    if not matches:
        return []
        
    questions = []
    for i in range(len(matches)):
        match = matches[i]
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        q_num_str = match.group(1) or match.group(2)
        if not q_num_str:
            continue
        q_num = int(q_num_str)
        
        q_text = text[start_idx:end_idx].strip()
        # Clean double spaces
        q_text = re.sub(r'\s+', ' ', q_text)
        
        # Look for marks hint: (X marks), [X marks], (X pts), [X], etc.
        marks_match = re.search(r'(?:\(|\[)\s*(\d+)\s*(?:marks?|pts?|points?)?\s*(?:\)|\])', q_text, re.IGNORECASE)
        if marks_match:
            marks_hint = int(marks_match.group(1))
            # Clean marks hint out of text
            q_text = q_text.replace(marks_match.group(0), "").strip()
            q_text = re.sub(r'\s+', ' ', q_text)
        else:
            marks_hint = 10
            
        questions.append({
            "question_number": q_num,
            "question_text": q_text,
            "marks_hint": marks_hint
        })
        
    return questions
