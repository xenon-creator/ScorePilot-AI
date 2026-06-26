import uuid
import enum
import datetime

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Text, DateTime,
    ForeignKey, Enum as SAEnum, Boolean, func, JSON, CheckConstraint
)
from sqlalchemy.orm import (
    DeclarativeBase, sessionmaker, relationship, Session
)
from app.core.config import settings


# ============================================
# ENGINE & SESSION
# ============================================

DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================
# BASE
# ============================================

class Base(DeclarativeBase):
    pass


# ============================================
# ENUMS
# ============================================

class UserRole(str, enum.Enum):
    admin = "admin"
    teacher = "teacher"
    reviewer = "reviewer"
    student = "student"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    short = "short"
    long = "long"


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    graded = "graded"
    flagged = "flagged"
    reviewed = "reviewed"


class PlanType(str, enum.Enum):
    free = "free"
    starter = "starter"
    pro = "pro"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    trial = "trial"


# ============================================
# MODELS
# ============================================

def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.teacher)
    student_id = Column(String, nullable=True, default=None)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    exams = relationship("Exam", back_populates="creator", foreign_keys="Exam.created_by")
    audit_logs = relationship("AuditLog", back_populates="user")
    lms_settings = relationship("LMSSettings", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", backref="user", uselist=False, cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    plan = Column(SAEnum(PlanType), nullable=False, default=PlanType.free)
    status = Column(SAEnum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.trial)
    papers_used = Column(Integer, default=0)
    papers_limit = Column(Integer, default=5)
    razorpay_sub_id = Column(String, nullable=True)
    razorpay_customer_id = Column(String, nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class Exam(Base):
    __tablename__ = "exams"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True, default="")
    language = Column(String, nullable=False, default="en")
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    creator = relationship("User", back_populates="exams", foreign_keys=[created_by])
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=_uuid)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    text = Column(Text, nullable=False)
    question_type = Column(SAEnum(QuestionType), nullable=False, default=QuestionType.short)
    model_answer = Column(Text, nullable=False)
    max_marks = Column(Float, nullable=False)
    marking_scheme = Column(JSON, nullable=True)
    dataset_question_id = Column(String, nullable=True)

    # Relationships
    exam = relationship("Exam", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, default=_uuid)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    student_name = Column(String, nullable=False)
    student_id = Column(String, nullable=True, default="")
    status = Column(SAEnum(SubmissionStatus), nullable=False, default=SubmissionStatus.pending)
    total_score = Column(Float, nullable=True, default=0.0)
    ai_confidence = Column(Float, nullable=True, default=0.0)
    extracted_text = Column(Text, nullable=True, default="")
    raw_text = Column(Text, nullable=True)
    cleaned_text = Column(Text, nullable=True)
    ocr_engine = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    scanned_image_url = Column(String, nullable=True, default="")
    uploaded_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    point_scores = Column(JSON, nullable=True)
    holistic_adjustment = Column(Float, nullable=True, default=0.0)
    match_details = Column(JSON, nullable=True)
    confidence_score = Column(Integer, CheckConstraint('confidence_score >= 0 AND confidence_score <= 100'), nullable=True, default=70)
    feedback = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    matched_points = Column(JSON, nullable=True)
    partial_points = Column(JSON, nullable=True)
    missing_points = Column(JSON, nullable=True)
    score = Column(Float, nullable=True, default=0.0)

    # Relationships
    exam = relationship("Exam", back_populates="submissions")
    answers = relationship("Answer", back_populates="submission", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(String, primary_key=True, default=_uuid)
    submission_id = Column(String, ForeignKey("submissions.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    question_number = Column(Integer, nullable=False, default=1)
    student_answer = Column(Text, nullable=True, default="")
    ai_score = Column(Float, nullable=True, default=0.0)
    final_score = Column(Float, nullable=True, default=0.0)
    ai_confidence = Column(Float, nullable=True, default=0.0)
    ai_reasoning = Column(Text, nullable=True, default="")
    flagged_for_review = Column(Boolean, nullable=False, default=False)
    scored_at = Column(DateTime, nullable=True, default=lambda: datetime.datetime.now(datetime.UTC))
    overridden_by = Column(String, ForeignKey("users.id"), nullable=True)
    evaluation_metadata = Column(JSON, nullable=True)

    # Relationships
    submission = relationship("Submission", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    override_user = relationship("User", foreign_keys=[overridden_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    detail = Column(Text, nullable=True, default="")
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    user = relationship("User", back_populates="audit_logs")


class LMSSettings(Base):
    __tablename__ = "lms_settings"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    lms_type = Column(String, nullable=False)  # "canvas" or "moodle"
    api_url = Column(String, nullable=False)
    api_token = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    user = relationship("User", back_populates="lms_settings")


# ============================================
# DEPENDENCY
# ============================================

def get_db():
    """FastAPI dependency that yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
