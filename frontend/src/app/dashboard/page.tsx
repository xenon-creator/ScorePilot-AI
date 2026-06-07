'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import {
  apiGetExams, apiGetSubmissions, apiGetAnalytics, apiGetAuditLogs, apiUploadPaper, apiOverrideScores,
  apiExportExamCsv, apiExportSubmissionPdf, apiCreateExam,
  apiGetLmsSettings, apiSaveLmsSettings, apiGetLmsCourses, apiSyncExamGradesToLms,
  type Exam, type Submission, type AnalyticsData, type AuditLog, type LmsSettings, type LmsCourse
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  Cpu, LayoutDashboard, FileText, Upload, BarChart3, Shield, LogOut, Loader2,
  ChevronDown, AlertCircle, CheckCircle, Clock, Eye, EyeOff, X, Plus, Trash2,
  Menu, Gem, Link as LinkIcon
} from 'lucide-react'
import { UploadQuestionPaper } from '@/components/ui/upload-question-paper'
import { BulkUpload } from '@/components/ui/bulk-upload'
import { UpgradePrompt } from '@/components/ui/upgrade-prompt'
import { PricingModal } from '@/components/ui/pricing-modal'


type Tab = 'overview' | 'my-grades' | 'exams' | 'submissions' | 'analytics' | 'audit' | 'lms'

const sidebarItems: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'my-grades', label: 'My Grades', icon: LayoutDashboard },
  { key: 'exams', label: 'Exams', icon: FileText },
  { key: 'submissions', label: 'Submissions', icon: Upload },
  { key: 'lms', label: 'LMS Connect', icon: LinkIcon },
  { key: 'analytics', label: 'Analytics', icon: BarChart3 },
  { key: 'audit', label: 'Audit Logs', icon: Shield },
]

export default function DashboardPage() {
  const router = useRouter()
  const { user, isAuthenticated, isLoading: authLoading, logout } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  // Set default tab for student
  useEffect(() => {
    if (user?.role?.toLowerCase() === 'student') {
      setActiveTab('my-grades')
    }
  }, [user])

  // Data state
  const [exams, setExams] = useState<Exam[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Collapsible submissions state for student grades view
  const [expandedSubmissions, setExpandedSubmissions] = useState<Record<string, boolean>>({})

  // Upload state
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadForm, setUploadForm] = useState({ studentName: '', studentId: '', examId: '', file: null as File | null })

  // Override state
  const [overrideTarget, setOverrideTarget] = useState<Submission | null>(null)

  // Create Exam state
  const [createExamOpen, setCreateExamOpen] = useState(false)
  const [createMode, setCreateMode] = useState<'choose' | 'manual' | 'upload'>('choose')
  const [bulkUploadOpen, setBulkUploadOpen] = useState(false)
  const [createExamLoading, setCreateExamLoading] = useState(false)
  const [createExamForm, setCreateExamForm] = useState({
    title: '',
    subject: '',
    code: '',
    language: 'en',
    questions: [
      { question_number: 1, question_text: '', question_type: 'Short', max_marks: 10, model_answer: '' }
    ]
  })

  // LMS Integration state
  const [lmsType, setLmsType] = useState<'canvas' | 'moodle'>('canvas')
  const [lmsUrl, setLmsUrl] = useState('')
  const [lmsToken, setLmsToken] = useState('')
  const [showLmsToken, setShowLmsToken] = useState(false)
  const [lmsConfigured, setLmsConfigured] = useState(false)
  const [lmsCourses, setLmsCourses] = useState<LmsCourse[]>([])
  const [lmsLoading, setLmsLoading] = useState(false)

  const [syncModalOpen, setSyncModalOpen] = useState(false)
  const [syncTargetExam, setSyncTargetExam] = useState<Exam | null>(null)
  const [selectedLmsCourseId, setSelectedLmsCourseId] = useState('')
  const [selectedLmsAssignmentId, setSelectedLmsAssignmentId] = useState('')
  const [syncLoading, setSyncLoading] = useState(false)

  // Subscription state
  const [subStatus, setSubStatus] = useState<{
    plan: string
    papers_used: number
    papers_limit: number
    can_grade: boolean
    upgrade_required: boolean
    status: string
  } | null>(null)
  const [upgradeOpen, setUpgradeOpen] = useState(false)
  const [showPricingModal, setShowPricingModal] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true)
  const [isMobile, setIsMobile] = useState(false)

  // Detect screen size on mount and resize
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      
      const saved = localStorage.getItem('sidebar_expanded')
      if (saved !== null) {
        setIsExpanded(saved === 'true')
      } else {
        setIsExpanded(!mobile)
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const toggleSidebar = () => {
    const nextState = !isExpanded
    setIsExpanded(nextState)
    localStorage.setItem('sidebar_expanded', String(nextState))
  }

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [authLoading, isAuthenticated, router])

  // Fetch data on mount
  const fetchData = useCallback(async () => {
    if (!user) return
    setLoading(true)
    setError('')
    try {
      const isStudent = user.role.toLowerCase() === 'student'
      if (isStudent) {
        const { apiGetStudentSubmissions } = await import('@/lib/api')
        const [examsData, subsData] = await Promise.all([
          apiGetExams(),
          apiGetStudentSubmissions(),
        ])
        setExams(examsData)
        setSubmissions(subsData)
      } else {
        const [examsData, subsData] = await Promise.all([
          apiGetExams(),
          apiGetSubmissions(),
        ])
        setExams(examsData)
        setSubmissions(subsData)

        // Fetch subscription status
        try {
          const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const token = localStorage.getItem('sp_token') || ''
          const subRes = await fetch(`${API_BASE}/api/v1/subscription/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (subRes.ok) {
            const subData = await subRes.json()
            setSubStatus(subData)
          }
        } catch (subErr) {
          console.error("Subscription status fetch failed:", subErr)
        }


        if (examsData.length > 0) {
          const analyticsData = await apiGetAnalytics(examsData[0].id)
          setAnalytics(analyticsData)
        }

        try {
          const logs = await apiGetAuditLogs()
          setAuditLogs(logs)
        } catch {
          // User may not have permission for audit logs
        }

        // Fetch LMS settings
        try {
          const lmsSet = await apiGetLmsSettings()
          setLmsConfigured(lmsSet.configured)
          if (lmsSet.configured) {
            setLmsType(lmsSet.lms_type || 'canvas')
            setLmsUrl(lmsSet.api_url || '')
            const coursesData = await apiGetLmsCourses()
            setLmsCourses(coursesData)
          }
        } catch (lmsErr) {
          console.error("LMS config fetch failed:", lmsErr)
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    if (isAuthenticated) fetchData()
  }, [isAuthenticated, fetchData])

  // Upload handler
  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!uploadForm.file || !uploadForm.examId) return

    // Proactive usage check
    if (subStatus && !subStatus.can_grade) {
      setUploadOpen(false)
      setUpgradeOpen(true)
      return
    }

    setUploadLoading(true)
    try {
      await apiUploadPaper(uploadForm.studentName, uploadForm.studentId, uploadForm.examId, uploadForm.file)
      setUploadOpen(false)
      setUploadForm({ studentName: '', studentId: '', examId: '', file: null })
      await fetchData()
    } catch (err: any) {
      if (err.status === 402 || (err.message && err.message.includes('usage_limit_reached'))) {
        setUploadOpen(false)
        setUpgradeOpen(true)
      } else {
        setError(err.message || 'Upload failed')
      }
    } finally {
      setUploadLoading(false)
    }
  }


  // Override handler
  async function handleApprove(sub: Submission) {
    try {
      const overrides = sub.scores.map(s => ({
        question_number: s.question_number,
        override_score: s.final_score,
        override_reason: 'Approved as-is by reviewer'
      }))
      await apiOverrideScores({ submission_id: sub.id, overrides })
      await fetchData()
      setOverrideTarget(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Override failed')
    }
  }

  // Create Exam handler
  async function handleCreateExam(e: React.FormEvent) {
    e.preventDefault()
    if (!createExamForm.title || !createExamForm.subject || !createExamForm.code) {
      setError('Please fill in all basic exam details.')
      return
    }
    if (createExamForm.questions.length === 0) {
      setError('Please add at least one question.')
      return
    }
    setCreateExamLoading(true)
    setError('')
    try {
      const totalMarks = createExamForm.questions.reduce((sum, q) => sum + Number(q.max_marks), 0)
      const passingMarks = Math.round(totalMarks * 0.5)
      
      const payload = {
        title: createExamForm.title,
        subject: createExamForm.subject,
        code: createExamForm.code,
        language: createExamForm.language,
        total_marks: totalMarks,
        passing_marks: passingMarks,
        questions: createExamForm.questions.map((q, idx) => ({
          question_number: idx + 1,
          question_text: q.question_text,
          question_type: q.question_type,
          max_marks: Number(q.max_marks),
          model_answer: q.model_answer,
        }))
      }
      
      const newExam = await apiCreateExam(payload)
      setExams(prev => [newExam, ...prev])
      setCreateExamOpen(false)
      // Reset form
      setCreateExamForm({
        title: '',
        subject: '',
        code: '',
        language: 'en',
        questions: [
          { question_number: 1, question_text: '', question_type: 'Short', max_marks: 10, model_answer: '' }
        ]
      })
      await fetchData()
    } catch (err: any) {
      setError(err.message || 'Failed to create exam')
    } finally {
      setCreateExamLoading(false)
    }
  }

  // LMS Connect Handlers
  async function handleSaveLms(e: React.FormEvent) {
    e.preventDefault()
    if (!lmsUrl || !lmsToken) {
      setError('Please provide a valid server URL and API token.')
      return
    }
    setLmsLoading(true)
    setError('')
    try {
      await apiSaveLmsSettings({ lms_type: lmsType, api_url: lmsUrl, api_token: lmsToken })
      setLmsConfigured(true)
      const coursesData = await apiGetLmsCourses()
      setLmsCourses(coursesData)
      setLmsToken('') // Clear token display
    } catch (err: any) {
      setError(err.message || 'Failed to save LMS parameters.')
    } finally {
      setLmsLoading(false)
    }
  }

  async function handleSyncGrades(e: React.FormEvent) {
    e.preventDefault()
    if (!syncTargetExam || !selectedLmsCourseId || !selectedLmsAssignmentId) {
      setError('Please select a target LMS course and assignment.')
      return
    }
    setSyncLoading(true)
    setError('')
    try {
      const res = await apiSyncExamGradesToLms(syncTargetExam.id, selectedLmsCourseId, selectedLmsAssignmentId)
      setSyncModalOpen(false)
      await fetchData()
      alert(`Successfully synchronized ${res.synced_count} grades to ${lmsType.toUpperCase()} gradebook!`)
    } catch (err: any) {
      setError(err.message || 'Grades synchronization failed.')
    } finally {
      setSyncLoading(false)
    }
  }

  function handleLogout() {
    logout()
    router.push('/')
  }

  const handleUpgradeSuccess = useCallback(async () => {
    setUpgradeOpen(false)
    await fetchData()
  }, [fetchData])


  if (authLoading || (!isAuthenticated && !authLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
      </div>
    )
  }

  const isStudent = user?.role?.toLowerCase() === 'student'
  const allowedSidebarItems = sidebarItems.filter((item) => {
    if (isStudent) {
      return item.key === 'my-grades' || item.key === 'exams'
    } else {
      return item.key !== 'my-grades'
    }
  })

  const scoredCount = submissions.filter(s => s.status === 'Scored').length
  const flaggedCount = submissions.filter(s => s.status === 'Flagged').length
  const approvedCount = submissions.filter(s => s.status === 'Approved').length
  const avgConfidence = submissions.length > 0
    ? (submissions.reduce((a, s) => a + s.ai_confidence, 0) / submissions.length * 100).toFixed(1)
    : '0'

  return (
    <div className="min-h-screen flex bg-background">
      {/* Mobile Hamburger Menu Button when sidebar is closed */}
      {isMobile && !isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="fixed top-4 left-4 z-50 p-2 bg-slate-900/80 backdrop-blur border border-white/10 text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <Menu size={20} />
        </button>
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed left-0 top-0 h-full bg-[oklch(0.10_0.005_270)] border-r border-white/[0.08] z-40",
        "transition-all duration-300 ease-in-out flex flex-col py-6 px-4",
        isMobile
          ? (isExpanded ? "left-0 w-60" : "-left-60 w-60")
          : (isExpanded ? "w-60" : "w-16 px-2")
      )}>
        {/* Header with hamburger */}
        <div className="flex items-center h-16 px-1 mb-6 border-b border-white/[0.06] flex-shrink-0">
          <button
            onClick={toggleSidebar}
            className="text-slate-400 hover:text-white transition-colors cursor-pointer p-1 rounded-lg hover:bg-white/[0.05]"
          >
            {isExpanded ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className={cn(
            "ml-3 font-semibold text-white tracking-tight transition-all duration-300 overflow-hidden whitespace-nowrap",
            isExpanded ? "opacity-100 w-auto" : "opacity-0 w-0 pointer-events-none"
          )}>
            ScorePilot<span className="text-cyan-400">AI</span>
          </span>
        </div>
 
        <nav className="flex-1 space-y-1">
          {allowedSidebarItems.map((item) => (
            <button
              key={item.key}
              onClick={() => {
                setActiveTab(item.key)
                if (isMobile) setIsExpanded(false)
              }}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer relative group justify-start',
                activeTab === item.key
                  ? 'bg-white/[0.06] text-white'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]'
              )}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              <span className={cn(
                "transition-all duration-300 overflow-hidden whitespace-nowrap text-sm font-medium",
                isExpanded ? "opacity-100 w-auto" : "opacity-0 w-0 pointer-events-none"
              )}>
                {item.label}
              </span>
              {!isExpanded && (
                /* Tooltip on hover when collapsed */
                <span className="absolute left-14 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity shadow-lg border border-white/[0.05]">
                  {item.label}
                </span>
              )}
            </button>
          ))}
          
          {/* Upgrade Item */}
          <button
            onClick={() => setShowPricingModal(true)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 text-cyan-400 hover:from-cyan-500/20 hover:to-blue-500/20 hover:text-cyan-300 text-left relative group justify-start"
            )}
          >
            <Gem size={20} className="flex-shrink-0" />
            <span className={cn(
              "transition-all duration-300 overflow-hidden whitespace-nowrap text-sm font-medium",
              isExpanded ? "opacity-100 w-auto" : "opacity-0 w-0 pointer-events-none"
            )}>
              Upgrade
            </span>
            {!isExpanded && (
              /* Tooltip on hover when collapsed */
              <span className="absolute left-14 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity shadow-lg border border-white/[0.05]">
                Upgrade Plan
              </span>
            )}
          </button>
        </nav>

        {/* Bottom section */}
        <div className="mt-auto pt-4 border-t border-white/[0.06] space-y-3 flex-shrink-0">
          {isExpanded ? (
            /* Full upgrade section */
            <div className="space-y-3">
              <div className="px-3">
                <p className="text-sm font-medium text-white">{user?.username}</p>
                <p className="text-xs text-slate-500">{user?.role}</p>
              </div>

              {/* Sidebar Subscription Widget */}
              <div className="p-3 bg-white/[0.02] border border-white/[0.04] rounded-2xl space-y-2.5 mx-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-400 capitalize">
                    {subStatus?.plan ? `${subStatus.plan} Plan` : 'Free Plan'}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {subStatus?.papers_used ?? 0} / {subStatus?.papers_limit ?? 5} used
                  </span>
                </div>
                
                <div className="h-1 w-full bg-white/[0.04] rounded-full overflow-hidden border border-white/[0.08]">
                  <div
                    className="h-full rounded-full bg-cyan-500 transition-all duration-500"
                    style={{
                      width: `${Math.min(100, (((subStatus?.papers_used ?? 0) / (subStatus?.papers_limit ?? 5)) * 100))}%`
                    }}
                  />
                </div>

                <Button
                  onClick={() => setShowPricingModal(true)}
                  variant="outline"
                  size="sm"
                  className="w-full justify-center border-cyan-500/20 text-cyan-400 hover:bg-cyan-500/10 hover:text-cyan-300 text-[10px] py-1.5 h-auto rounded-xl flex items-center gap-1.5"
                >
                  <Gem size={12} />
                  <span>Upgrade Plan</span>
                </Button>
              </div>

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/5 transition-colors cursor-pointer justify-start"
              >
                <LogOut className="h-4 w-4 flex-shrink-0" />
                <span>Logout</span>
              </button>
            </div>
          ) : (
            /* Collapsed: just gem icon & logout icon */
            <div className="flex flex-col items-center gap-2">
              <button
                onClick={() => setShowPricingModal(true)}
                className="w-full flex justify-center p-2.5 text-cyan-400 hover:bg-cyan-500/10 rounded-xl transition-colors cursor-pointer relative group"
              >
                <Gem size={20} />
                <span className="absolute left-14 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity shadow-lg border border-white/[0.05]">
                  Upgrade Plan
                </span>
              </button>
              
              <button
                onClick={handleLogout}
                className="w-full flex justify-center p-2.5 text-slate-500 hover:text-red-400 hover:bg-red-500/5 rounded-xl transition-colors cursor-pointer relative group"
              >
                <LogOut size={20} />
                <span className="absolute left-14 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity shadow-lg border border-white/[0.05]">
                  Logout
                </span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile overlay backdrop */}
      {isMobile && isExpanded && (
        <div
          className="fixed inset-0 bg-black/60 z-30 transition-opacity duration-300"
          onClick={() => setIsExpanded(false)}
        />
      )}

      {/* Main content */}
      <main className={cn(
        "flex-grow flex-1 overflow-y-auto min-h-screen transition-all duration-300 ease-in-out",
        isMobile ? "ml-0" : (isExpanded ? "ml-60" : "ml-16")
      )}>
        <div className="border-b border-white/[0.04] bg-black/10 backdrop-blur-md px-8 py-3.5 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dashboard</span>
          <Link href="/pricing" className="text-xs font-semibold text-slate-400 hover:text-cyan-400 transition-colors">
            Pricing
          </Link>
        </div>
        <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">
          {/* Subscription Status Bar */}
          {subStatus && (
            <div className="glass-card rounded-2xl p-4 border border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-white capitalize">
                  {subStatus.plan} Plan
                </span>
                <span className="text-xs text-slate-500">
                  {subStatus.papers_used} / {subStatus.papers_limit} papers used
                </span>
                {subStatus.plan === 'free' && (
                  <button
                    onClick={() => setUpgradeOpen(true)}
                    className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold hover:underline bg-transparent border-0 cursor-pointer"
                  >
                    [Upgrade &rarr;]
                  </button>
                )}
              </div>
              <div className="flex items-center gap-3 w-full sm:w-64">
                <div className="h-2 w-full bg-white/[0.04] rounded-full overflow-hidden border border-white/[0.08]">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      subStatus.plan === 'free' && (subStatus.papers_used / subStatus.papers_limit) >= 0.8
                        ? "bg-red-500"
                        : "bg-gradient-to-r from-cyan-500 to-blue-500"
                    )}
                    style={{ width: `${Math.min(100, (subStatus.papers_used / (subStatus.papers_limit || 1)) * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400 mb-6">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
              <button onClick={() => setError('')} className="ml-auto cursor-pointer"><X className="h-3.5 w-3.5" /></button>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
            </div>
          ) : (
            <>
              {/* MY GRADES TAB FOR STUDENT */}
              {activeTab === 'my-grades' && (
                <div className="space-y-8 animate-in fade-in duration-300">
                  <div>
                    <h1 className="text-2xl font-semibold text-white tracking-tight">My Grades</h1>
                    <p className="text-sm text-slate-500 mt-1">
                      Welcome back, {user?.username}. View your submitted papers, AI scores, and reviews.
                    </p>
                  </div>

                  {/* Student Stats Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      { label: 'Exams Submitted', value: submissions.length, icon: FileText, color: 'text-cyan-400' },
                      { label: 'Graded / Approved', value: submissions.filter(s => s.status === 'Scored' || s.status === 'Approved').length, icon: CheckCircle, color: 'text-emerald-400' },
                      { label: 'Awaiting Grade', value: submissions.filter(s => s.status === 'Pending').length, icon: Clock, color: 'text-yellow-400' },
                    ].map((stat) => (
                      <div key={stat.label} className="glass-card rounded-2xl p-6">
                        <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] mb-4', stat.color)}>
                          <stat.icon className="h-5 w-5" />
                        </div>
                        <p className="text-3xl font-bold text-white tracking-tight">{stat.value}</p>
                        <p className="text-sm text-slate-500 mt-1">{stat.label}</p>
                      </div>
                    ))}
                  </div>

                  {/* My Grades List */}
                  <div className="space-y-4">
                    {submissions.length === 0 ? (
                      <div className="glass-card rounded-2xl p-12 text-center text-slate-500">
                        You haven&apos;t submitted any exam papers yet.
                      </div>
                    ) : (
                      submissions.map((sub) => {
                        const exam = exams.find(e => e.id === sub.exam_id)
                        const isExpanded = expandedSubmissions[sub.id]
                        const isPending = sub.status === 'Pending'

                        return (
                          <div key={sub.id} className="glass-card rounded-2xl p-6 transition-all duration-300">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">
                                    {exam?.code || 'EXAM'}
                                  </span>
                                  <span className="text-xs text-slate-500">
                                    Submitted {new Date(sub.created_at).toLocaleDateString()}
                                  </span>
                                </div>
                                <h3 className="text-lg font-semibold text-white tracking-tight">{exam?.title || 'Unknown Exam'}</h3>
                              </div>

                              <div className="flex items-center justify-between sm:justify-end gap-6">
                                <div className="text-left sm:text-right">
                                  <span className={cn(
                                    'text-xs px-2.5 py-1 rounded-full font-medium inline-block mb-1',
                                    sub.status === 'Pending' && 'bg-yellow-500/10 text-yellow-400',
                                    sub.status === 'Scored' && 'bg-cyan-500/10 text-cyan-400',
                                    sub.status === 'Flagged' && 'bg-yellow-500/10 text-yellow-400', // show flagged as Awaiting Review or Graded
                                    sub.status === 'Approved' && 'bg-emerald-500/10 text-emerald-400',
                                  )}>
                                    {sub.status === 'Flagged' ? 'Graded (Awaiting Review)' : sub.status}
                                  </span>
                                  {!isPending && (
                                    <div>
                                      <p className="text-2xl font-bold text-white tracking-tight">
                                        {sub.total_score}
                                        <span className="text-xs text-slate-500">/{exam?.total_marks || 0}</span>
                                      </p>
                                    </div>
                                  )}
                                </div>

                                {!isPending && (
                                  <button
                                    onClick={() => setExpandedSubmissions(prev => ({ ...prev, [sub.id]: !prev[sub.id] }))}
                                    className="p-2 rounded-lg bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all cursor-pointer"
                                  >
                                    <ChevronDown className={cn("h-4 w-4 transition-transform duration-300", isExpanded && "rotate-180")} />
                                  </button>
                                )}
                              </div>
                            </div>

                            {/* Collapsible Details */}
                            {isExpanded && !isPending && (
                              <div className="mt-6 pt-6 border-t border-white/[0.06] space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                                <div>
                                  <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-3">Question breakdown & Feedback</h4>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {sub.scores.map((sc) => {
                                      const matchingQ = exam?.questions.find(q => q.question_number === sc.question_number)
                                      return (
                                        <div key={sc.question_number} className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 space-y-3">
                                          <div className="flex justify-between items-start gap-2">
                                            <div>
                                              <span className="text-[10px] font-medium text-slate-500 font-mono">QUESTION {sc.question_number}</span>
                                              <p className="text-xs text-slate-300 font-medium line-clamp-1 mt-0.5">{matchingQ?.question_text || 'Exam Question'}</p>
                                            </div>
                                            <div className="text-right shrink-0">
                                              <span className="text-sm font-semibold text-white">
                                                {sc.final_score}
                                              </span>
                                              <span className="text-xs text-slate-500">/{matchingQ?.max_marks || 0}</span>
                                            </div>
                                          </div>
                                          <div className="text-xs text-slate-400 bg-white/[0.02] border border-white/[0.04] rounded-xl p-3 italic">
                                            {sc.feedback || 'No feedback available for this response.'}
                                          </div>
                                        </div>
                                      )
                                    })}
                                  </div>
                                </div>

                                <div className="flex flex-wrap items-center gap-4 pt-2">
                                  {sub.scanned_image_url && (
                                    <a
                                      href={sub.scanned_image_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors cursor-pointer"
                                    >
                                      <Eye className="h-4 w-4" /> View Graded Exam Paper Scan
                                    </a>
                                  )}
                                  <button
                                    onClick={async () => {
                                      try {
                                        await apiExportSubmissionPdf(sub.id, sub.student_name)
                                      } catch (err: any) {
                                        setError(err.message || 'PDF export failed')
                                      }
                                    }}
                                    className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors cursor-pointer bg-transparent border-0 p-0"
                                  >
                                    <FileText className="h-4 w-4" /> Export Verified PDF Report
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              )}

              {/* OVERVIEW TAB */}
              {activeTab === 'overview' && (
                exams.length === 0 && submissions.length === 0 ? (
                  <div className="space-y-8 animate-in fade-in duration-300">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Dashboard</h1>
                      <p className="text-sm text-slate-500 mt-1">Welcome back, {user?.username}</p>
                    </div>
                    <div className="glass-card rounded-3xl p-8 space-y-6">
                      <div className="text-center py-6">
                        <div className="text-6xl mb-4">🚀</div>
                        <h2 className="text-xl font-bold text-white mb-2">No data yet</h2>
                        <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
                          Welcome to ScorePilot AI! Follow these simple steps to start grading papers automatically.
                        </p>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-white/[0.01] border border-white/[0.04] p-5 rounded-2xl space-y-2">
                          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest font-mono">Step 1</span>
                          <h4 className="text-sm font-semibold text-white">Create an Exam</h4>
                          <p className="text-xs text-slate-400 leading-relaxed">
                            Define your exam code, subject, questions, and model answers either manually or via OCR upload.
                          </p>
                        </div>
                        <div className="bg-white/[0.01] border border-white/[0.04] p-5 rounded-2xl space-y-2">
                          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest font-mono">Step 2</span>
                          <h4 className="text-sm font-semibold text-white">Upload Papers</h4>
                          <p className="text-xs text-slate-400 leading-relaxed">
                            Upload scanned student sheets or run bulk imports of PDFs and images to trigger AI evaluation.
                          </p>
                        </div>
                        <div className="bg-white/[0.01] border border-white/[0.04] p-5 rounded-2xl space-y-2">
                          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest font-mono">Step 3</span>
                          <h4 className="text-sm font-semibold text-white">Review & LMS Sync</h4>
                          <p className="text-xs text-slate-400 leading-relaxed">
                            Review AI scoring feedback, override scores when needed, and sync grades to Canvas or Moodle.
                          </p>
                        </div>
                      </div>

                      {/* Onboarding Upgrade Banner */}
                      <div className="bg-white/[0.02] border border-white/[0.04] p-5 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4 mt-2">
                        <div className="flex items-center gap-3">
                          <span className="text-xl">🚀</span>
                          <div className="text-left">
                            <h4 className="text-sm font-semibold text-white">Need more than 5 papers/month?</h4>
                            <p className="text-xs text-slate-400 mt-0.5">Upgrade to Starter for ₹999/month — grade 200 papers.</p>
                          </div>
                        </div>
                        <Button
                          onClick={() => setShowPricingModal(true)}
                          variant="outline"
                          size="sm"
                          className="border-cyan-500/20 text-cyan-400 hover:bg-cyan-500/10 rounded-xl text-xs px-4 py-2 shrink-0 cursor-pointer"
                        >
                          View Plans &rarr;
                        </Button>
                      </div>

                      <div className="flex justify-center pt-4">
                        <button
                          onClick={() => { setCreateExamOpen(true); setCreateMode('choose'); }}
                          className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-6 py-3 rounded-lg transition-colors cursor-pointer"
                        >
                          Create Your First Exam &rarr;
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-8">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Dashboard</h1>
                      <p className="text-sm text-slate-500 mt-1">Welcome back, {user?.username}</p>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      {[
                        { label: 'Active Exams', value: exams.length, icon: FileText, color: 'text-cyan-400' },
                        { label: 'Total Submissions', value: submissions.length, icon: Upload, color: 'text-blue-400' },
                        { label: 'Flagged for Review', value: flaggedCount, icon: AlertCircle, color: 'text-yellow-400' },
                        { label: 'Avg AI Confidence', value: `${avgConfidence}%`, icon: BarChart3, color: 'text-emerald-400' },
                      ].map((stat) => (
                        <div key={stat.label} className="glass-card rounded-2xl p-6">
                          <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] mb-4', stat.color)}>
                            <stat.icon className="h-5 w-5" />
                          </div>
                          <p className="text-3xl font-bold text-white tracking-tight">{stat.value}</p>
                          <p className="text-sm text-slate-500 mt-1">{stat.label}</p>
                        </div>
                      ))}
                    </div>

                    {/* Recent submissions */}
                    <div className="glass-card rounded-2xl overflow-hidden">
                      <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
                        <h2 className="text-sm font-semibold text-white">Recent Submissions</h2>
                        <Button size="sm" variant="ghost" className="text-slate-400 text-xs" onClick={() => setActiveTab('submissions')}>
                          View All
                        </Button>
                      </div>
                      <div className="divide-y divide-white/[0.04]">
                        {submissions.slice(0, 5).map((sub) => (
                          <div key={sub.id} className="px-6 py-4 flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium text-white">{sub.student_name}</p>
                              <p className="text-xs text-slate-500">{sub.student_id} • {new Date(sub.created_at).toLocaleDateString()}</p>
                            </div>
                            <div className="flex items-center gap-4">
                              <span className="text-sm font-bold text-white">{sub.total_score}<span className="text-xs text-slate-500">/{exams.find(e => e.id === sub.exam_id)?.total_marks || '?'}</span></span>
                              <span className={cn(
                                'text-xs px-2.5 py-1 rounded-full font-medium',
                                sub.status === 'Scored' && 'bg-cyan-500/10 text-cyan-400',
                                sub.status === 'Flagged' && 'bg-yellow-500/10 text-yellow-400',
                                sub.status === 'Approved' && 'bg-emerald-500/10 text-emerald-400',
                              )}>
                                {sub.status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              )}


              {/* EXAMS TAB */}
              {activeTab === 'exams' && (
                <div className="space-y-8">
                  <div className="flex items-center justify-between">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Exams</h1>
                      <p className="text-sm text-slate-500 mt-1">{exams.length} active exams</p>
                    </div>
                    {(user?.role?.toLowerCase() === 'teacher' || user?.role?.toLowerCase() === 'admin') && (
                      <Button
                        size="sm"
                        className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium cursor-pointer"
                        onClick={() => { setCreateExamOpen(true); setCreateMode('choose'); }}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Create Exam
                      </Button>
                    )}
                  </div>

                  {/* Create Exam Modal */}
                  {createExamOpen && createMode === 'choose' && (
                    <div className="glass-card rounded-2xl p-6 space-y-6">
                      <div className="flex items-center justify-between border-b border-white/[0.04] pb-4">
                        <div>
                          <h3 className="text-base font-semibold text-white">Create New Exam</h3>
                          <p className="text-xs text-slate-500 mt-0.5">Choose how you want to create your exam questions.</p>
                        </div>
                        <button onClick={() => setCreateExamOpen(false)} className="text-slate-500 hover:text-white cursor-pointer">
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div 
                          onClick={() => setCreateMode('upload')}
                          className="border border-white/[0.08] hover:border-cyan-500/30 rounded-2xl p-6 text-center cursor-pointer transition-all bg-white/[0.01] hover:bg-cyan-500/[0.01] space-y-3"
                        >
                          <Upload className="h-8 w-8 text-cyan-400 mx-auto" />
                          <h4 className="text-sm font-semibold text-white">Upload Question Paper</h4>
                          <p className="text-xs text-slate-500">Upload your exam paper PDF/Image and extract questions automatically using AI OCR.</p>
                        </div>

                        <div 
                          onClick={() => setCreateMode('manual')}
                          className="border border-white/[0.08] hover:border-cyan-500/30 rounded-2xl p-6 text-center cursor-pointer transition-all bg-white/[0.01] hover:bg-cyan-500/[0.01] space-y-3"
                        >
                          <Plus className="h-8 w-8 text-cyan-400 mx-auto" />
                          <h4 className="text-sm font-semibold text-white">Create Manually</h4>
                          <p className="text-xs text-slate-500">Manually define your questions, types, and model answers step-by-step.</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {createExamOpen && createMode === 'upload' && (
                    <UploadQuestionPaper 
                      onSuccess={(newExam) => {
                        setExams(prev => [...prev, newExam])
                        setCreateExamOpen(false)
                      }}
                      onCancel={() => setCreateExamOpen(false)}
                    />
                  )}

                  {createExamOpen && createMode === 'manual' && (
                    <div className="glass-card rounded-2xl p-6 space-y-6">
                      <div className="flex items-center justify-between border-b border-white/[0.04] pb-4">
                        <div className="flex items-center gap-2">
                          <button onClick={() => setCreateMode('choose')} className="text-xs text-cyan-400 hover:underline mr-2">
                            &larr; Back
                          </button>
                          <div>
                            <h3 className="text-base font-semibold text-white">Create New Exam</h3>
                            <p className="text-xs text-slate-500 mt-0.5">Define exam metadata, language, and evaluation questions.</p>
                          </div>
                        </div>
                        <button onClick={() => setCreateExamOpen(false)} className="text-slate-500 hover:text-white cursor-pointer">
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      <form onSubmit={handleCreateExam} className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          <div className="md:col-span-2">
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Exam Title</label>
                            <input
                              type="text" placeholder="e.g. Biology Cell Structure Exam" required
                              value={createExamForm.title}
                              onChange={(e) => setCreateExamForm(f => ({ ...f, title: e.target.value }))}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Subject</label>
                            <input
                              type="text" placeholder="e.g. Biology" required
                              value={createExamForm.subject}
                              onChange={(e) => setCreateExamForm(f => ({ ...f, subject: e.target.value }))}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Exam Code</label>
                            <input
                              type="text" placeholder="e.g. BIO-101" required
                              value={createExamForm.code}
                              onChange={(e) => setCreateExamForm(f => ({ ...f, code: e.target.value }))}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Exam Language</label>
                            <select
                              value={createExamForm.language}
                              onChange={(e) => setCreateExamForm(f => ({ ...f, language: e.target.value }))}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                            >
                              <option value="en" className="bg-zinc-900">English (en)</option>
                              <option value="es" className="bg-zinc-900">Spanish (es)</option>
                              <option value="fr" className="bg-zinc-900">French (fr)</option>
                              <option value="de" className="bg-zinc-900">German (de)</option>
                            </select>
                          </div>
                        </div>

                        <div className="space-y-4 border-t border-white/[0.04] pt-4">
                          <div className="flex items-center justify-between">
                            <h4 className="text-sm font-semibold text-slate-300">Exam Questions</h4>
                            <Button
                              type="button" size="sm" variant="outline"
                              className="border-white/[0.08] text-cyan-400 hover:bg-white/[0.04] cursor-pointer"
                              onClick={() => setCreateExamForm(f => ({
                                ...f,
                                questions: [
                                  ...f.questions,
                                  { question_number: f.questions.length + 1, question_text: '', question_type: 'Short', max_marks: 10, model_answer: '' }
                                ]
                              }))}
                            >
                              <Plus className="h-3 w-3 mr-1" /> Add Question
                            </Button>
                          </div>

                          <div className="space-y-4">
                            {createExamForm.questions.map((q, idx) => (
                              <div key={idx} className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 space-y-3 relative">
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-semibold text-cyan-400 font-mono">Question #{idx + 1}</span>
                                  {createExamForm.questions.length > 1 && (
                                    <button
                                      type="button"
                                      className="text-slate-500 hover:text-red-400 cursor-pointer"
                                      onClick={() => setCreateExamForm(f => {
                                        const updatedQ = f.questions.filter((_, qIdx) => qIdx !== idx)
                                        return {
                                          ...f,
                                          questions: updatedQ.map((uq, uidx) => ({ ...uq, question_number: uidx + 1 }))
                                        }
                                      })}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </button>
                                  )}
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                                  <div className="md:col-span-2">
                                    <label className="block text-[10px] text-slate-500 mb-1">Question Prompt</label>
                                    <input
                                      type="text" placeholder="e.g. What is the role of mitochondria?" required
                                      value={q.question_text}
                                      onChange={(e) => setCreateExamForm(f => {
                                        const updatedQ = [...f.questions]
                                        updatedQ[idx].question_text = e.target.value
                                        return { ...f, questions: updatedQ }
                                      })}
                                      className="w-full h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-[10px] text-slate-500 mb-1">Response Type</label>
                                    <select
                                      value={q.question_type}
                                      onChange={(e) => setCreateExamForm(f => {
                                        const updatedQ = [...f.questions]
                                        updatedQ[idx].question_type = e.target.value as any
                                        return { ...f, questions: updatedQ }
                                      })}
                                      className="w-full h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 text-xs text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                                    >
                                      <option value="MCQ" className="bg-zinc-900">MCQ</option>
                                      <option value="Short" className="bg-zinc-900">Short</option>
                                      <option value="Long" className="bg-zinc-900">Long</option>
                                    </select>
                                  </div>
                                  <div>
                                    <label className="block text-[10px] text-slate-500 mb-1">Max Marks</label>
                                    <input
                                      type="number" min="1" max="100" required
                                      value={q.max_marks}
                                      onChange={(e) => setCreateExamForm(f => {
                                        const updatedQ = [...f.questions]
                                        updatedQ[idx].max_marks = Number(e.target.value)
                                        return { ...f, questions: updatedQ }
                                      })}
                                      className="w-full h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 text-xs text-white focus:outline-none focus:border-cyan-500/40"
                                    />
                                  </div>
                                </div>

                                <div>
                                  <label className="block text-[10px] text-slate-500 mb-1">Model Answer / Evaluator Rubric Criteria</label>
                                  <textarea
                                    placeholder="e.g. Mitochondria is the powerhouse of the cell generating ATP..." required rows={2}
                                    value={q.model_answer}
                                    onChange={(e) => setCreateExamForm(f => {
                                      const updatedQ = [...f.questions]
                                      updatedQ[idx].model_answer = e.target.value
                                      return { ...f, questions: updatedQ }
                                    })}
                                    className="w-full rounded-lg bg-white/[0.04] border border-white/[0.06] p-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 resize-y"
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-3 border-t border-white/[0.04] pt-4">
                          <Button
                            type="button" variant="outline" size="sm"
                            className="border-white/[0.08] hover:bg-white/[0.04] text-slate-300"
                            onClick={() => setCreateExamOpen(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            type="submit" size="sm" disabled={createExamLoading}
                            className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold"
                          >
                            {createExamLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                            Create Exam
                          </Button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="space-y-4">
                    {exams.map((exam) => (
                      <div key={exam.id} className="glass-card glass-card-hover rounded-2xl p-6">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-3 mb-2">
                              <span className="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">{exam.code}</span>
                              <span className="text-xs text-slate-500">{exam.subject}</span>
                              <span className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded uppercase">{exam.language || 'en'}</span>
                            </div>
                            <h3 className="text-lg font-semibold text-white">{exam.title}</h3>
                            <p className="text-xs text-slate-500 mt-1">
                              {exam.questions.length} questions • {exam.total_marks} total marks • Pass: {exam.passing_marks}
                            </p>
                          </div>
                          <span className={cn(
                            'text-xs px-2.5 py-1 rounded-full font-medium',
                            exam.status === 'Active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-500/10 text-slate-400'
                          )}>
                            {exam.status}
                          </span>
                        </div>

                        {/* Questions preview */}
                        <div className="mt-4 pt-4 border-t border-white/[0.04] space-y-2">
                          {exam.questions.map((q) => (
                            <div key={q.id} className="flex items-center justify-between text-xs">
                              <span className="text-slate-400">
                                Q{q.question_number}: {q.question_text.length > 60 ? q.question_text.slice(0, 60) + '...' : q.question_text}
                              </span>
                              <div className="flex items-center gap-3 shrink-0">
                                <span className={cn(
                                  'px-2 py-0.5 rounded text-[10px] font-medium',
                                  q.question_type === 'MCQ' && 'bg-blue-500/10 text-blue-400',
                                  q.question_type === 'Short' && 'bg-violet-500/10 text-violet-400',
                                  q.question_type === 'Long' && 'bg-cyan-500/10 text-cyan-400',
                                )}>
                                  {q.question_type}
                                </span>
                                <span className="text-slate-600">{q.max_marks}m</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SUBMISSIONS TAB */}
              {activeTab === 'submissions' && (
                <div className="space-y-8">
                  <div className="flex items-center justify-between">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Submissions</h1>
                      <p className="text-sm text-slate-500 mt-1">
                        {scoredCount} scored • {flaggedCount} flagged • {approvedCount} approved
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {lmsConfigured && exams.length > 0 && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-cyan-500/20 text-cyan-400 hover:bg-cyan-500/10 cursor-pointer"
                          onClick={() => {
                            setSyncTargetExam(exams[0])
                            setSyncModalOpen(true)
                          }}
                        >
                          <Cpu className="h-4 w-4 mr-2" />
                          Sync LMS Grades
                        </Button>
                      )}
                      {exams.length > 0 && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/[0.08] hover:bg-white/[0.04] text-slate-300 cursor-pointer"
                          onClick={async () => {
                            try {
                              await apiExportExamCsv(exams[0].id, exams[0].title)
                            } catch (err: any) {
                              setError(err.message || 'CSV export failed')
                            }
                          }}
                        >
                          <FileText className="h-4 w-4 mr-2" />
                          Export CSV
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium cursor-pointer"
                        onClick={() => setUploadOpen(true)}
                      >
                        <Upload className="h-4 w-4 mr-2" />
                        Upload Paper
                      </Button>
                      {(user?.role?.toLowerCase() === 'teacher' || user?.role?.toLowerCase() === 'admin') && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/[0.08] text-slate-300 hover:bg-white/[0.04] hover:text-white cursor-pointer"
                          onClick={() => setBulkUploadOpen(true)}
                        >
                          <Upload className="h-4 w-4 mr-2" />
                          Bulk Upload
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* LMS Sync Modal */}
                  {syncModalOpen && syncTargetExam && (
                    <div className="glass-card rounded-2xl p-6 space-y-4">
                      <div className="flex items-center justify-between border-b border-white/[0.04] pb-3">
                        <h3 className="text-sm font-semibold text-white">Sync Grades to LMS Gradebook</h3>
                        <button onClick={() => setSyncModalOpen(false)} className="text-slate-500 hover:text-white cursor-pointer"><X className="h-4 w-4" /></button>
                      </div>
                      <form onSubmit={handleSyncGrades} className="space-y-4">
                        <p className="text-xs text-slate-400">
                          This will synchronize all scored submission results for **{syncTargetExam.title}** directly to your connected {lmsType.toUpperCase()} account.
                        </p>
                        
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-[10px] text-slate-500 mb-1">Target Course</label>
                            <select
                              required value={selectedLmsCourseId}
                              onChange={(e) => {
                                setSelectedLmsCourseId(e.target.value)
                                setSelectedLmsAssignmentId('') // reset assignment selection
                              }}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                            >
                              <option value="" className="bg-zinc-900">Select LMS Course</option>
                              {lmsCourses.map(c => (
                                <option key={c.id} value={c.id} className="bg-zinc-900">{c.code} — {c.name}</option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label className="block text-[10px] text-slate-500 mb-1">Target Assignment</label>
                            <select
                              required value={selectedLmsAssignmentId}
                              onChange={(e) => setSelectedLmsAssignmentId(e.target.value)}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                              disabled={!selectedLmsCourseId}
                            >
                              <option value="" className="bg-zinc-900">Select LMS Assignment</option>
                              {lmsCourses.find(c => c.id === selectedLmsCourseId)?.assignments.map(a => (
                                <option key={a.id} value={a.id} className="bg-zinc-900">{a.name} ({a.max_points} pts)</option>
                              )) || []}
                            </select>
                          </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-2">
                          <Button
                            type="button" variant="outline" size="sm"
                            className="border-white/[0.08] hover:bg-white/[0.04] text-slate-300 cursor-pointer"
                            onClick={() => setSyncModalOpen(false)}
                          >
                            Cancel
                          </Button>
                          <Button type="submit" disabled={syncLoading} className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold cursor-pointer">
                            {syncLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Cpu className="h-4 w-4 mr-2" />}
                            Publish Grades
                          </Button>
                        </div>
                      </form>
                    </div>
                  )}

                  {/* Bulk Upload modal */}
                  {bulkUploadOpen && (
                    <BulkUpload 
                      onSuccess={() => {
                        setBulkUploadOpen(false)
                        fetchData()
                      }}
                      onCancel={() => setBulkUploadOpen(false)}
                    />
                  )}

                  {/* Upload modal */}
                  {uploadOpen && (
                    <div className="glass-card rounded-2xl p-6 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-white">Upload Answer Sheet</h3>
                        <button onClick={() => setUploadOpen(false)} className="text-slate-500 hover:text-white cursor-pointer"><X className="h-4 w-4" /></button>
                      </div>
                      <form onSubmit={handleUpload} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <input
                          type="text" placeholder="Student Name" required
                          value={uploadForm.studentName}
                          onChange={(e) => setUploadForm(f => ({ ...f, studentName: e.target.value }))}
                          className="h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                        />
                        <input
                          type="text" placeholder="Student ID" required
                          value={uploadForm.studentId}
                          onChange={(e) => setUploadForm(f => ({ ...f, studentId: e.target.value }))}
                          className="h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                        />
                        <select
                          required value={uploadForm.examId}
                          onChange={(e) => setUploadForm(f => ({ ...f, examId: e.target.value }))}
                          className="h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                        >
                          <option value="" className="bg-zinc-900">Select Exam</option>
                          {exams.map(ex => (
                            <option key={ex.id} value={ex.id} className="bg-zinc-900">{ex.code} — {ex.title}</option>
                          ))}
                        </select>
                        <input
                          type="file" required accept="image/*,.pdf"
                          onChange={(e) => setUploadForm(f => ({ ...f, file: e.target.files?.[0] || null }))}
                          className="h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-slate-400 file:mr-4 file:text-xs file:text-cyan-400 file:bg-transparent file:border-0 cursor-pointer"
                        />
                        <div className="sm:col-span-2">
                          <Button type="submit" disabled={uploadLoading} className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium">
                            {uploadLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
                            Submit for AI Grading
                          </Button>
                        </div>
                      </form>
                    </div>
                  )}

                  {/* Submissions list */}
                  <div className="space-y-3">
                    {submissions.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-96 gap-6 text-center">
                        <div className="text-6xl">📄</div>
                        <div>
                          <h3 className="text-xl font-semibold text-white mb-2">No submissions yet</h3>
                          <p className="text-slate-400 max-w-md">
                            No submissions yet, upload your first paper
                          </p>
                        </div>
                        <button
                          onClick={() => setUploadOpen(true)}
                          className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-6 py-3 rounded-lg transition-colors cursor-pointer"
                        >
                          Upload Your First Paper →
                        </button>
                      </div>
                    ) : (
                      submissions.map((sub) => (
                        <div key={sub.id} className="glass-card rounded-2xl p-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <div className="flex items-center gap-3 mb-1">
                                <h3 className="text-base font-semibold text-white">{sub.student_name}</h3>
                                <span className={cn(
                                  'text-xs px-2.5 py-0.5 rounded-full font-medium',
                                  sub.status === 'Scored' && 'bg-cyan-500/10 text-cyan-400',
                                  sub.status === 'Flagged' && 'bg-yellow-500/10 text-yellow-400',
                                  sub.status === 'Approved' && 'bg-emerald-500/10 text-emerald-400',
                                )}>
                                  {sub.status}
                                </span>
                              </div>
                              <p className="text-xs text-slate-500">
                                {sub.student_id} • {exams.find(e => e.id === sub.exam_id)?.code} • {new Date(sub.created_at).toLocaleString()}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-bold text-white">{sub.total_score}</p>
                              <p className="text-xs text-slate-500">AI Confidence: {(sub.ai_confidence * 100).toFixed(0)}%</p>
                            </div>
                          </div>

                          {/* Score breakdown */}
                          <div className="space-y-2 mb-4">
                            {sub.scores.map((sc) => (
                              <div key={sc.question_number} className="flex items-center justify-between py-2 border-t border-white/[0.04] first:border-0">
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs text-slate-400">Q{sc.question_number}</p>
                                  <p className="text-xs text-slate-600 truncate">{sc.feedback}</p>
                                </div>
                                <div className="flex items-center gap-4 shrink-0">
                                  <span className="text-sm font-semibold text-white">{sc.final_score}</span>
                                  <span className={cn(
                                    'text-[10px] font-mono',
                                    sc.ai_confidence >= 0.9 ? 'text-emerald-400' :
                                    sc.ai_confidence >= 0.7 ? 'text-yellow-400' : 'text-orange-400'
                                  )}>
                                    {(sc.ai_confidence * 100).toFixed(0)}%
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Actions */}
                          <div className="flex flex-wrap items-center gap-2">
                            {(sub.status === 'Scored' || sub.status === 'Approved' || sub.status === 'Flagged') && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="border-white/[0.08] hover:bg-white/[0.04] text-slate-400 hover:text-white cursor-pointer"
                                onClick={async () => {
                                  try {
                                    await apiExportSubmissionPdf(sub.id, sub.student_name)
                                  } catch (err: any) {
                                    setError(err.message || 'PDF export failed')
                                  }
                                }}
                              >
                                <FileText className="h-4 w-4 mr-1.5" /> Export PDF
                              </Button>
                            )}
                            {sub.status === 'Flagged' && (
                              <>
                                <Button size="sm" className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer" onClick={() => handleApprove(sub)}>
                                  <CheckCircle className="h-4 w-4 mr-1" /> Approve
                                </Button>
                                <Button size="sm" variant="ghost" className="text-slate-400 cursor-pointer" onClick={() => setOverrideTarget(sub)}>
                                  Review Details
                                </Button>
                              </>
                            )}
                            {sub.status === 'Approved' && sub.reviewer_id && (
                              <p className="text-xs text-slate-600 self-center">Reviewed by {sub.reviewer_id} on {sub.reviewed_at ? new Date(sub.reviewed_at).toLocaleString() : 'N/A'}</p>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                </div>
              )}

              {/* LMS CONNECT TAB */}
              {activeTab === 'lms' && (
                <div className="space-y-8">
                  <div>
                    <h1 className="text-2xl font-semibold text-white tracking-tight">LMS Connect</h1>
                    <p className="text-sm text-slate-500 mt-1">Connect your institutional Canvas or Moodle environments to synchronize evaluation grades.</p>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* LMS Setup card */}
                    <div className="lg:col-span-1 glass-card rounded-2xl p-6 space-y-4 h-fit">
                      <div className="flex items-center gap-3 pb-3 border-b border-white/[0.04]">
                        <Cpu className="h-5 w-5 text-cyan-400" />
                        <h3 className="text-sm font-semibold text-white">Connection Profile</h3>
                      </div>

                      <form onSubmit={handleSaveLms} className="space-y-4">
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 mb-1.5">LMS Platform Type</label>
                          <select
                            value={lmsType}
                            onChange={(e) => setLmsType(e.target.value as any)}
                            className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40 cursor-pointer"
                          >
                            <option value="canvas" className="bg-zinc-900">Canvas LMS</option>
                            <option value="moodle" className="bg-zinc-900">Moodle LMS</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-400 mb-1.5">API Server URL</label>
                          <input
                            type="url" placeholder={lmsType === 'canvas' ? 'https://canvas.instructure.com/api/v1' : 'https://moodle.university.edu/webservice/rest/server.php'} required
                            value={lmsUrl}
                            onChange={(e) => setLmsUrl(e.target.value)}
                            className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-400 mb-1.5">API Developer Token</label>
                          <div className="relative">
                            <input
                              type={showLmsToken ? "text" : "password"} placeholder="••••••••••••••••••••••••••••••••" required
                              value={lmsToken}
                              onChange={(e) => setLmsToken(e.target.value)}
                              className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-4 pr-12 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                            />
                            <button
                              type="button"
                              onClick={() => setShowLmsToken(!showLmsToken)}
                              className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors cursor-pointer"
                              tabIndex={-1}
                              aria-label={showLmsToken ? "Hide token" : "Show token"}
                            >
                              {showLmsToken ? (
                                <EyeOff size={18} />
                              ) : (
                                <Eye size={18} />
                              )}
                            </button>
                          </div>
                        </div>

                        <Button type="submit" disabled={lmsLoading} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-semibold cursor-pointer">
                          {lmsLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Cpu className="h-4 w-4 mr-2" />}
                          Save & Test Connection
                        </Button>
                      </form>

                      {lmsConfigured ? (
                        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 flex items-start gap-3">
                          <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-semibold text-emerald-400">Connection Connected</p>
                            <p className="text-[10px] text-slate-400 mt-0.5">Connected to {lmsType.toUpperCase()} server. Ready to synchronize gradebooks.</p>
                          </div>
                        </div>
                      ) : (
                        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
                          <AlertCircle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-semibold text-amber-400">Not Connected</p>
                            <p className="text-[10px] text-slate-400 mt-0.5">Please provide connection parameters to authorize class directories sync.</p>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Course catalog card */}
                    <div className="lg:col-span-2 glass-card rounded-2xl p-6 space-y-4">
                      <div className="flex items-center justify-between pb-3 border-b border-white/[0.04]">
                        <h3 className="text-sm font-semibold text-white">Imported Course Catalog</h3>
                        {lmsConfigured && (
                          <span className="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2.5 py-0.5 rounded-full uppercase">{lmsType} Mode</span>
                        )}
                      </div>

                      {!lmsConfigured ? (
                        <div className="flex flex-col items-center justify-center text-center p-12 space-y-3">
                          <Cpu className="h-10 w-10 text-slate-700" />
                          <div>
                            <h4 className="text-sm font-medium text-slate-400">No LMS Courses Imported</h4>
                            <p className="text-xs text-slate-600 mt-1 max-w-sm">Provide your integration configurations in the side panel to dynamically fetch courses directories from your Canvas or Moodle platform.</p>
                          </div>
                        </div>
                      ) : lmsCourses.length === 0 ? (
                        <div className="flex flex-col items-center justify-center text-center p-12 space-y-3">
                          <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
                          <h4 className="text-xs text-slate-500">Querying LMS courses repository...</h4>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {lmsCourses.map((c) => (
                            <div key={c.id} className="bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all rounded-xl p-4 space-y-3">
                              <div>
                                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">{c.code}</span>
                                <h4 className="text-sm font-semibold text-white mt-1.5">{c.name}</h4>
                              </div>
                              <div className="border-t border-white/[0.04] pt-3 space-y-1.5">
                                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">LMS Assignments</p>
                                {c.assignments.length === 0 ? (
                                  <p className="text-xs text-slate-600 italic">No assignments found for this course.</p>
                                ) : (
                                  c.assignments.map((a) => (
                                    <div key={a.id} className="flex items-center justify-between text-xs">
                                      <span className="text-slate-400">{a.name}</span>
                                      <span className="text-slate-600 shrink-0">{a.max_points} points</span>
                                    </div>
                                  ))
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* ANALYTICS TAB */}
              {activeTab === 'analytics' && (
                !analytics || exams.length === 0 || analytics.papers_processed === 0 ? (
                  <div className="space-y-8 animate-in fade-in duration-300">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Analytics</h1>
                    </div>
                    <div className="flex flex-col items-center justify-center 
                                    h-96 gap-6 text-center">
                      <div className="text-6xl">📊</div>
                      <div>
                        <h3 className="text-xl font-semibold text-white mb-2">
                          No analytics yet
                        </h3>
                        <p className="text-slate-400 max-w-md">
                          Analytics will appear here after you create your first 
                          exam and grade some student submissions.
                        </p>
                      </div>
                      <a href="/dashboard/exams" 
                         onClick={(e) => { e.preventDefault(); setActiveTab('exams'); }}
                         className="bg-cyan-500 hover:bg-cyan-400 text-black 
                                    font-semibold px-6 py-3 rounded-lg 
                                    transition-colors">
                        Create Your First Exam →
                      </a>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-8 animate-in fade-in duration-300">
                    <div>
                      <h1 className="text-2xl font-semibold text-white tracking-tight">Analytics</h1>
                      <p className="text-sm text-slate-500 mt-1">{analytics.exam_title}</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="glass-card rounded-2xl p-6 text-center">
                        <p className="text-3xl font-bold text-white">{analytics.papers_processed}</p>
                        <p className="text-sm text-slate-500 mt-1">Papers Processed</p>
                      </div>
                      <div className="glass-card rounded-2xl p-6 text-center">
                        <p className="text-3xl font-bold text-white">{analytics.average_score}</p>
                        <p className="text-sm text-slate-500 mt-1">Average Score</p>
                      </div>
                      <div className="glass-card rounded-2xl p-6 text-center">
                        <p className="text-3xl font-bold text-cyan-400">{analytics.pass_count > 0 ? ((analytics.pass_count / analytics.papers_processed) * 100).toFixed(0) : 0}%</p>
                        <p className="text-sm text-slate-500 mt-1">Pass Rate ({analytics.pass_count}P / {analytics.fail_count}F)</p>
                      </div>
                    </div>

                    {/* Score distribution */}
                    <div className="glass-card rounded-2xl p-8">
                      <h3 className="text-lg font-semibold text-white mb-6">Score Distribution</h3>
                      <div className="space-y-3">
                        {Object.entries(analytics.score_distribution).map(([range, count]) => (
                          <div key={range} className="flex items-center gap-4">
                            <span className="text-xs text-slate-500 w-16 text-right font-mono">{range}</span>
                            <div className="flex-1 h-6 rounded-lg bg-white/[0.04] overflow-hidden">
                              <div
                                className="h-full rounded-lg bg-gradient-to-r from-cyan-500/40 to-cyan-400/60 flex items-center justify-end pr-3"
                                style={{ width: `${analytics.papers_processed > 0 ? (count / analytics.papers_processed * 100) : 0}%`, minWidth: count > 0 ? '30px' : '0' }}
                              >
                                <span className="text-[10px] font-medium text-white/80">{count}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Question difficulty */}
                    <div className="glass-card rounded-2xl p-8">
                      <h3 className="text-lg font-semibold text-white mb-6">Question Difficulty Index</h3>
                      <div className="space-y-3">
                        {analytics.question_difficulty.map((q) => (
                          <div key={q.question_number} className="flex items-center gap-4">
                            <span className="text-xs text-slate-500 w-8 font-mono">Q{q.question_number}</span>
                            <div className="flex-1">
                              <div className="flex justify-between mb-1">
                                <span className="text-xs text-slate-400 truncate max-w-xs">{q.question_text_short}</span>
                                <span className={cn(
                                  'text-xs font-medium',
                                  q.difficulty_percentage >= 80 ? 'text-emerald-400' :
                                  q.difficulty_percentage >= 50 ? 'text-yellow-400' : 'text-orange-400'
                                )}>
                                  {q.difficulty_percentage}%
                                </span>
                              </div>
                              <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                <div
                                  className={cn(
                                    'h-full rounded-full',
                                    q.difficulty_percentage >= 80 ? 'bg-emerald-500' :
                                    q.difficulty_percentage >= 50 ? 'bg-yellow-500' : 'bg-orange-500'
                                  )}
                                  style={{ width: `${q.difficulty_percentage}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              )}


              {/* AUDIT TAB */}
              {activeTab === 'audit' && (
                <div className="space-y-8">
                  <div>
                    <h1 className="text-2xl font-semibold text-white tracking-tight">Audit Logs</h1>
                    <p className="text-sm text-slate-500 mt-1">{auditLogs.length} events recorded</p>
                  </div>

                  <div className="glass-card rounded-2xl overflow-hidden divide-y divide-white/[0.04]">
                    {auditLogs.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-80 gap-4 text-center p-8">
                        <div className="text-5xl animate-bounce duration-1000">🛡️</div>
                        <div>
                          <h3 className="text-lg font-semibold text-white mb-1">No activity yet</h3>
                          <p className="text-xs text-slate-500 max-w-sm">
                            System actions and administrator activities will be recorded here once you begin performing grading tasks.
                          </p>
                        </div>
                      </div>
                    ) : (
                      auditLogs.map((log) => (
                        <div key={log.id} className="px-6 py-4 flex items-start justify-between animate-in fade-in duration-200">
                          <div className="flex items-start gap-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.04] shrink-0 mt-0.5">
                              <Clock className="h-3.5 w-3.5 text-slate-500" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-white">{log.action}</p>
                              <p className="text-xs text-slate-500 mt-0.5">
                                by <span className="text-cyan-400">{log.user}</span> • {new Date(log.timestamp).toLocaleString()}
                              </p>
                              {log.details && (
                                <p className="text-xs text-slate-600 mt-1 font-mono">
                                  {JSON.stringify(log.details).slice(0, 120)}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                </div>
              )}
            </>
          )}
        </div>
        {upgradeOpen && subStatus && (
          <UpgradePrompt
            papersUsed={subStatus.papers_used}
            papersLimit={subStatus.papers_limit}
            onSuccess={handleUpgradeSuccess}
            onClose={() => setUpgradeOpen(false)}
          />
        )}
        <PricingModal
          isOpen={showPricingModal}
          onClose={() => setShowPricingModal(false)}
          subStatus={subStatus}
          onSuccess={fetchData}
        />
      </main>
    </div>
  )
}

