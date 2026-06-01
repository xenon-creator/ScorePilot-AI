# Deploying ScorePilot AI

## Free Stack
| Service | Provider | Cost |
|---|---|---|
| Frontend | Vercel | Free |
| Backend API | Render | Free |
| Database | Supabase | Free (500MB) |
| File Storage | Cloudinary or local | Free tier |

## Step 1 — Supabase (Database)
1. Go to supabase.com → New project
2. Name it: scorepilot-ai
3. Note your connection string:
   postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
4. In Supabase SQL editor, you don't need to create tables —
   Alembic will do that automatically on first deploy.

## Step 2 — Render (Backend)
1. Go to render.com → New Web Service
2. Connect your GitHub repo: xenon-creator/ScorePilot-AI
3. Root directory: backend
4. Build command: pip install -r requirements.txt
5. Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
6. Add environment variables from .env.example
   Replace DB_* values with your Supabase connection details
7. After first deploy, open Render shell and run:
   alembic upgrade head
   python -m app.seed
8. Copy your Render URL (e.g. https://scorepilot-api.onrender.com)

## Step 3 — Vercel (Frontend)
1. Go to vercel.com → New Project
2. Import: xenon-creator/ScorePilot-AI
3. Root directory: frontend
4. Add environment variable:
   NEXT_PUBLIC_API_URL = https://scorepilot-api.onrender.com
5. Deploy
6. Copy your Vercel URL (e.g. https://scorepilot-ai.vercel.app)

## Step 4 — Update CORS
In Render environment variables, add:
  ALLOWED_ORIGINS = https://scorepilot-ai.vercel.app

## Done
Your app is live at https://scorepilot-ai.vercel.app
