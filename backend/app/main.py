from dotenv import load_dotenv
load_dotenv()

import uuid
import json
import datetime
import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, RoleChecker, get_current_user_payload
from app.models.database import (
    get_db, User, Exam, Question, Submission, Answer, AuditLog, LMSSettings,
    UserRole, QuestionType, SubmissionStatus
)
from app.services.ocr_service import OCRService
from app.workers.tasks import process_and_score_submission
from app.services.lms_service import LMSService

try:
    from app.services.scoring_service import score_answer
    print("Scoring service loaded OK")
except Exception as e:
    print(f"WARNING: Scoring service failed to load: {e}")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables and columns exist in database
    try:
        from sqlalchemy import text
        from app.models.database import engine, Base
        Base.metadata.create_all(bind=engine)
        
        with engine.connect() as conn:
            if "sqlite" not in str(conn.engine.url):
                # Ensure all missing columns exist in PostgreSQL
                conn.execute(text("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS student_id VARCHAR;"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS raw_text TEXT;"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS extracted_text TEXT;"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS scanned_image_url VARCHAR;"))
                conn.commit()
                print("Database columns synchronized successfully on startup.")
    except Exception as db_err:
        import logging
        logging.getLogger(__name__).warning(f"Could not automatically synchronize db columns: {db_err}")

    try:
        from app.services.storage_service import ensure_bucket_exists
        ensure_bucket_exists()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error ensuring MinIO bucket exists on startup: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard connections
import os
from fastapi.middleware.cors import CORSMiddleware

# Read allowed origins from environment
raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
)

# Parse comma-separated list and clean whitespace
allowed_origins = [
    origin.strip() 
    for origin in raw_origins.split(",") 
    if origin.strip()
]

# Always add localhost for development
dev_origins = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://127.0.0.1:3000",
]

all_origins = list(set(allowed_origins + dev_origins))

print(f"CORS allowed origins: {all_origins}")  # log for debugging

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ==========================================
# PYDANTIC VALIDATION MODELS
# ==========================================
class LoginModel(BaseModel):
    email: EmailStr
    password: str

class SignUpModel(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "Teacher"
    student_id: Optional[str] = None

class RubricModel(BaseModel):
    criterion: str
    weight: float
    keywords: List[str]
    description: str

class QuestionCreateModel(BaseModel):
    question_number: int
    question_text: str
    question_type: str  # MCQ, Short, Long
    max_marks: float
    model_answer: str
    rubrics: Optional[List[RubricModel]] = None
    keywords: Optional[List[str]] = None

class ExamCreateModel(BaseModel):
    title: str
    subject: str
    code: str
    total_marks: int
    passing_marks: int
    questions: List[QuestionCreateModel]
    language: str = "en"

class QuestionFromPaperModel(BaseModel):
    text: str
    type: str  # MCQ, Short, Long
    max_marks: float
    model_answer: str

class ExamCreateFromPaperModel(BaseModel):
    title: str
    subject: str
    questions: List[QuestionFromPaperModel]
    language: str = "en"

class ReviewOverrideItemModel(BaseModel):
    question_number: int
    override_score: float
    override_reason: str

class ReviewSubmissionOverrideModel(BaseModel):
    submission_id: str
    overrides: List[ReviewOverrideItemModel]


class LMSSettingsCreateModel(BaseModel):
    lms_type: str  # "canvas" or "moodle"
    api_url: str
    api_token: str


class LMSSyncPayload(BaseModel):
    course_id: str
    assignment_id: str


class LMSPushModel(BaseModel):
    submission_id: str
    lms_type: str  # "moodle" or "canvas"


class CreateOrderModel(BaseModel):
    plan: str


class VerifyPaymentModel(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


class RazorpayStandardCreateOrderRequest(BaseModel):
    amount: int
    currency: str = "INR"
    receipt: Optional[str] = None


class RazorpayStandardVerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str



# ==========================================
# HELPERS
# ==========================================


ROLE_MAP = {
    "Admin": UserRole.admin, "admin": UserRole.admin,
    "Teacher": UserRole.teacher, "teacher": UserRole.teacher,
    "Reviewer": UserRole.reviewer, "reviewer": UserRole.reviewer,
    "Student": UserRole.student, "student": UserRole.student,
}

QTYPE_MAP = {
    "MCQ": QuestionType.mcq, "mcq": QuestionType.mcq,
    "Short": QuestionType.short, "short": QuestionType.short,
    "Long": QuestionType.long, "long": QuestionType.long,
}

def _role_display(role: UserRole) -> str:
    return role.value.capitalize()

def _qtype_display(qt: QuestionType) -> str:
    return {"mcq": "MCQ", "short": "Short", "long": "Long"}.get(qt.value, qt.value)

def _audit(db: Session, user_id: Optional[str], action: str, detail: dict):
    log = AuditLog(user_id=user_id, action=action, detail=json.dumps(detail))
    db.add(log)


def _format_exam(exam: Exam) -> dict:
    """Format an Exam ORM object to the response shape the frontend expects."""
    return {
        "id": exam.id,
        "title": exam.title,
        "subject": exam.description or "",
        "code": exam.title[:8].upper().replace(" ", "-") if exam.description is None else exam.description,
        "language": exam.language,
        "creator_id": exam.created_by,
        "total_marks": int(sum(q.max_marks for q in exam.questions)),
        "passing_marks": int(sum(q.max_marks for q in exam.questions) * 0.5),
        "status": "Active",
        "created_at": exam.created_at.isoformat() + "Z" if exam.created_at else "",
        "questions": [
            {
                "id": q.id,
                "question_number": idx + 1,
                "question_text": q.text,
                "question_type": _qtype_display(q.question_type),
                "max_marks": q.max_marks,
                "model_answer": q.model_answer,
                "rubrics": None,
                "keywords": None,
            }
            for idx, q in enumerate(exam.questions)
        ],
    }


def _format_submission(sub: Submission, exam: Optional[Exam] = None) -> dict:
    """Format a Submission ORM object to the response shape the frontend expects."""
    from app.services.storage_service import generate_presigned_view_url

    status_map = {
        SubmissionStatus.pending: "Pending",
        SubmissionStatus.graded: "Scored",
        SubmissionStatus.flagged: "Flagged",
        SubmissionStatus.reviewed: "Approved",
    }
    return {
        "id": sub.id,
        "exam_id": sub.exam_id,
        "student_id": sub.student_id or "",
        "student_name": sub.student_name,
        "scanned_image_url": generate_presigned_view_url(sub.scanned_image_url) if sub.scanned_image_url else "",
        "extracted_text": sub.extracted_text or "",
        "status": status_map.get(sub.status, "Scored"),
        "total_score": sub.total_score or 0.0,
        "ai_confidence": sub.ai_confidence or 0.0,
        "created_at": sub.uploaded_at.isoformat() + "Z" if sub.uploaded_at else "",
        "scores": [
            {
                "question_id": a.question_id,
                "question_number": a.question_number,
                "raw_score": a.ai_score or 0.0,
                "final_score": a.final_score or 0.0,
                "ai_generated_score": a.ai_score or 0.0,
                "ai_confidence": a.ai_confidence or 0.0,
                "feedback": a.ai_reasoning or "",
                "criteria_matched": {},
            }
            for a in sub.answers
        ],
        "reviewer_id": None,
        "reviewed_at": None,
    }


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"status": "online", "service": "AegisGrading AI API gateway", "time": str(datetime.datetime.now(datetime.UTC))}


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok", "service": "ScorePilot AI"}


@app.get("/cors-debug")
def cors_debug():
    return {
        "allowed_origins": all_origins,
        "env_value": os.getenv("ALLOWED_ORIGINS", "NOT SET")
    }


# --- AUTHENTICATION ---
@app.post("/api/v1/auth/signup")
def signup(data: SignUpModel, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    role = ROLE_MAP.get(data.role, UserRole.teacher)
    new_user = User(
        email=data.email,
        name=data.username,
        role=role,
        student_id=data.student_id if role == UserRole.student else None,
        password=hash_password(data.password),
    )
    db.add(new_user)
    db.flush()

    _audit(db, new_user.id, "User Signup", {"role": _role_display(role)})
    db.commit()

    token = create_access_token(data.username, _role_display(role))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": data.username,
            "role": _role_display(role),
            "student_id": new_user.student_id
        }
    }


@app.post("/api/v1/auth/login")
def login(data: LoginModel, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token(user.name, _role_display(user.role))

    _audit(db, user.id, "User Login", {"ip": "127.0.0.1"})
    db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.name,
            "role": _role_display(user.role),
            "student_id": user.student_id
        }
    }


@app.get("/api/v1/auth/me")
def get_me(payload: dict = Depends(get_current_user_payload), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    student_id = user.student_id if user else None
    return {"username": payload["sub"], "role": payload["role"], "student_id": student_id}


# --- EXAMS ---
@app.get("/api/v1/exams")
def get_exams(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    return [_format_exam(e) for e in exams]


@app.post("/api/v1/exams")
def create_exam(data: ExamCreateModel, db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    # Find the user
    creator = db.query(User).filter(User.name == payload["sub"]).first()
    creator_id = creator.id if creator else None
    if not creator_id:
        raise HTTPException(status_code=400, detail="Creator user not found")

    exam = Exam(
        title=data.title,
        description=data.subject,
        language=data.language,
        created_by=creator_id,
    )
    db.add(exam)
    db.flush()

    for q_data in data.questions:
        qtype = QTYPE_MAP.get(q_data.question_type, QuestionType.short)
        question = Question(
            exam_id=exam.id,
            text=q_data.question_text,
            question_type=qtype,
            model_answer=q_data.model_answer,
            max_marks=q_data.max_marks,
        )
        db.add(question)

    _audit(db, creator_id, "Exam Creation", {"exam_title": data.title, "questions_count": len(data.questions)})
    db.commit()
    db.refresh(exam)

    return _format_exam(exam)


@app.post("/api/v1/exams/upload-paper")
def upload_question_paper(
    file: UploadFile = File(...),
    payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))
):
    from app.services.question_paper_service import QuestionPaperService

    file_bytes = file.file.read()
    filename = file.filename or "paper.pdf"
    file_type = filename.split(".")[-1] if "." in filename else "pdf"
    
    try:
        questions = QuestionPaperService.extract_questions_from_paper(file_bytes, file_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract questions: {str(e)}")
        
    formatted_questions = [
        {
            "number": q["question_number"],
            "text": q["question_text"],
            "marks_hint": q["marks_hint"]
        }
        for q in questions
    ]
    return {"questions": formatted_questions}


@app.post("/api/v1/exams/from-paper")
def create_exam_from_paper(
    data: ExamCreateFromPaperModel,
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))
):
    creator = db.query(User).filter(User.name == payload["sub"]).first()
    creator_id = creator.id if creator else None
    if not creator_id:
        raise HTTPException(status_code=400, detail="Creator user not found")

    exam = Exam(
        title=data.title,
        description=data.subject,
        language=data.language,
        created_by=creator_id,
    )
    db.add(exam)
    db.flush()

    for idx, q_data in enumerate(data.questions):
        # Support various cases (MCQ, mcq, Short, short, Long, long)
        qtype = QTYPE_MAP.get(q_data.type, QTYPE_MAP.get(q_data.type.upper(), QuestionType.short))
        question = Question(
            exam_id=exam.id,
            text=q_data.text,
            question_type=qtype,
            model_answer=q_data.model_answer,
            max_marks=q_data.max_marks,
        )
        db.add(question)

    _audit(db, creator_id, "Exam Created From Paper", {"exam_title": data.title, "questions_count": len(data.questions)})
    db.commit()
    db.refresh(exam)

    return _format_exam(exam)


# --- UPLOADS & SCORING ---
@app.post("/api/v1/uploads")
async def upload_papers(
    student_name: str = Form(...),
    exam_id: str = Form(...),
    student_id: Optional[str] = Form(None),
    question_number: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    from app.services.subscription_service import check_usage_limit, increment_usage
    import uuid, datetime
    from app.models.database import Submission, Question, Answer
    from app.services.scoring_service import score_answer

    # 1. Retrieve current user and check subscription usage limit
    current_user = db.query(User).filter(User.name == payload["sub"]).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        usage = check_usage_limit(current_user.id, db)
    except Exception as e:
        print(f"Subscription check failed: {e}")
        usage = {"can_grade": True, "papers_used": 0, "papers_limit": 5, "upgrade_required": False}

    if not usage["can_grade"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "usage_limit_reached",
                "message": "You've used all 5 free papers this month. Upgrade to continue.",
                "papers_used": usage["papers_used"],
                "papers_limit": usage["papers_limit"]
            }
        )

    # 2. Extract text from file if provided
    extracted_text = ""
    scanned_image_url = ""
    filename = file.filename if file else ""
    if file and file.filename:
        try:
            contents = await file.read()
            # Perform OCR using the file content and name
            from app.services.ocr_service import OCRService
            res = OCRService.extract_text(contents, file.filename)
            extracted_text = res.get("extracted_text", "")
            
            # Save local copy reference
            scanned_image_url = f"uploads/{uuid.uuid4()}_{file.filename}"
        except Exception as e:
            print(f"OCR failed: {e}")
            extracted_text = student_name  # fallback

    # 3. Create submission in database
    submission = Submission(
        id=str(uuid.uuid4()),
        exam_id=exam_id,
        student_name=student_name,
        student_id=student_id or "",
        status=SubmissionStatus.pending,
        total_score=0.0,
        ai_confidence=0.0,
        extracted_text=extracted_text,
        raw_text=extracted_text,
        scanned_image_url=scanned_image_url,
        uploaded_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 4. Get questions for this exam
    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).all()

    if not questions:
        submission.status = SubmissionStatus.graded
        db.commit()
    else:
        # Score each question
        total_score = 0.0
        total_confidence = 0.0
        any_flagged = False

        for i, question in enumerate(questions):
            try:
                q_type = question.question_type.value \
                         if hasattr(question.question_type, 'value') \
                         else str(question.question_type)
                
                result = score_answer(
                    student_answer=extracted_text or f"Answer by {student_name}",
                    model_answer=question.model_answer or "",
                    question_type=q_type,
                    max_marks=float(question.max_marks or 10)
                )

                answer = Answer(
                    id=str(uuid.uuid4()),
                    submission_id=submission.id,
                    question_id=question.id,
                    question_number=i + 1,
                    student_answer=(extracted_text or student_name)[:500],
                    ai_score=float(result.get('score', 0)),
                    final_score=float(result.get('score', 0)),
                    ai_confidence=float(result.get('confidence', 0)),
                    ai_reasoning=str(result.get('reasoning', '')),
                    flagged_for_review=bool(result.get('flagged_for_review', False)),
                    scored_at=datetime.datetime.now(datetime.UTC)
                )
                db.add(answer)

                total_score += float(result.get('score', 0))
                total_confidence += float(result.get('confidence', 0))
                if result.get('flagged_for_review'):
                    any_flagged = True

            except Exception as e:
                print(f"Error scoring question {i}: {e}")

        n = max(len(questions), 1)
        submission.total_score = round(total_score, 2)
        submission.ai_confidence = round(total_confidence / n, 2)
        submission.status = SubmissionStatus.flagged if any_flagged else SubmissionStatus.graded
        db.commit()

    # Log initial submission upload event
    try:
        _audit(db, current_user.id, "Submission Uploaded", {
            "submission_id": submission.id,
            "student_name": submission.student_name,
            "filename": filename,
        })
        db.commit()
    except Exception as audit_err:
        print(f"Audit log failed: {audit_err}")

    # Increment subscription usage count
    try:
        increment_usage(current_user.id, db)
    except Exception as e:
        print(f"Subscription increment failed: {e}")

    # Return standard formatted response combined with specific keys from user's template
    formatted = _format_submission(submission)
    response_data = {
        "submission_id": submission.id,
        "student_name": submission.student_name,
        "status": submission.status.value if hasattr(submission.status, 'value') else str(submission.status),
        "total_score": submission.total_score,
        "ai_confidence": submission.ai_confidence,
        "message": "Graded successfully"
    }
    response_data.update(formatted)
    # Ensure both submission_id and message are preserved in the response dict
    response_data["submission_id"] = submission.id
    response_data["message"] = "Graded successfully"
    return response_data




BULK_JOBS = {}

@app.post("/api/v1/uploads/bulk")
def upload_bulk_submissions(
    exam_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))
):
    from app.services.bulk_upload_service import process_bulk_upload

    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Cannot upload more than 50 files in a single batch.")
        
    try:
        result = process_bulk_upload(files, exam_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk upload failed: {str(e)}")
        
    job_id = str(uuid.uuid4())
    BULK_JOBS[job_id] = {
        "submission_ids": result["submissions"],
        "total": len(files)
    }
    
    return {
        "job_id": job_id,
        "total": result["total"],
        "processed": result["processed"],
        "failed": result["failed"],
        "submission_ids": result["submissions"]
    }


@app.get("/api/v1/uploads/bulk/status/{job_id}")
def get_bulk_upload_status(
    job_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))
):
    job = BULK_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bulk upload job not found")
        
    submission_ids = job["submission_ids"]
    total = job["total"]
    
    # Query database to count how many are processed
    # Processed means status != 'pending'
    processed = db.query(Submission).filter(
        Submission.id.in_(submission_ids),
        Submission.status != SubmissionStatus.pending
    ).count()
    
    status_str = "processing"
    if processed == total:
        status_str = "complete"
    elif len(submission_ids) == 0:
        status_str = "failed"
        
    return {
        "status": status_str,
        "processed": processed,
        "total": total
    }


@app.get("/api/v1/submissions")
def list_submissions(exam_id: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        query = db.query(Submission)
        if exam_id:
            query = query.filter(Submission.exam_id == exam_id)
        subs = query.order_by(Submission.uploaded_at.desc()).all()
        return [_format_submission(s) for s in subs]
    except Exception as e:
        print(f"Submissions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/student/submissions")
def list_student_submissions(
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Student"]))
):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student profile not found")

    from sqlalchemy import or_
    filters = []
    if user.student_id:
        filters.append(Submission.student_id == user.student_id)
    filters.append(Submission.student_name == user.name)
    filters.append(Submission.student_id == user.email)

    subs = db.query(Submission).filter(or_(*filters)).order_by(Submission.uploaded_at.desc()).all()
    return [_format_submission(s) for s in subs]


# --- HUMAN IN THE LOOP REVIEW ---
@app.post("/api/v1/review/override")
def override_scores(
    data: ReviewSubmissionOverrideModel,
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Teacher", "Reviewer", "Admin"])),
):
    submission = db.query(Submission).filter(Submission.id == data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    reviewer = db.query(User).filter(User.name == payload["sub"]).first()
    reviewer_id = reviewer.id if reviewer else None

    audit_overrides = []
    total_override_score = 0.0

    for ov in data.overrides:
        answer = next(
            (a for a in submission.answers if a.question_number == ov.question_number),
            None
        )
        if not answer:
            raise HTTPException(status_code=400, detail=f"Question {ov.question_number} not found in scores list")

        old_score = answer.final_score or answer.ai_score or 0.0
        answer.final_score = ov.override_score
        answer.ai_reasoning = (answer.ai_reasoning or "") + f" [Override: {ov.override_reason}]"
        answer.overridden_by = reviewer_id

        audit_overrides.append({
            "question_number": ov.question_number,
            "old_score": old_score,
            "new_score": ov.override_score,
            "reason": ov.override_reason,
        })
        total_override_score += ov.override_score

    # Recalculate total (overridden + untouched)
    override_qnums = {ov.question_number for ov in data.overrides}
    untouched_score = sum(
        (a.final_score or a.ai_score or 0.0)
        for a in submission.answers
        if a.question_number not in override_qnums
    )
    submission.total_score = round(untouched_score + total_override_score, 2)
    submission.status = SubmissionStatus.reviewed

    _audit(db, reviewer_id, "Human Grading Override", {
        "submission_id": data.submission_id,
        "student_name": submission.student_name,
        "changes": audit_overrides,
        "new_total": submission.total_score,
    })
    db.commit()
    db.refresh(submission)

    # Trigger async score release email notification task
    from app.workers.tasks import send_score_release_email_task
    send_score_release_email_task.delay(submission.id)

    result = _format_submission(submission)
    result["reviewer_id"] = payload["sub"]
    result["reviewed_at"] = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
    return result


@app.post("/api/v1/admin/regrade-pending")
def regrade_pending(db: Session = Depends(get_db)):
    from app.models.database import Submission, Question, Answer
    from app.services.scoring_service import score_answer
    import uuid, datetime
    
    pending = db.query(Submission).filter(
        Submission.status == 'pending'
    ).all()
    
    regraded = 0
    for sub in pending:
        try:
            questions = db.query(Question).filter(
                Question.exam_id == sub.exam_id
            ).all()
            
            db.query(Answer).filter(
                Answer.submission_id == sub.id
            ).delete()
            
            total_score = 0.0
            total_confidence = 0.0
            any_flagged = False
            
            for i, q in enumerate(questions):
                try:
                    q_type = q.question_type.value \
                             if hasattr(q.question_type, 'value') \
                             else str(q.question_type)
                    result = score_answer(
                        student_answer=sub.student_name or "student",
                        model_answer=q.model_answer or "",
                        question_type=q_type,
                        max_marks=float(q.max_marks or 10)
                    )
                    answer = Answer(
                        id=str(uuid.uuid4()),
                        submission_id=sub.id,
                        question_id=q.id,
                        question_number=i+1,
                        student_answer=sub.student_name or "student",
                        ai_score=float(result.get('score',0)),
                        final_score=float(result.get('score',0)),
                        ai_confidence=float(result.get('confidence',0)),
                        ai_reasoning=str(result.get('reasoning','')),
                        flagged_for_review=bool(
                            result.get('flagged_for_review',False)),
                        scored_at=datetime.datetime.now(datetime.UTC)
                    )
                    db.add(answer)
                    total_score += float(result.get('score',0))
                    total_confidence += float(result.get('confidence',0))
                    if result.get('flagged_for_review'):
                        any_flagged = True
                except Exception as e:
                    print(f"Score error: {e}")
            
            n = max(len(questions), 1)
            sub.total_score = round(total_score, 2)
            sub.ai_confidence = round(total_confidence/n, 2)
            sub.status = 'flagged' if any_flagged else 'graded'
            db.commit()
            regraded += 1
        except Exception as e:
            print(f"Regrade error for {sub.id}: {e}")
            db.rollback()
    
    return {"success": True, "regraded": regraded,
            "total": len(pending)}


# --- ANALYTICS ---
@app.get("/api/v1/analytics")
def get_analytics(exam_id: str, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    subs = db.query(Submission).filter(Submission.exam_id == exam_id).all()
    total_marks = sum(q.max_marks for q in exam.questions)

    scores_list = [s.total_score or 0.0 for s in subs]
    avg_score = round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
    pass_threshold = total_marks * 0.5
    pass_count = sum(1 for s in scores_list if s >= pass_threshold)
    fail_count = len(scores_list) - pass_count

    # Score distribution slots
    distribution = {"0-25%": 0, "26-50%": 0, "51-75%": 0, "76-100%": 0}
    for s in scores_list:
        pct = (s / total_marks) * 100 if total_marks else 0
        if pct <= 25:
            distribution["0-25%"] += 1
        elif pct <= 50:
            distribution["26-50%"] += 1
        elif pct <= 75:
            distribution["51-75%"] += 1
        else:
            distribution["76-100%"] += 1

    # Question difficulty
    question_difficulty = []
    for idx, q in enumerate(exam.questions):
        q_num = idx + 1
        q_scores = []
        for s in subs:
            ans = next((a for a in s.answers if a.question_number == q_num), None)
            if ans:
                q_scores.append(ans.final_score or ans.ai_score or 0.0)
        avg_q = sum(q_scores) / len(q_scores) if q_scores else 0.0
        diff_pct = round((avg_q / q.max_marks) * 100, 2) if q.max_marks else 0.0
        question_difficulty.append({
            "question_number": q_num,
            "difficulty_percentage": diff_pct,
            "question_text_short": q.text[:40] + "...",
        })

    return {
        "exam_id": exam_id,
        "exam_title": exam.title,
        "papers_processed": len(subs),
        "average_score": avg_score,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "score_distribution": distribution,
        "question_difficulty": question_difficulty,
    }


# --- EXPORTS ---
@app.get("/api/v1/exams/{exam_id}/export/csv")
def export_exam_csv(
    exam_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(RoleChecker(["Teacher", "Reviewer", "Admin"]))
):
    from fastapi.responses import StreamingResponse
    from app.services.export_service import ExportService
    
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    submissions = db.query(Submission).filter(Submission.exam_id == exam_id).order_by(Submission.uploaded_at.desc()).all()
    
    csv_generator = ExportService.generate_submissions_csv_generator(exam, submissions)
    
    filename = f"exam_{exam_id}_grades.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(csv_generator, media_type="text/csv", headers=headers)


@app.get("/api/v1/submissions/{submission_id}/export/pdf")
def export_submission_pdf(
    submission_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload)
):
    from fastapi import Response
    from app.services.export_service import ExportService
    
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    exam = db.query(Exam).filter(Exam.id == submission.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    # Enforce Student Ownership check
    user_role = payload.get("role")
    if user_role == "Student":
        user = db.query(User).filter(User.name == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User profile not found")
            
        is_owner = False
        if submission.student_id == user.student_id:
            is_owner = True
        elif submission.student_name == user.name:
            is_owner = True
        elif submission.student_id == user.email:
            is_owner = True
            
        if not is_owner:
            raise HTTPException(status_code=403, detail="Access denied: You can only export your own exam results.")
            
    pdf_bytes = ExportService.generate_student_pdf_bytes(submission, exam)
    
    filename = f"submission_{submission_id}_report.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


# --- AUDIT LOGS ---
@app.get("/api/v1/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Admin", "Moderator", "Teacher"]))):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    result = []
    for log in logs:
        detail = {}
        if log.detail:
            try:
                detail = json.loads(log.detail)
            except (json.JSONDecodeError, TypeError):
                detail = {"raw": log.detail}
        result.append({
            "id": f"aud-{log.id}",
            "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else "",
            "user": log.user.name if log.user else "system",
            "action": log.action,
            "details": detail,
        })
    return result


# --- LMS INTEGRATION ---
@app.get("/api/v1/lms/settings")
def get_lms_settings(db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    settings_rec = db.query(LMSSettings).filter(LMSSettings.user_id == user.id, LMSSettings.is_active == True).first()
    if not settings_rec:
        return {"configured": False}
    
    return {
        "configured": True,
        "lms_type": settings_rec.lms_type,
        "api_url": settings_rec.api_url,
        "api_token": "********"  # Hide token for security
    }


@app.post("/api/v1/lms/settings")
def save_lms_settings(data: LMSSettingsCreateModel, db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    # Deactivate existing settings
    db.query(LMSSettings).filter(LMSSettings.user_id == user.id).update({"is_active": False})
    
    new_settings = LMSSettings(
        user_id=user.id,
        lms_type=data.lms_type,
        api_url=data.api_url,
        api_token=data.api_token,
        is_active=True
    )
    db.add(new_settings)
    
    _audit(db, user.id, "LMS Settings Configured", {"lms_type": data.lms_type, "api_url": data.api_url})
    db.commit()
    return {"status": "success", "message": "LMS settings saved successfully"}


@app.get("/api/v1/lms/courses")
def get_lms_courses(db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    settings_rec = db.query(LMSSettings).filter(LMSSettings.user_id == user.id, LMSSettings.is_active == True).first()
    if not settings_rec:
        raise HTTPException(status_code=400, detail="LMS connection not configured.")
        
    courses = LMSService.sync_courses(
        lms_type=settings_rec.lms_type,
        api_url=settings_rec.api_url,
        api_token=settings_rec.api_token
    )
    
    # Retrieve assignments for each course to make frontend rendering seamless
    result = []
    for course in courses:
        try:
            assigns = LMSService.sync_assignments(
                lms_type=settings_rec.lms_type,
                api_url=settings_rec.api_url,
                api_token=settings_rec.api_token,
                course_id=course["id"]
            )
        except Exception:
            assigns = []
        result.append({
            "id": course["id"],
            "name": course["name"],
            "code": course["code"],
            "assignments": assigns
        })
    return result


@app.post("/api/v1/exams/{exam_id}/sync-lms")
def sync_exam_grades_to_lms(exam_id: str, data: LMSSyncPayload, db: Session = Depends(get_db), payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    settings_rec = db.query(LMSSettings).filter(LMSSettings.user_id == user.id, LMSSettings.is_active == True).first()
    if not settings_rec:
        raise HTTPException(status_code=400, detail="LMS connection not configured.")
        
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    # Gather scored submissions
    submissions = db.query(Submission).filter(
        Submission.exam_id == exam_id,
        Submission.status == SubmissionStatus.graded
    ).all()
    
    if not submissions:
        raise HTTPException(status_code=400, detail="No scored submissions found for this exam.")
        
    # Standardize grade payloads
    grades_payload = []
    for sub in submissions:
        student_identifier = sub.student_id or sub.student_name
        feedback_notes = f"ScorePilot AI evaluation completed for {exam.title}."
        grades_payload.append({
            "student_id": student_identifier,
            "grade": sub.total_score or 0.0,
            "feedback": feedback_notes
        })
        
    sync_result = LMSService.sync_grades(
        lms_type=settings_rec.lms_type,
        api_url=settings_rec.api_url,
        api_token=settings_rec.api_token,
        course_id=data.course_id,
        assignment_id=data.assignment_id,
        grades_data=grades_payload
    )
    
    _audit(
        db, user.id, "LMS Grades Synchronized",
        {
            "exam_id": exam_id,
            "exam_title": exam.title,
            "course_id": data.course_id,
            "assignment_id": data.assignment_id,
            "synced_count": len(grades_payload),
            "lms_type": settings_rec.lms_type
        }
    )
    db.commit()
    
    return sync_result


@app.get("/api/v1/student/results")
def get_student_results(
    student_name: str,
    db: Session = Depends(get_db)
):
    if not student_name or not student_name.strip():
        raise HTTPException(status_code=400, detail="Student name parameter is required")

    from sqlalchemy import func
    subs = db.query(Submission).filter(
        func.lower(Submission.student_name) == student_name.strip().lower()
    ).order_by(Submission.uploaded_at.desc()).all()

    results = []
    for sub in subs:
        exam = db.query(Exam).filter(Exam.id == sub.exam_id).first()
        exam_title = exam.title if exam else "Unknown Exam"
        
        answers_list = []
        for ans in sorted(sub.answers, key=lambda a: a.question_number):
            question = db.query(Question).filter(Question.id == ans.question_id).first()
            q_text = question.text if question else f"Question {ans.question_number}"
            max_m = question.max_marks if question else 0.0
            
            answers_list.append({
                "question_number": ans.question_number,
                "question_text": q_text,
                "student_answer": ans.student_answer,
                "ai_score": ans.ai_score,
                "final_score": ans.final_score,
                "ai_confidence": ans.ai_confidence,
                "ai_reasoning": ans.ai_reasoning or "No reasoning provided.",
                "max_marks": max_m
            })
            
        results.append({
            "submission_id": sub.id,
            "exam_title": exam_title,
            "student_name": sub.student_name,
            "status": sub.status.value,
            "total_score": sub.total_score,
            "max_score": sum(a["max_marks"] for a in answers_list),
            "ai_confidence": sub.ai_confidence,
            "uploaded_at": sub.uploaded_at.isoformat() if sub.uploaded_at else None,
            "answers": answers_list
        })
        
    return results


@app.post("/api/v1/lms/push")
def push_grade_to_lms(
    data: LMSPushModel,
    db: Session = Depends(get_db)
):
    if not settings.LMS_URL:
        return {"status": "skipped", "reason": "LMS not configured"}

    submission = db.query(Submission).filter(Submission.id == data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    exam = db.query(Exam).filter(Exam.id == submission.exam_id).first()
    exam_title = exam.title if exam else "Unknown Exam"

    import httpx
    
    payload = {
        "submission_id": submission.id,
        "student_name": submission.student_name,
        "student_id": submission.student_id,
        "exam_title": exam_title,
        "grade": submission.total_score,
        "status": submission.status.value,
        "lms_type": data.lms_type
    }
    
    headers = {}
    if settings.LMS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.LMS_TOKEN}"
        
    try:
        response = httpx.post(settings.LMS_URL, json=payload, headers=headers, timeout=10)
        return {
            "status": "success",
            "lms_response_status": response.status_code,
            "lms_response_body": response.text,
            "payload_sent": payload
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to post grade to LMS_URL: {e}")
        return {
            "status": "failed",
            "reason": f"Connection failed: {e}",
            "payload_sent": payload
        }


# ==========================================
# SAAS MONETIZATION ENDPOINTS
# ==========================================
from app.services.subscription_service import (
    get_or_create_subscription, check_usage_limit,
    increment_usage, create_razorpay_subscription,
    activate_subscription, cancel_subscription
)
from app.core.plans import PLANS
import hmac
import hashlib

@app.get("/api/v1/subscription/status")
def get_subscription_status(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload)
):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        sub = get_or_create_subscription(user.id, db)
        usage = check_usage_limit(user.id, db)
        plan_val = sub.plan.value
        papers_used_val = sub.papers_used
        papers_limit_val = sub.papers_limit
        can_grade_val = usage["can_grade"]
        upgrade_required_val = usage["upgrade_required"]
        status_val = sub.status.value
    except Exception as e:
        print(f"Subscription status check failed: {e}")
        plan_val = "free"
        papers_used_val = 0
        papers_limit_val = 5
        can_grade_val = True
        upgrade_required_val = False
        status_val = "active"

    return {
        "plan": plan_val,
        "papers_used": papers_used_val,
        "papers_limit": papers_limit_val,
        "can_grade": can_grade_val,
        "upgrade_required": upgrade_required_val,
        "status": status_val
    }

@app.get("/api/v1/subscription/plans")
def get_plans():
    return PLANS

@app.post("/api/v1/subscription/create-order")
def create_subscription_order(
    data: CreateOrderModel,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload)
):
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    if not RAZORPAY_KEY_ID:
        return {"error": "payments_not_configured"}

    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    try:
        order_details = create_razorpay_subscription(
            user_id=user.id,
            plan=data.plan,
            user_email=user.email,
            user_name=user.name,
            db=db
        )
        return order_details
    except ValueError as ve:
        if str(ve) == "Payments not configured":
            return {"error": "payments_not_configured"}
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create subscription order: {str(e)}")

@app.post("/api/v1/subscription/verify-payment")
def verify_subscription_payment(
    data: VerifyPaymentModel,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload)
):
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not RAZORPAY_KEY_SECRET:
        return {"error": "payments_not_configured"}

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{data.razorpay_payment_id}|{data.razorpay_subscription_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if expected == data.razorpay_signature:
        activate_subscription(data.razorpay_subscription_id, data.razorpay_payment_id, db)
        sub = db.query(Subscription).filter_by(razorpay_sub_id=data.razorpay_subscription_id).first()
        plan_str = sub.plan.value if sub else "free"
        return {"success": True, "plan": plan_str}
    else:
        raise HTTPException(status_code=400, detail="Invalid signature verification failed")

@app.post("/api/v1/subscription/webhook")
async def subscription_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    
    if webhook_secret:
        signature = request.headers.get("X-Razorpay-Signature", "")
        expected = hmac.new(
            webhook_secret.encode(),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        if expected != signature:
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event_data = json.loads(body_str)
        event_type = event_data.get("event")
        
        if event_type == "subscription.activated":
            payload_sub = event_data.get("payload", {}).get("subscription", {}).get("entity", {})
            sub_id = payload_sub.get("id")
            activate_subscription(sub_id, "webhook", db)
        elif event_type in ["subscription.cancelled", "subscription.expired"]:
            payload_sub = event_data.get("payload", {}).get("subscription", {}).get("entity", {})
            sub_id = payload_sub.get("id")
            db_sub = db.query(Subscription).filter_by(razorpay_sub_id=sub_id).first()
            if db_sub:
                cancel_subscription(db_sub.user_id, db)
        elif event_type == "payment.failed":
            payload_payment = event_data.get("payload", {}).get("payment", {}).get("entity", {})
            sub_id = payload_payment.get("subscription_id")
            if sub_id:
                db_sub = db.query(Subscription).filter_by(razorpay_sub_id=sub_id).first()
                if db_sub:
                    cancel_subscription(db_sub.user_id, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error handling Razorpay webhook: {e}")
        
    return {"status": "ok"}

@app.post("/api/v1/subscription/cancel")
def user_cancel_subscription(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload)
):
    user = db.query(User).filter(User.name == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    cancel_subscription(user.id, db)
    return {"status": "cancelled"}


@app.post("/api/create-order")
def create_standard_order(
    data: RazorpayStandardCreateOrderRequest,
    payload: dict = Depends(get_current_user_payload)
):
    import razorpay
    import razorpay.errors
    
    # Validate amount >= 100 paise
    if data.amount < 100:
        raise HTTPException(
            status_code=400,
            detail="Amount must be at least 100 paise"
        )
        
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=500,
            detail="Razorpay credentials not configured"
        )
        
    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        order_params = {
            "amount": data.amount,
            "currency": data.currency,
            "receipt": data.receipt or f"receipt_{uuid.uuid4().hex[:10]}"
        }
        order = client.order.create(data=order_params)
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        }
    except razorpay.errors.AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Razorpay authentication failed"
        )
    except razorpay.errors.BadRequestError as bre:
        raise HTTPException(
            status_code=400,
            detail=str(bre)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Razorpay order creation failed: {str(e)}"
        )


@app.post("/api/verify-payment")
def verify_standard_payment(
    data: RazorpayStandardVerifyPaymentRequest,
    payload: dict = Depends(get_current_user_payload)
):
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_secret:
        raise HTTPException(
            status_code=500,
            detail="Razorpay credentials not configured"
        )
        
    if not data.razorpay_order_id or not data.razorpay_payment_id or not data.razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing signature verification fields"
        )
        
    # Generate signature using HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    msg = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
    expected = hmac.new(
        key_secret.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if hmac.compare_digest(expected, data.razorpay_signature):
        return {"success": True}
    else:
        raise HTTPException(
            status_code=400,
            detail="Signature verification failed"
        )


