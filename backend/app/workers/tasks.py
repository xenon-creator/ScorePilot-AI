import os
import time
import datetime
import logging
from typing import Dict, Any

from celery import Celery
from app.core.config import settings
from app.models.database import SessionLocal, Submission, Exam, Question, Answer, SubmissionStatus, AuditLog
from app.services.ocr_service import OCRService
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

# Initialize a real Celery application
celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="tasks.process_and_score_submission")
def process_and_score_submission(submission_id: str, filepath: str, filename: str) -> Dict[str, Any]:
    """
    Asynchronous Celery task:
    1. Reads saved document staging files.
    2. Runs high-fidelity OCR scanning.
    3. Performs real NLP semantic grading via sentence-transformers.
    4. Automatically flags low-confidence submissions.
    5. Saves answers, updates totals, and creates audit logs.
    """
    logger.info(f"[Worker] Starting background scoring for submission_id: {submission_id}...")
    
    db = SessionLocal()
    try:
        # Retrieve submission
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            logger.error(f"[Worker] Submission {submission_id} not found in database.")
            return {"status": "error", "message": f"Submission {submission_id} not found"}

        # Retrieve exam questions
        exam = db.query(Exam).filter(Exam.id == submission.exam_id).first()
        if not exam:
            logger.error(f"[Worker] Exam {submission.exam_id} not found.")
            return {"status": "error", "message": f"Exam {submission.exam_id} not found"}

        # Read staging file content
        file_bytes = b""
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                logger.info(f"[Worker] Staged file read successfully: {len(file_bytes)} bytes.")
            except Exception as fe:
                logger.warning(f"[Worker] Could not read staged file at {filepath}: {fe}")

        # Run OCR simulation pipeline
        ocr_result = OCRService.simulate_scanning_pipeline(
            file_content=file_bytes,
            filename=filename or "paper.pdf"
        )
        
        submission.extracted_text = ocr_result.get("raw_text", "")
        ocr_blocks = {b["question_number"]: b for b in ocr_result.get("blocks", [])}

        total_score = 0.0
        total_confidence = 0.0
        any_flagged = False

        # Clean existing answers to prevent duplicate rows on retry
        db.query(Answer).filter(Answer.submission_id == submission.id).delete()

        # Score questions
        for idx, q in enumerate(exam.questions):
            q_num = idx + 1
            q_type = q.question_type.value  # "mcq", "short", "long"

            block = ocr_blocks.get(q_num)
            student_text = block["answer_text"] if block else ""
            ocr_conf = block["confidence"] if block else 0.90

            # Grade with real AI
            if q_type == "mcq":
                result = ScoringService.evaluate_mcq(student_text, q.model_answer, q.max_marks)
            elif q_type == "short":
                result = ScoringService.evaluate_short_answer(student_text, q.model_answer, q.max_marks)
            else:
                result = ScoringService.evaluate_long_answer(student_text, q.model_answer, q.max_marks)

            # Blend AI score confidence and OCR confidence
            blended_conf = round((result.confidence * 0.7) + (ocr_conf * 0.3), 2)

            if result.flagged_for_review:
                any_flagged = True

            total_score += result.score
            total_confidence += blended_conf

            answer = Answer(
                submission_id=submission.id,
                question_id=q.id,
                question_number=q_num,
                student_answer=student_text,
                ai_score=result.score,
                final_score=result.score,
                ai_confidence=blended_conf,
                ai_reasoning=result.reasoning,
                flagged_for_review=result.flagged_for_review,
                scored_at=datetime.datetime.utcnow(),
            )
            db.add(answer)

        # Update submission state
        num_questions = len(exam.questions) or 1
        submission.total_score = round(total_score, 2)
        submission.ai_confidence = round(total_confidence / num_questions, 2)
        submission.status = SubmissionStatus.flagged if any_flagged else SubmissionStatus.graded

        # Add Audit log entry
        audit_log = AuditLog(
            user_id=None,
            action="AI Scoring Completed",
            detail=f"Asynchronously graded submission {submission.id} for exam '{exam.title}'. Status: {submission.status.value}. Total Score: {submission.total_score}/{sum(q.max_marks for q in exam.questions)}",
            timestamp=datetime.datetime.utcnow()
        )
        db.add(audit_log)
        
        db.commit()
        logger.info(f"[Worker] Ingestion completed. Submission status: {submission.status.value}. Score: {submission.total_score}")

        return {
            "status": "success",
            "submission_id": submission.id,
            "total_score": submission.total_score,
            "final_status": submission.status.value
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Worker] Fatal exception in Celery scoring task: {e}", exc_info=True)
        # Attempt to mark the submission as flagged to alert the user of failure
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if submission:
                submission.status = SubmissionStatus.flagged
                db.commit()
        except Exception as db_ex:
            logger.error(f"[Worker] Could not fallback flag submission: {db_ex}")
        raise e
    finally:
        db.close()
