import uuid
import json
import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, RoleChecker, get_current_user_payload
from app.models.database import (
    get_db, User, Exam, Question, Submission, Answer, AuditLog,
    UserRole, QuestionType, SubmissionStatus
)
from app.services.ocr_service import OCRService
from app.services.scoring_service import ScoringService

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

class ReviewOverrideItemModel(BaseModel):
    question_number: int
    override_score: float
    override_reason: str

class ReviewSubmissionOverrideModel(BaseModel):
    submission_id: str
    overrides: List[ReviewOverrideItemModel]


# ==========================================
# HELPERS
# ==========================================

ROLE_MAP = {
    "Admin": UserRole.admin, "admin": UserRole.admin,
    "Teacher": UserRole.teacher, "teacher": UserRole.teacher,
    "Reviewer": UserRole.reviewer, "reviewer": UserRole.reviewer,
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
    status_map = {
        SubmissionStatus.pending: "Scored",
        SubmissionStatus.graded: "Scored",
        SubmissionStatus.flagged: "Flagged",
        SubmissionStatus.reviewed: "Approved",
    }
    return {
        "id": sub.id,
        "exam_id": sub.exam_id,
        "student_id": sub.student_id or "",
        "student_name": sub.student_name,
        "scanned_image_url": "",
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
        password=hash_password(data.password),
    )
    db.add(new_user)
    db.flush()

    _audit(db, new_user.id, "User Signup", {"role": _role_display(role)})
    db.commit()

    token = create_access_token(data.username, _role_display(role))
    return {"access_token": token, "token_type": "bearer", "user": {"username": data.username, "role": _role_display(role)}}


@app.post("/api/v1/auth/login")
def login(data: LoginModel, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token(user.name, _role_display(user.role))

    _audit(db, user.id, "User Login", {"ip": "127.0.0.1"})
    db.commit()

    return {"access_token": token, "token_type": "bearer", "user": {"username": user.name, "role": _role_display(user.role)}}


@app.get("/api/v1/auth/me")
def get_me(payload: dict = Depends(get_current_user_payload)):
    return {"username": payload["sub"], "role": payload["role"]}


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

    # Run OCR simulation to get extracted text
    ocr_result = OCRService.simulate_scanning_pipeline(
        file_content=b"pdf-binary-simulation",
        filename=file.filename or "paper.pdf",
    )

    # Create submission (pending)
    submission = Submission(
        exam_id=exam_id,
        student_name=student_name,
        student_id=student_id,
        status=SubmissionStatus.pending,
        extracted_text=ocr_result.get("raw_text", ""),
    )
    db.add(submission)
    db.flush()

    # Map OCR blocks by question number
    ocr_blocks = {b["question_number"]: b for b in ocr_result.get("blocks", [])}

    total_score = 0.0
    total_confidence = 0.0
    any_flagged = False

    for idx, q in enumerate(exam.questions):
        q_num = idx + 1
        q_type = q.question_type.value  # "mcq", "short", "long"

        # Get student answer from OCR
        block = ocr_blocks.get(q_num)
        student_text = block["answer_text"] if block else ""

        # Score using real AI
        if q_type == "mcq":
            result = ScoringService.evaluate_mcq(student_text, q.model_answer, q.max_marks)
        elif q_type == "short":
            result = ScoringService.evaluate_short_answer(student_text, q.model_answer, q.max_marks)
        else:
            result = ScoringService.evaluate_long_answer(student_text, q.model_answer, q.max_marks)

        if result.flagged_for_review:
            any_flagged = True

        total_score += result.score
        total_confidence += result.confidence

        answer = Answer(
            submission_id=submission.id,
            question_id=q.id,
            question_number=q_num,
            student_answer=student_text,
            ai_score=result.score,
            final_score=result.score,
            ai_confidence=result.confidence,
            ai_reasoning=result.reasoning,
            flagged_for_review=result.flagged_for_review,
            scored_at=datetime.datetime.utcnow(),
        )
        db.add(answer)

    # Update submission totals
    num_questions = len(exam.questions) or 1
    submission.total_score = round(total_score, 2)
    submission.ai_confidence = round(total_confidence / num_questions, 2)
    submission.status = SubmissionStatus.flagged if any_flagged else SubmissionStatus.graded

    _audit(db, None, "AI Scoring Completed", {
        "submission_id": submission.id,
        "status": submission.status.value,
        "score": submission.total_score,
        "flagged": any_flagged,
    })
    db.commit()
    db.refresh(submission)

    return _format_submission(submission)


@app.get("/api/v1/submissions")
def list_submissions(exam_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Submission)
    if exam_id:
        query = query.filter(Submission.exam_id == exam_id)
    subs = query.order_by(Submission.uploaded_at.desc()).all()
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
