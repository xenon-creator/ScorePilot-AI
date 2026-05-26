import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Text, JSON, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="Teacher")  # Admin, Teacher, Reviewer, Moderator
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    exams = relationship("Exam", back_populates="creator")
    audits = relationship("AuditLog", back_populates="user")

class Exam(Base):
    __tablename__ = "exams"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(100), nullable=False)
    subject = Column(String(50), nullable=False)
    code = Column(String(20), unique=True, index=True, nullable=False)
    creator_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    total_marks = Column(Integer, nullable=False)
    passing_marks = Column(Integer, nullable=False)
    status = Column(String(20), default="Draft")  # Draft, Active, Completed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    creator = relationship("User", back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(String(36), ForeignKey("exams.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False)  # MCQ, Short, Long
    max_marks = Column(Float, nullable=False)
    model_answer = Column(Text, nullable=False)
    rubrics = Column(JSON, nullable=True)  # Detailed list of scoring criteria
    
    exam = relationship("Exam", back_populates="questions")
    scores = relationship("Score", back_populates="question", cascade="all, delete-orphan")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(String(36), ForeignKey("exams.id"), nullable=False)
    student_id = Column(String(50), index=True, nullable=False)
    student_name = Column(String(100), nullable=False)
    scanned_image_url = Column(String(255), nullable=True)
    extracted_text = Column(Text, nullable=True)
    status = Column(String(20), default="Pending")  # Pending, Processing, Scored, Flagged, Reviewed, Approved
    total_score = Column(Float, default=0.0)
    ai_confidence = Column(Float, default=0.0)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    exam = relationship("Exam", back_populates="submissions")
    scores = relationship("Score", back_populates="submission", cascade="all, delete-orphan")

class Score(Base):
    __tablename__ = "scores"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("questions.id"), nullable=False)
    raw_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    ai_generated_score = Column(Float, default=0.0)
    ai_confidence = Column(Float, default=0.0)
    feedback = Column(Text, nullable=True)
    criteria_matched = Column(JSON, nullable=True)  # Details of matched/missing rubric items
    override_reason = Column(Text, nullable=True)
    override_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    submission = relationship("Submission", back_populates="scores")
    question = relationship("Question", back_populates="scores")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # UserLogin, ScoreOverride, RubricEdit, BatchUpload
    details = Column(JSON, nullable=True)
    
    user = relationship("User", back_populates="audits")
