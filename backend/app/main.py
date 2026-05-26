import uuid
import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, RoleChecker, get_current_user_payload
from app.services.ocr_service import OCRService
from app.services.scoring_service import ScoringService
from app.workers.tasks import process_and_score_submission

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
# IN-MEMORY SEED DB (FOR OUT-OF-THE-BOX MVP)
# ==========================================
SEED_USERS = {
    "admin@aegis.edu": {
        "id": "u-admin-1",
        "username": "admin",
        "email": "admin@aegis.edu",
        "hashed_password": hash_password("admin123"),
        "role": "Admin",
        "is_active": True
    },
    "teacher@aegis.edu": {
        "id": "u-teacher-1",
        "username": "prof_sarah",
        "email": "teacher@aegis.edu",
        "hashed_password": hash_password("teacher123"),
        "role": "Teacher",
        "is_active": True
    },
    "reviewer@aegis.edu": {
        "id": "u-reviewer-1",
        "username": "reviewer_john",
        "email": "reviewer@aegis.edu",
        "hashed_password": hash_password("reviewer123"),
        "role": "Reviewer",
        "is_active": True
    }
}

SEED_EXAMS = [
    {
        "id": "ex-bio-101",
        "title": "Introduction to Cellular Biology",
        "subject": "Biology",
        "code": "BIO-101",
        "creator_id": "u-teacher-1",
        "total_marks": 20,
        "passing_marks": 10,
        "status": "Active",
        "created_at": "2026-05-20T10:00:00Z",
        "questions": [
            {
                "id": "q-bio-1",
                "question_number": 1,
                "question_text": "Which organelle is considered the powerhouse of the cell?",
                "question_type": "MCQ",
                "max_marks": 2.0,
                "model_answer": "A",
                "rubrics": None,
                "keywords": None
            },
            {
                "id": "q-bio-2",
                "question_number": 2,
                "question_text": "What is the primary product of photosynthesis that plants use for food?",
                "question_type": "MCQ",
                "max_marks": 2.0,
                "model_answer": "C",
                "rubrics": None,
                "keywords": None
            },
            {
                "id": "q-bio-3",
                "question_number": 3,
                "question_text": "Explain the role of Mitochondria in cellular respiration.",
                "question_type": "Short",
                "max_marks": 6.0,
                "model_answer": "Mitochondria generates ATP through cellular respiration using nutrients and oxygen. It contains a double membrane structure with cristae.",
                "rubrics": None,
                "keywords": ["ATP", "respiration", "membrane", "oxygen"]
            },
            {
                "id": "q-bio-4",
                "question_number": 4,
                "question_text": "Describe the complete process of photosynthesis, detailing light and dark reactions.",
                "question_type": "Long",
                "max_marks": 10.0,
                "model_answer": "Photosynthesis turns light energy into chemical glucose. In light-dependent reactions, chlorophyll absorbs sunlight inside thylakoid membranes to split water and yield oxygen and ATP. In dark reactions (Calvin Cycle), ATP and carbon dioxide are processed inside the stroma to synthesize glucose.",
                "rubrics": [
                    {"criterion": "Light Reactions", "weight": 0.4, "keywords": ["light", "thylakoid", "water", "oxygen"], "description": "Accurate description of photon capture and splitting of water."},
                    {"criterion": "Calvin Cycle", "weight": 0.4, "keywords": ["dark", "stroma", "carbon dioxide", "glucose"], "description": "Details about CO2 fixation into sugars."},
                    {"criterion": "Scientific Grammar", "weight": 0.2, "keywords": ["chloroplast", "chlorophyll"], "description": "Correct spelling of organelles and fluent structures."}
                ],
                "keywords": None
            }
        ]
    }
]

SEED_SUBMISSIONS = [
    {
        "id": "sub-bio-01",
        "exam_id": "ex-bio-101",
        "student_id": "STU-8821",
        "student_name": "Alexander Vance",
        "scanned_image_url": "https://aegis-storage.s3.amazonaws.com/submissions/bio_alex.jpg",
        "extracted_text": "Q1: A\nQ2: C\nQ3: Mitochondria is the powerhouse. It makes ATP energy via respiration cycles.\nQ4: Photosynthesis captures light in leaves to produce sugar glucose. Thylakoids generate oxygen. The stroma handles the dark Calvin cycle to assemble carbon and sugars.",
        "status": "Scored",
        "total_score": 17.5,
        "ai_confidence": 0.92,
        "created_at": "2026-05-25T11:20:00Z",
        "scores": [
            {"question_id": "q-bio-1", "question_number": 1, "raw_score": 2.0, "final_score": 2.0, "ai_generated_score": 2.0, "ai_confidence": 1.0, "feedback": "Correct option matching.", "criteria_matched": {"option_match": True}},
            {"question_id": "q-bio-2", "question_number": 2, "raw_score": 2.0, "final_score": 2.0, "ai_generated_score": 2.0, "ai_confidence": 1.0, "feedback": "Correct option matching.", "criteria_matched": {"option_match": True}},
            {"question_id": "q-bio-3", "question_number": 3, "raw_score": 5.5, "final_score": 5.5, "ai_generated_score": 5.5, "ai_confidence": 0.94, "feedback": "Excellent response! Captures ATP and respiration concept.", "criteria_matched": {"semantic_similarity_percentage": 88, "matched_keywords": ["ATP", "respiration"]}},
            {"question_id": "q-bio-4", "question_number": 4, "raw_score": 8.0, "final_score": 8.0, "ai_generated_score": 8.0, "ai_confidence": 0.89, "feedback": "Strong understanding of both pathways.", "criteria_matched": {
                "criteria_details": [
                    {"criterion": "Light Reactions", "weight": 0.4, "matched_points": ["light", "oxygen"], "missing_points": ["thylakoid"], "coverage_percentage": 85},
                    {"criterion": "Calvin Cycle", "weight": 0.4, "matched_points": ["dark", "glucose", "carbon dioxide"], "missing_points": [], "coverage_percentage": 95},
                    {"criterion": "Scientific Grammar", "weight": 0.2, "matched_points": ["chlorophyll"], "missing_points": ["chloroplast"], "coverage_percentage": 70}
                ]
            }}
        ]
    },
    {
        "id": "sub-bio-02",
        "exam_id": "ex-bio-101",
        "student_id": "STU-4912",
        "student_name": "Eleanor Vance",
        "scanned_image_url": "https://aegis-storage.s3.amazonaws.com/submissions/bio_eleanor.jpg",
        "extracted_text": "Q1: B\nQ2: C\nQ3: Mitochondria is an organelle that does some cellular breathing.\nQ4: Plants do photosynthesis using carbon dioxide and water to grow.",
        "status": "Flagged",
        "total_score": 6.5,
        "ai_confidence": 0.68,
        "created_at": "2026-05-25T11:22:00Z",
        "scores": [
            {"question_id": "q-bio-1", "question_number": 1, "raw_score": 0.0, "final_score": 0.0, "ai_generated_score": 0.0, "ai_confidence": 1.0, "feedback": "Incorrect choice.", "criteria_matched": {"option_match": False}},
            {"question_id": "q-bio-2", "question_number": 2, "raw_score": 2.0, "final_score": 2.0, "ai_generated_score": 2.0, "ai_confidence": 1.0, "feedback": "Correct option matching.", "criteria_matched": {"option_match": True}},
            {"question_id": "q-bio-3", "question_number": 3, "raw_score": 1.5, "final_score": 1.5, "ai_generated_score": 1.5, "ai_confidence": 0.65, "feedback": "Incomplete. Missing key terms like ATP.", "criteria_matched": {"semantic_similarity_percentage": 30, "matched_keywords": [], "missing_keywords": ["ATP", "respiration"]}},
            {"question_id": "q-bio-4", "question_number": 4, "raw_score": 3.0, "final_score": 3.0, "ai_confidence": 0.58, "feedback": "Very sparse answer. Missing both light and dark cycle definitions.", "criteria_matched": {
                "criteria_details": [
                    {"criterion": "Light Reactions", "weight": 0.4, "matched_points": [], "missing_points": ["light", "oxygen"], "coverage_percentage": 20},
                    {"criterion": "Calvin Cycle", "weight": 0.4, "matched_points": ["carbon dioxide"], "missing_points": ["dark", "glucose"], "coverage_percentage": 35},
                    {"criterion": "Scientific Grammar", "weight": 0.2, "matched_points": [], "missing_points": ["chlorophyll"], "coverage_percentage": 20}
                ]
            }}
        ]
    }
]

SEED_AUDIT_LOGS = [
    {
        "id": "aud-1",
        "timestamp": "2026-05-25T11:00:00Z",
        "user": "prof_sarah",
        "action": "Exam Creation",
        "details": {"exam_code": "BIO-101", "questions_count": 4}
    },
    {
        "id": "aud-2",
        "timestamp": "2026-05-25T11:15:00Z",
        "user": "prof_sarah",
        "action": "Batch Upload Scans",
        "details": {"exam_code": "BIO-101", "files_uploaded": 2}
    }
]

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
# REST API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"status": "online", "service": "AegisGrading AI API gateway", "time": str(datetime.datetime.utcnow())}

# --- AUTHENTICATION ---
@app.post("/api/v1/auth/signup")
def signup(data: SignUpModel):
    if data.email in SEED_USERS:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = {
        "id": f"u-{str(uuid.uuid4())[:8]}",
        "username": data.username,
        "email": data.email,
        "hashed_password": hash_password(data.password),
        "role": data.role,
        "is_active": True
    }
    SEED_USERS[data.email] = new_user
    
    # Audit log
    SEED_AUDIT_LOGS.insert(0, {
        "id": f"aud-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": data.username,
        "action": "User Signup",
        "details": {"role": data.role}
    })
    
    token = create_access_token(data.username, data.role)
    return {"access_token": token, "token_type": "bearer", "user": {"username": data.username, "role": data.role}}

@app.post("/api/v1/auth/login")
def login(data: LoginModel):
    user = SEED_USERS.get(data.email)
    if not user or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    token = create_access_token(user["username"], user["role"])
    
    # Audit log
    SEED_AUDIT_LOGS.insert(0, {
        "id": f"aud-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": user["username"],
        "action": "User Login",
        "details": {"ip": "127.0.0.1"}
    })
    
    return {"access_token": token, "token_type": "bearer", "user": {"username": user["username"], "role": user["role"]}}

@app.get("/api/v1/auth/me")
def get_me(payload: dict = Depends(get_current_user_payload)):
    return {"username": payload["sub"], "role": payload["role"]}

# --- EXAMS ---
@app.get("/api/v1/exams")
def get_exams():
    return SEED_EXAMS

@app.post("/api/v1/exams")
def create_exam(data: ExamCreateModel, payload: dict = Depends(RoleChecker(["Teacher", "Admin"]))):
    # Check duplicate code
    if any(ex["code"] == data.code for ex in SEED_EXAMS):
        raise HTTPException(status_code=400, detail="Exam with this code already exists")
        
    exam_dict = data.dict()
    exam_dict["id"] = f"ex-{str(uuid.uuid4())[:8]}"
    exam_dict["creator_id"] = payload.get("sub", "u-teacher-1")
    exam_dict["status"] = "Active"
    exam_dict["created_at"] = datetime.datetime.utcnow().isoformat()
    
    for q in exam_dict["questions"]:
        q["id"] = f"q-{str(uuid.uuid4())[:8]}"
        
    SEED_EXAMS.append(exam_dict)
    
    # Audit log
    SEED_AUDIT_LOGS.insert(0, {
        "id": f"aud-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": payload["sub"],
        "action": "Exam Creation",
        "details": {"exam_code": data.code, "questions_count": len(data.questions)}
    })
    
    return exam_dict

# --- UPLOADS & SCORING ---
@app.post("/api/v1/uploads")
def upload_papers(
    student_name: str = Form(...),
    student_id: str = Form(...),
    exam_id: str = Form(...),
    file: UploadFile = File(...)
):
    # Retrieve exam question templates
    target_exam = next((ex for ex in SEED_EXAMS if ex["id"] == exam_id), None)
    if not target_exam:
        raise HTTPException(status_code=404, detail="Exam details not found")
        
    submission_id = f"sub-{str(uuid.uuid4())[:8]}"
    submission_meta = {
        "id": submission_id,
        "exam_id": exam_id,
        "student_id": student_id,
        "student_name": student_name,
        "filename": file.filename,
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    
    # Call celery worker scoring pipeline simulation
    graded_payload = process_and_score_submission(submission_meta, target_exam["questions"])
    
    # Save graded details into in-memory store
    new_submission = {
        "id": submission_id,
        "exam_id": exam_id,
        "student_id": student_id,
        "student_name": student_name,
        "scanned_image_url": f"https://aegis-storage.s3.amazonaws.com/submissions/{file.filename}",
        "extracted_text": graded_payload["extracted_text"],
        "status": graded_payload["status"],
        "total_score": graded_payload["total_score"],
        "ai_confidence": graded_payload["ai_confidence"],
        "created_at": submission_meta["created_at"],
        "scores": graded_payload["scores"]
    }
    SEED_SUBMISSIONS.append(new_submission)
    
    # Audit log
    SEED_AUDIT_LOGS.insert(0, {
        "id": f"aud-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": "celery_worker",
        "action": "Automated Grading Completed",
        "details": {"submission_id": submission_id, "status": graded_payload["status"], "score": graded_payload["total_score"]}
    })
    
    return new_submission

@app.get("/api/v1/submissions")
def list_submissions(exam_id: Optional[str] = None):
    if exam_id:
        return [sub for sub in SEED_SUBMISSIONS if sub["exam_id"] == exam_id]
    return SEED_SUBMISSIONS

# --- HUMAN IN THE LOOP REVIEW ---
@app.post("/api/v1/review/override")
def override_scores(data: ReviewSubmissionOverrideModel, payload: dict = Depends(RoleChecker(["Teacher", "Reviewer", "Admin"]))):
    submission = next((sub for sub in SEED_SUBMISSIONS if sub["id"] == data.submission_id), None)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    audit_overrides = []
    total_new_score = 0.0
    
    # Apply score overrides
    for ov in data.overrides:
        target_score = next((sc for sc in submission["scores"] if sc["question_number"] == ov.question_number), None)
        if target_score:
            old_score = target_score["raw_score"]
            target_score["final_score"] = ov.override_score
            target_score["raw_score"] = ov.override_score
            target_score["override_reason"] = ov.override_reason
            target_score["override_by"] = payload["sub"]
            
            audit_overrides.append({
                "question_number": ov.question_number,
                "old_score": old_score,
                "new_score": ov.override_score,
                "reason": ov.override_reason
            })
            total_new_score += ov.override_score
        else:
            raise HTTPException(status_code=400, detail=f"Question {ov.question_number} not found in scores list")
            
    # Keep untouched scores in total
    untouched_score = sum(
        sc["final_score"] if "final_score" in sc else sc["raw_score"]
        for sc in submission["scores"]
        if not any(ov.question_number == sc["question_number"] for ov in data.overrides)
    )
    
    submission["total_score"] = round(untouched_score + total_new_score, 2)
    submission["status"] = "Approved"
    submission["reviewer_id"] = payload["sub"]
    submission["reviewed_at"] = datetime.datetime.utcnow().isoformat()
    
    # Audit trail
    SEED_AUDIT_LOGS.insert(0, {
        "id": f"aud-{str(uuid.uuid4())[:8]}",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": payload["sub"],
        "action": "Human Grading Override",
        "details": {
            "submission_id": data.submission_id,
            "student_name": submission["student_name"],
            "changes": audit_overrides,
            "new_total": submission["total_score"]
        }
    })
    
    return submission

# --- ANALYTICS ---
@app.get("/api/v1/analytics")
def get_analytics(exam_id: str):
    exam = next((ex for ex in SEED_EXAMS if ex["id"] == exam_id), None)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    subs = [sub for sub in SEED_SUBMISSIONS if sub["exam_id"] == exam_id]
    
    # Calculations
    scores_list = [s["total_score"] for s in subs]
    avg_score = round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
    pass_threshold = exam["passing_marks"]
    pass_count = sum(1 for s in scores_list if s >= pass_threshold)
    fail_count = len(scores_list) - pass_count
    
    # Score distribution slots: 0-25%, 26-50%, 51-75%, 76-100%
    max_m = exam["total_marks"]
    distribution = {"0-25%": 0, "26-50%": 0, "51-75%": 0, "76-100%": 0}
    for s in scores_list:
        pct = (s / max_m) * 100 if max_m else 0
        if pct <= 25: distribution["0-25%"] += 1
        elif pct <= 50: distribution["26-50%"] += 1
        elif pct <= 75: distribution["51-75%"] += 1
        else: distribution["76-100%"] += 1
        
    # Question difficulty index (average score on each question / max mark of that question)
    question_difficulty = []
    for q in exam["questions"]:
        q_scores = []
        for s in subs:
            sq = next((score for score in s["scores"] if score["question_number"] == q["question_number"]), None)
            if sq:
                q_scores.append(sq["raw_score"])
        avg_q_score = sum(q_scores) / len(q_scores) if q_scores else 0.0
        difficulty_pct = round((avg_q_score / q["max_marks"]) * 100, 2) if q["max_marks"] else 0.0
        question_difficulty.append({
            "question_number": q["question_number"],
            "difficulty_percentage": difficulty_pct,  # 100% means easy, lower means hard
            "question_text_short": q["question_text"][:40] + "..."
        })
        
    return {
        "exam_id": exam_id,
        "exam_title": exam["title"],
        "papers_processed": len(subs),
        "average_score": avg_score,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "score_distribution": distribution,
        "question_difficulty": question_difficulty
    }

# --- AUDIT LOGS ---
@app.get("/api/v1/audit-logs")
def get_audit_logs(payload: dict = Depends(RoleChecker(["Admin", "Moderator", "Teacher"]))):
    return SEED_AUDIT_LOGS
