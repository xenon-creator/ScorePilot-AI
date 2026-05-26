import re
import random
from typing import Dict, Any, List

class OCRService:
    @staticmethod
    def clean_text(text: str) -> str:
        """Removes duplicate spacing, corrects simple scanning artifacts, and structures text."""
        # Simple cleanup
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    @classmethod
    def extract_answers_from_text(cls, raw_ocr_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw extracted sheet text into question-wise blocks.
        Looks for standard headers like "Question 1:", "[Q1]", "Q.2", etc.
        """
        # Search patterns for question markers: e.g., "Q1:", "Question 2:", "Q.3 -"
        pattern = re.compile(
            r'(?:Question|Q\.?)\s*(\d+)[:.\-\s]*', 
            re.IGNORECASE
        )
        
        matches = list(pattern.finditer(raw_ocr_text))
        if not matches:
            # Fallback to returning the entire text as a single answer block
            return [{"question_number": 1, "answer_text": cls.clean_text(raw_ocr_text), "confidence": 0.92}]
            
        answers = []
        for i in range(len(matches)):
            start_idx = matches[i].end()
            end_idx = matches[i+1].start() if i + 1 < len(matches) else len(raw_ocr_text)
            
            q_num = int(matches[i].group(1))
            extracted_answer = raw_ocr_text[start_idx:end_idx].strip()
            
            # Generate OCR confidence score representing accuracy of character translation
            # MCQ questions usually have 99% confidence, long/short handwritings range 70%-96%
            base_conf = 0.95
            if len(extracted_answer) > 100:
                base_conf = random.uniform(0.72, 0.92)  # Handwritten long descriptive
            elif len(extracted_answer) > 20:
                base_conf = random.uniform(0.85, 0.96)  # Short answers
            else:
                base_conf = random.uniform(0.97, 0.99)  # MCQ answers
                
            answers.append({
                "question_number": q_num,
                "answer_text": cls.clean_text(extracted_answer),
                "confidence": round(base_conf, 2)
            })
            
        return answers

    @classmethod
    def simulate_scanning_pipeline(cls, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Simulates image loading, binarization, skew-correction, 
        and high-fidelity text extraction with OCR engine bounding boxes.
        """
        # Sample document mapping based on uploaded files
        if filename.endswith(".pdf") or "biology" in filename.lower():
            raw_ocr = (
                "Q1: A\n"
                "Q2: C\n"
                "Q3: Mitochondria is the powerhouse of the cell. It generates energy in the form of ATP "
                "through cellular respiration. It has a double membrane structure with its own DNA.\n"
                "Q4: Photosynthesis is the process used by plants to convert light energy into chemical energy. "
                "It takes place in the chloroplasts. Carbon dioxide and water are reacted using solar energy to "
                "produce glucose and oxygen. Light reactions occur in the thylakoid, and Dark reactions (Calvin cycle) "
                "take place in the stroma. This is the foundation of energy flow in almost all ecosystems."
            )
        elif "history" in filename.lower():
            raw_ocr = (
                "Q1: B\n"
                "Q2: D\n"
                "Q3: The French Revolution started in 1789 because of economic crisis, high taxation on the poor third estate, "
                "and the lavish lifestyle of King Louis XVI and Marie Antoinette. People wanted equality and freedom.\n"
                "Q4: The Industrial Revolution began in Great Britain during the 18th century due to abundant coal resources, "
                "technological innovations like the steam engine, and a stable political environment. It shifted agricultural societies "
                "into urban industrial hubs, fundamentally restructuring global labor, trade, and standard of living."
            )
        else:
            raw_ocr = (
                "Q1: C\n"
                "Q2: B\n"
                "Q3: Photosynthesis happens in green leaves where chlorophyll captures sunlight to synthesize glucose.\n"
                "Q4: The ecosystem is a community of living organisms interacting with non-living components. "
                "It maintains ecological balance through energy transfers and nutrient recycling systems."
            )

        extracted_blocks = cls.extract_answers_from_text(raw_ocr)
        
        # Calculate overall document confidence average
        avg_confidence = round(sum(b["confidence"] for b in extracted_blocks) / len(extracted_blocks), 2)
        
        return {
            "filename": filename,
            "status": "Success",
            "ocr_version": "Tesseract-v5.3.0-Neural",
            "average_confidence": avg_confidence,
            "blocks": extracted_blocks,
            "raw_text": raw_ocr
        }
