const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = 2,
  delay = 2000
): Promise<Response> {
  try {
    const response = await fetch(url, options)
    if (!response.ok && retries > 0) {
      await new Promise(r => setTimeout(r, delay))
      return fetchWithRetry(url, options, retries - 1, delay)
    }
    return response
  } catch (error) {
    if (retries > 0) {
      await new Promise(r => setTimeout(r, delay))
      return fetchWithRetry(url, options, retries - 1, delay)
    }
    throw error
  }
}

// ============================================
// TYPES
// ============================================

export interface User {
  username: string
  role: string
  student_id?: string
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
  language: string
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
  status: 'Scored' | 'Flagged' | 'Approved' | 'Pending'
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

  const res = await fetchWithRetry(`${API_BASE}${path}`, {
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
  role: string = 'Teacher',
  studentId?: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ username, email, password, role, student_id: studentId }),
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
  language?: string
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

export async function apiGetStudentSubmissions(): Promise<Submission[]> {
  return apiFetch<Submission[]>('/api/v1/student/submissions')
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

// ============================================
// EXPORTS
// ============================================

export async function apiExportExamCsv(examId: string, examTitle: string): Promise<void> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('sp_token') : null
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetchWithRetry(`${API_BASE}/api/v1/exams/${examId}/export/csv`, { headers })
  if (!res.ok) throw new Error('Failed to export CSV')
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `exam_${examTitle.toLowerCase().replace(/ /g, '_')}_grades.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export async function apiExportSubmissionPdf(submissionId: string, studentName: string): Promise<void> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('sp_token') : null
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetchWithRetry(`${API_BASE}/api/v1/submissions/${submissionId}/export/pdf`, { headers })
  if (!res.ok) throw new Error('Failed to export PDF')
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `submission_${studentName.toLowerCase().replace(/ /g, '_')}_report.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export interface LmsSettings {
  configured: boolean
  lms_type?: 'canvas' | 'moodle'
  api_url?: string
}

export interface LmsCourse {
  id: string
  name: string
  code: string
  assignments: Array<{
    id: string
    name: string
    max_points: number
  }>
}

export async function apiGetLmsSettings(): Promise<LmsSettings> {
  return apiFetch<LmsSettings>('/api/v1/lms/settings')
}

export async function apiSaveLmsSettings(data: {
  lms_type: string
  api_url: string
  api_token: string
}): Promise<{ status: string, message: string }> {
  return apiFetch<{ status: string, message: string }>('/api/v1/lms/settings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function apiGetLmsCourses(): Promise<LmsCourse[]> {
  return apiFetch<LmsCourse[]>('/api/v1/lms/courses')
}

export async function apiSyncExamGradesToLms(
  examId: string,
  courseId: string,
  assignmentId: string
): Promise<{ status: string, synced_count: number, details: any }> {
  return apiFetch<{ status: string, synced_count: number, details: any }>(`/api/v1/exams/${examId}/sync-lms`, {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId, assignment_id: assignmentId }),
  })
}
