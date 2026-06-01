import os
import re
import uuid
import logging
from typing import List, Any
from sqlalchemy.orm import Session
from app.models.database import Submission, Answer, Exam, SubmissionStatus
from app.services.ocr_service import OCRService
from app.services.storage_service import upload_file_content
from app.workers.tasks import process_and_score_submission

logger = logging.getLogger(__name__)

def extract_student_name(text: str, filename: str) -> str:
    # Look for Name: X or Student: X in the first 5 lines
    lines = [line.strip() for line in text.split("\n") if line.strip()][:5]
    for line in lines:
        match = re.search(r'\b(?:Name|Student)\s*:\s*([^\n]+)', line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
    # Fallback: filename without extension
    base = os.path.basename(filename)
    name_fallback, _ = os.path.splitext(base)
    name_fallback = re.sub(r'[_\-]+', ' ', name_fallback)
    return name_fallback.strip()

def parse_answers_from_text(text: str, questions: list) -> dict:
    # Match patterns like: "Answer 1:", "Ans 1:", "Q1:", "1."
    pattern = re.compile(
        r'(?:^|\n)\s*(?:Answer|Ans|Q)?\s*(\d+)(?:[:.\-\s]+|\b)',
        re.IGNORECASE
    )
    
    matches = list(pattern.finditer(text))
    
    parsed = {}
    if not matches:
        # Fallback: whole text is question 1
        if questions:
            first_q = questions[0].question_number if hasattr(questions[0], 'question_number') else (questions[0].get('question_number') if isinstance(questions[0], dict) else 1)
            parsed[first_q] = text.strip()
        return parsed
        
    for i in range(len(matches)):
        match = matches[i]
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        q_num = int(match.group(1))
        ans_text = text[start_idx:end_idx].strip()
        parsed[q_num] = ans_text
        
    return parsed

def process_bulk_upload(files: List[Any], exam_id: str, db: Session) -> dict:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError(f"Exam {exam_id} not found")
        
    processed = 0
    failed = 0
    submissions = []
    
    for file in files:
        try:
            filename = file.filename
            file_bytes = file.file.read()
            # Reset seek position just in case
            file.file.seek(0)
            
            # 1. Upload to S3/MinIO
            object_key = f"uploads/{uuid.uuid4()}_{filename}"
            upload_file_content(
                file_bytes=file_bytes,
                object_key=object_key,
                content_type=file.content_type or "application/pdf"
            )
            
            # 2. Run OCR using existing OCR pipeline
            ocr_result = OCRService.simulate_scanning_pipeline(
                file_content=file_bytes,
                filename=filename,
                language=exam.language
            )
            raw_text = ocr_result.get("raw_text") or ocr_result.get("extracted_text") or ""
            
            # 3. Extract Name
            student_name = extract_student_name(raw_text, filename)
            
            # 4. Parse Answers
            parsed_answers = parse_answers_from_text(raw_text, exam.questions)
            
            # 5. Create Submission & Answer records in DB
            submission = Submission(
                exam_id=exam_id,
                student_name=student_name,
                student_id=student_name, # fallback student_id to name
                status=SubmissionStatus.pending,
                scanned_image_url=object_key,
                total_score=0.0,
                ai_confidence=0.0,
                extracted_text=raw_text,
            )
            db.add(submission)
            db.flush()
            
            # Add answers to DB
            for q in exam.questions:
                ans_text = parsed_answers.get(q.question_number, "")
                answer = Answer(
                    submission_id=submission.id,
                    question_id=q.id,
                    question_number=q.question_number,
                    student_answer=ans_text,
                    ai_score=0.0,
                    final_score=0.0,
                    ai_confidence=0.0,
                    ai_reasoning="Awaiting AI evaluation.",
                )
                db.add(answer)
                
            db.commit()
            
            # 6. Queue Celery task for background grading
            process_and_score_submission.delay(submission.id, object_key, filename)
            
            submissions.append(submission.id)
            processed += 1
        except Exception as e:
            db.rollback()
            failed += 1
            logger.error(f"Failed to process bulk upload file {getattr(file, 'filename', 'unknown')}: {e}", exc_info=True)
            
    return {
        "total": len(files),
        "processed": processed,
        "failed": failed,
        "submissions": submissions
    }
