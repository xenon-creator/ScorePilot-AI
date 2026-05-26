import time
import random
from typing import Dict, Any
from app.services.ocr_service import OCRService
from app.services.scoring_service import ScoringService

# Simulating celery task structures
class CeleryAppSimulator:
    def __init__(self):
        self.tasks = {}

    def task(self, name: str):
        def decorator(func):
            self.tasks[name] = func
            return func
        return decorator

celery_app = CeleryAppSimulator()

@celery_app.task("tasks.process_and_score_submission")
def process_and_score_submission(submission_data: Dict[str, Any], exam_questions: list) -> Dict[str, Any]:
    """
    Asynchronous worker task:
    1. Triggers OCR raw scan extraction.
    2. Maps answers to exam questions.
    3. Runs MCQ, Short, and Long NLP AI scoring algorithms.
    4. Evaluates total marks and sets confidence flags.
    """
    print(f"[Worker] Starting ingestion for student {submission_data.get('student_name')}...")
    
    # 1. Simulate network and disk IO latency for document downloads
    time.sleep(1.5)
    
    # 2. Run OCR service
    ocr_result = OCRService.simulate_scanning_pipeline(
        file_content=b"pdf-binary-simulation",
        filename=submission_data.get("filename", "biology_final.pdf")
    )
    
    # 3. Match and score questions
    scored_items = []
    total_score = 0.0
    accumulated_confidence = 0.0
    
    ocr_blocks_map = {b["question_number"]: b for b in ocr_result["blocks"]}
    
    for q in exam_questions:
        q_num = q["question_number"]
        q_type = q["question_type"]
        max_marks = q["max_marks"]
        model_ans = q["model_answer"]
        rubrics = q.get("rubrics", [])
        keywords = q.get("keywords", [])
        
        # Get OCR answer
        ans_block = ocr_blocks_map.get(q_num)
        student_text = ans_block["answer_text"] if ans_block else ""
        ocr_conf = ans_block["confidence"] if ans_block else 0.90
        
        # Grade based on type
        if q_type == "MCQ":
            result = ScoringService.evaluate_mcq(student_text, model_ans, max_marks, negative_marking=0.25)
        elif q_type == "Short":
            result = ScoringService.evaluate_short_answer(student_text, model_ans, max_marks, keywords=keywords)
        else: # Long descriptive
            result = ScoringService.evaluate_long_answer(student_text, model_ans, max_marks, rubrics=rubrics)
            
        # Blended confidence including OCR accuracy
        blended_conf = round((result["confidence"] * 0.7) + (ocr_conf * 0.3), 2)
        
        scored_items.append({
            "question_id": q["id"],
            "question_number": q_num,
            "raw_score": result["score"],
            "ai_generated_score": result["score"],
            "ai_confidence": blended_conf,
            "feedback": result["feedback"],
            "criteria_matched": result["criteria_matched"]
        })
        
        total_score += result["score"]
        accumulated_confidence += blended_conf

    # 4. Check confidence boundaries to determine status
    avg_confidence = round(accumulated_confidence / len(exam_questions), 2) if exam_questions else 1.0
    
    # Flag submissions with confidence levels below 0.85 or with extremely low score segments
    status = "Scored"
    if avg_confidence < 0.85 or any(item["ai_confidence"] < 0.75 for item in scored_items):
        status = "Flagged"  # Redirect to Human review queues
        
    result_payload = {
        "submission_id": submission_data.get("id"),
        "student_name": submission_data.get("student_name"),
        "student_id": submission_data.get("student_id"),
        "total_score": round(total_score, 2),
        "ai_confidence": avg_confidence,
        "status": status,
        "extracted_text": ocr_result["raw_text"],
        "scores": scored_items
    }
    
    print(f"[Worker] Ingestion completed. Result: {status} (Score: {total_score}, Confidence: {avg_confidence})")
    return result_payload
