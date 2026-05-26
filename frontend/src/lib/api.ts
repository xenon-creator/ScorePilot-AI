const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ============================================
// TYPES
// ============================================

export interface User {
  username: string
  role: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Rubric {
  criterion: string
  weight: number
  keywords: string[]
  description: string
}

export interface Question {
  id: string
  question_number: number
  question_text: string
  question_type: 'MCQ' | 'Short' | 'Long'
  max_marks: number
  model_answer: string
  rubrics: Rubric[] | null
  keywords: string[] | null
}

export interface Exam {
  id: string
  title: string
  subject: string
  code: string
  creator_id: string
  total_marks: number
  passing_marks: number
  status: string
  created_at: string
  questions: Question[]
}

export interface ScoreDetail {
  question_id: string
  question_number: number
  raw_score: number
  final_score: number
  ai_generated_score?: number
  ai_confidence: number
  feedback: string
  criteria_matched: Record<string, unknown>
  override_reason?: string
  override_by?: string
}

export interface Submission {
  id: string
  exam_id: string
  student_id: string
  student_name: string
  scanned_image_url: string
  extracted_text: string
  status: 'Scored' | 'Flagged' | 'Approved'
  total_score: number
  ai_confidence: number
  created_at: string
  scores: ScoreDetail[]
  reviewer_id?: string
  reviewed_at?: string
}

export interface AuditLog {
  id: string
  timestamp: string
  user: string
  action: string
  details: Record<string, unknown>
}

export interface AnalyticsData {
  exam_id: string
  exam_title: string
  papers_processed: number
  average_score: number
  pass_count: number
  fail_count: number
  score_distribution: Record<string, number>
  question_difficulty: Array<{
    question_number: number
    difficulty_percentage: number
    question_text_short: string
  }>
}

// ============================================
// FETCH HELPER
// ============================================

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('sp_token') : null

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(body.detail || 'API Error', res.status)
  }

  return res.json()
}

// ============================================
// AUTH ENDPOINTS
// ============================================

export async function apiLogin(email: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function apiSignup(
  username: string,
  email: string,
  password: string,
  role: string = 'Teacher'
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ username, email, password, role }),
  })
}

export async function apiGetMe(): Promise<User> {
  return apiFetch<User>('/api/v1/auth/me')
}

// ============================================
// EXAMS
// ============================================

export async function apiGetExams(): Promise<Exam[]> {
  return apiFetch<Exam[]>('/api/v1/exams')
}

export async function apiCreateExam(data: {
  title: string
  subject: string
  code: string
  total_marks: number
  passing_marks: number
  questions: Array<{
    question_number: number
    question_text: string
    question_type: string
    max_marks: number
    model_answer: string
    rubrics?: Rubric[] | null
    keywords?: string[] | null
  }>
}): Promise<Exam> {
  return apiFetch<Exam>('/api/v1/exams', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============================================
// UPLOADS & SUBMISSIONS
// ============================================

export async function apiUploadPaper(
  studentName: string,
  studentId: string,
  examId: string,
  file: File
): Promise<Submission> {
  const formData = new FormData()
  formData.append('student_name', studentName)
  formData.append('student_id', studentId)
  formData.append('exam_id', examId)
  formData.append('file', file)

  return apiFetch<Submission>('/api/v1/uploads', {
    method: 'POST',
    body: formData,
  })
}

export async function apiGetSubmissions(examId?: string): Promise<Submission[]> {
  const query = examId ? `?exam_id=${encodeURIComponent(examId)}` : ''
  return apiFetch<Submission[]>(`/api/v1/submissions${query}`)
}

// ============================================
// REVIEW / OVERRIDE
// ============================================

export async function apiOverrideScores(data: {
  submission_id: string
  overrides: Array<{
    question_number: number
    override_score: number
    override_reason: string
  }>
}): Promise<Submission> {
  return apiFetch<Submission>('/api/v1/review/override', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============================================
// ANALYTICS
// ============================================

export async function apiGetAnalytics(examId: string): Promise<AnalyticsData> {
  return apiFetch<AnalyticsData>(`/api/v1/analytics?exam_id=${encodeURIComponent(examId)}`)
}

// ============================================
// AUDIT LOGS
// ============================================

export async function apiGetAuditLogs(): Promise<AuditLog[]> {
  return apiFetch<AuditLog[]>('/api/v1/audit-logs')
}
