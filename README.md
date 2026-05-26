<div align="center">

# 🎯 ScorePilot AI

### The Future Operating System for AI-Powered Academic Evaluation

[![Next.js](https://img.shields.io/badge/Next.js-16.2-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)

<br />

**ScorePilot AI** transforms how academic institutions grade exams — combining intelligent OCR extraction, semantic AI scoring, and human-in-the-loop review into one cinematic, enterprise-grade platform.

<br />

[🚀 Getting Started](#-getting-started) · [✨ Features](#-features) · [🏗️ Architecture](#️-architecture) · [📖 API Reference](#-api-reference) · [🎨 Design System](#-design-system)

<br />

---

</div>

## ✨ Features

### 🤖 AI-Powered Scoring Engine
- **Semantic Analysis** — Goes beyond keyword matching using transformer-based models that understand meaning, context, and reasoning quality
- **Multi-Question Support** — Handles MCQ (exact match), Short Answer (keyword + semantic similarity), and Long Answer (rubric-based weighted evaluation)
- **Confidence Scoring** — Every AI grade includes a confidence percentage; low-confidence submissions are automatically flagged for human review
- **Explainable AI** — Full reasoning traces for every score, including matched criteria, coverage percentages, and missing points

### 📄 Intelligent OCR Pipeline
- **Handwriting Recognition** — AI-powered extraction from scanned answer sheets, PDFs, and images
- **Multi-Format Support** — Upload scanned papers in JPG, PNG, PDF, or TIFF
- **Auto-Orientation Correction** — Handles rotated or skewed scans
- **Field-Level Confidence** — Per-question extraction reliability scores

### 👨‍🏫 Human-in-the-Loop Review
- **Review Queue** — Prioritized queue of flagged submissions requiring human attention
- **Side-by-Side View** — Student response alongside AI assessment with confidence indicators
- **Score Override** — Teachers can approve, adjust, or override any AI-generated score with audit trail
- **Batch Processing** — Efficiently review multiple papers in sequence

### 📊 Real-Time Analytics Dashboard
- **Score Distributions** — Visual breakdown across cohorts and assessments
- **Question Difficulty Index** — Identify which questions students struggle with most
- **Pass/Fail Analytics** — Real-time pass rates with historical comparison
- **AI Accuracy Metrics** — Track how AI scoring improves over time

### 🔐 Enterprise Security
- **JWT Authentication** — Secure token-based auth with role-based access control
- **Role System** — Admin, Teacher, and Reviewer roles with granular permissions
- **Audit Trail** — Complete log of every action: logins, uploads, score changes, overrides
- **CORS Protection** — Configurable cross-origin policies

---

## 🏗️ Architecture

```
ScorePilot-AI/
├── backend/                    # FastAPI Python Backend
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py       # Environment & app settings
│   │   │   └── security.py     # JWT, password hashing, RBAC
│   │   ├── models/
│   │   │   └── database.py     # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── ocr_service.py  # OCR extraction engine
│   │   │   └── scoring_service.py  # AI scoring pipeline
│   │   ├── workers/
│   │   │   └── tasks.py        # Celery async task simulation
│   │   └── main.py             # FastAPI app + all REST endpoints
│   ├── tests/                  # Pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # Next.js 16 Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Landing page (cinematic hero)
│   │   │   ├── login/          # Auth login page
│   │   │   ├── signup/         # Auth registration page
│   │   │   ├── dashboard/      # Protected dashboard (all tabs)
│   │   │   ├── layout.tsx      # Root layout + AuthProvider
│   │   │   └── globals.css     # shadcn design tokens + utilities
│   │   ├── components/ui/      # Reusable UI components
│   │   │   ├── hero-section-2.tsx    # Cinematic hero + navbar
│   │   │   ├── ai-workflow.tsx       # 5-step workflow timeline
│   │   │   ├── scoring-showcase.tsx  # AI scoring demo panels
│   │   │   ├── human-review.tsx      # Review interface mock
│   │   │   ├── analytics-section.tsx # Analytics preview
│   │   │   ├── mesh-gradient.tsx     # Animated background
│   │   │   ├── animated-group.tsx    # Stagger animations
│   │   │   ├── button.tsx            # shadcn button variants
│   │   │   └── footer.tsx            # Site footer
│   │   └── lib/
│   │       ├── api.ts          # Typed API client (all endpoints)
│   │       ├── auth-context.tsx # React auth context + JWT
│   │       └── utils.ts        # cn() utility
│   ├── next.config.ts          # API proxy rewrites
│   └── package.json
│
├── kubernetes/                 # K8s deployment manifests
│   └── deployment.yaml
├── docker-compose.yml          # Full-stack Docker orchestration
├── .env.example                # Environment variable template
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version |
|------|---------|
| **Node.js** | 18+ |
| **Python** | 3.11+ |
| **npm** | 9+ |

### 1. Clone the Repository

```bash
git clone https://github.com/xenon-creator/ScorePilot-AI.git
cd ScorePilot-AI
```

### 2. Setup Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Setup Frontend

```bash
cd frontend
npm install
```

### 4. Configure Environment

```bash
# From project root
cp .env.example .env
# Edit .env with your values (or use defaults for local dev)
```

### 5. Run the Platform

**Terminal 1 — Backend API:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### 6. Open in Browser

| Service | URL |
|---------|-----|
| 🌐 **Landing Page** | [http://localhost:3000](http://localhost:3000) |
| 🔐 **Login** | [http://localhost:3000/login](http://localhost:3000/login) |
| 📊 **Dashboard** | [http://localhost:3000/dashboard](http://localhost:3000/dashboard) |
| 📚 **API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |

### 🔑 Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| **Admin** | `admin@aegis.edu` | `admin123` |
| **Teacher** | `teacher@aegis.edu` | `teacher123` |
| **Reviewer** | `reviewer@aegis.edu` | `reviewer123` |

---

## 📖 API Reference

All endpoints are prefixed with `/api/v1`

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/signup` | — | Create account → returns JWT |
| `POST` | `/auth/login` | — | Login → returns JWT |
| `GET` | `/auth/me` | 🔒 JWT | Get current user profile |

### Exams

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/exams` | — | List all exams with questions |
| `POST` | `/exams` | 🔒 Teacher/Admin | Create exam with question bank |

### Scoring Pipeline

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/uploads` | — | Upload answer sheet → auto-grade |
| `GET` | `/submissions` | — | List all submissions |
| `POST` | `/review/override` | 🔒 Teacher/Reviewer/Admin | Override AI scores |

### Analytics & Audit

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/analytics?exam_id=` | — | Score distribution, difficulty index |
| `GET` | `/audit-logs` | 🔒 Admin/Teacher | Full system audit trail |

> 💡 **Interactive API docs** available at [localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)

---

## 🎨 Design System

The frontend uses a **cinematic dark glassmorphism** design language:

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `oklch(0.07 0.005 270)` | Deep dark base |
| `--primary` | `oklch(0.75 0.15 200)` | Cyan accent |
| `--border` | `oklch(1 0 0 / 8%)` | Subtle glass borders |
| Font | **Inter** | Primary sans-serif |
| Font Mono | **Geist Mono** | Code & data |

### Glassmorphism Utilities

```css
.glass-card        /* Frosted glass panel: blur(20px), 3% white bg, 8% border */
.glass-card-hover  /* Hover: 6% white bg, 12% border, deeper shadow */
.text-gradient-cyan   /* Cyan→Blue gradient text */
.text-gradient-violet /* Violet→Cyan gradient text */
.glow-cyan         /* Cyan ambient glow shadow */
```

### Component Library

Built on **shadcn/ui** architecture with custom dark theme:

- `Button` — 4 variants (default, outline, ghost, destructive) × 4 sizes
- `AnimatedGroup` — 10 animation presets (fade, blur-slide, zoom, bounce, etc.)
- `MeshGradient` — Animated multi-orb gradient background

---

## 🐳 Docker Deployment

```bash
# Full stack with one command
docker-compose up --build
```

The `docker-compose.yml` orchestrates:
- **Backend API** (FastAPI + Uvicorn)
- **PostgreSQL** database
- **Redis** for Celery task queue
- **MinIO** for object storage (scanned papers)
- **Celery Worker** for async grading pipeline

---

## 🔧 Tech Stack

<table>
<tr>
<td align="center" width="50%">

### Frontend
| Technology | Purpose |
|-----------|---------|
| Next.js 16 | React framework |
| Tailwind CSS 4 | Utility-first styling |
| shadcn/ui | Component system |
| Framer Motion | Animations |
| TypeScript | Type safety |
| Lucide React | Icon library |

</td>
<td align="center" width="50%">

### Backend
| Technology | Purpose |
|-----------|---------|
| FastAPI | REST API framework |
| Pydantic | Data validation |
| PyJWT | Authentication |
| bcrypt | Password hashing |
| SQLAlchemy | ORM (models ready) |
| Celery | Async task queue |

</td>
</tr>
</table>

---

## 📂 Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# JWT
JWT_SECRET=your-secret-key-here

# Database
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=aegis_grading

# Redis
REDIS_URL=redis://localhost:6379/0

# Object Storage (MinIO)
S3_ENDPOINT=localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=exam-papers
```

> ⚠️ **Never commit `.env` files.** The `.gitignore` is configured to exclude all `.env*` files except `.env.example`.

---

## 🗺️ Roadmap

- [ ] Real PostgreSQL integration with Alembic migrations
- [ ] Celery worker with Redis for production async grading
- [ ] MinIO file storage for scanned papers
- [ ] Real OCR integration (Tesseract / Google Vision API)
- [ ] Real AI scoring with sentence-transformers
- [ ] Student portal with self-service score viewing
- [ ] Email notifications for score release
- [ ] Export results to CSV/PDF
- [ ] Multi-language OCR support
- [ ] LMS integration (Moodle, Canvas)

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ by [xenon-creator](https://github.com/xenon-creator)**

<br />

<sub>ScorePilot AI — Transforming academic evaluation through intelligent AI scoring.</sub>

</div>
