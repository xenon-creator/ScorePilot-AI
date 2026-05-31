import uuid
import json
import datetime
import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend dashboard connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    try:
        from app.services.storage_service import ensure_bucket_exists
        ensure_bucket_exists()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error ensuring MinIO bucket exists on startup: {e}")

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
    return {"status": "online", "service": "AegisGrading AI API gateway", "time": str(datetime.datetime.utcnow())}


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


# --- UPLOADS & SCORING ---
@app.post("/api/v1/uploads")
def upload_papers(
    student_name: str = Form(...),
    student_id: str = Form(...),
    exam_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Retrieve exam
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam details not found")

    filename = file.filename or "paper.pdf"
    object_key = f"uploads/{uuid.uuid4()}_{filename}"

    # Read uploaded file bytes and put directly to S3 storage
    try:
        from app.services.storage_service import upload_file_content
        file_bytes = file.file.read()
        upload_file_content(
            file_bytes=file_bytes,
            object_key=object_key,
            content_type=file.content_type or "application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(e)}")

    # Create submission in database with pending status and S3 reference
    submission = Submission(
        exam_id=exam_id,
        student_name=student_name,
        student_id=student_id,
        status=SubmissionStatus.pending,
        scanned_image_url=object_key,
        total_score=0.0,
        ai_confidence=0.0,
        extracted_text="",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Dispatch Celery background task for asynchronous scoring with object key
    process_and_score_submission.delay(submission.id, object_key, filename)

    # Log initial submission upload event
    _audit(db, None, "Submission Uploaded", {
        "submission_id": submission.id,
        "student_name": submission.student_name,
        "filename": filename,
    })
    db.commit()

    return _format_submission(submission)


@app.get("/api/v1/submissions")
def list_submissions(exam_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Submission)
    if exam_id:
        query = query.filter(Submission.exam_id == exam_id)
    subs = query.order_by(Submission.uploaded_at.desc()).all()
    return [_format_submission(s) for s in subs]


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
    result["reviewed_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    return result


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
