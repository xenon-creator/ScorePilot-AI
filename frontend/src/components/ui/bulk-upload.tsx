'use client'

import React, { useState, useEffect, useRef } from 'react'
import { UploadCloud, FileText, CheckCircle2, Loader2, AlertCircle, Play, ArrowRight, Download, Eye } from 'lucide-react'
import { Button } from './button'

interface Exam {
  id: string
  title: string
  total_marks: number
}

interface Submission {
  id: string
  student_name: string
  total_score: number
  status: 'Pending' | 'Scored' | 'Flagged' | 'Approved'
}

interface BulkUploadProps {
  onSuccess: () => void
  onCancel: () => void
}

export function BulkUpload({ onSuccess, onCancel }: BulkUploadProps) {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Step 1: Select Exam state
  const [exams, setExams] = useState<Exam[]>([])
  const [selectedExamId, setSelectedExamId] = useState('')

  // Step 2: Upload Files state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Step 3: Processing state
  const [jobId, setJobId] = useState('')
  const [jobStatus, setJobStatus] = useState({
    status: 'processing',
    processed: 0,
    total: 0
  })
  const [submissionIds, setSubmissionIds] = useState<string[]>([])
  const [submissionsList, setSubmissionsList] = useState<Submission[]>([])
  const [startTime, setStartTime] = useState<number | null>(null)
  const [duration, setDuration] = useState('')

  // Step 4: Summary data
  const [flaggedCount, setFlaggedCount] = useState(0)

  // Fetch exams on step 1 mount
  useEffect(() => {
    if (step === 1) {
      const fetchExams = async () => {
        setLoading(true)
        setError('')
        try {
          const token = localStorage.getItem('sp_token') || ''
          const API_BASE = ''
          const res = await fetch(`${API_BASE}/api/v1/exams`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (!res.ok) throw new Error('Failed to fetch exams.')
          const data = await res.json()
          setExams(data)
          if (data.length > 0) {
            setSelectedExamId(data[0].id)
          }
        } catch (err: any) {
          setError(err.message || 'Failed to load exams list.')
        } finally {
          setLoading(false)
        }
      }
      fetchExams()
    }
  }, [step])

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files) {
      const filesArr = Array.from(e.dataTransfer.files).filter(f =>
        /\.(pdf|jpg|jpeg|png|tiff)$/i.test(f.name)
      )
      if (filesArr.length > 0) {
        setSelectedFiles(prev => [...prev, ...filesArr].slice(0, 50))
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArr = Array.from(e.target.files)
      setSelectedFiles(prev => [...prev, ...filesArr].slice(0, 50))
    }
  }

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, idx) => idx !== index))
  }

  // Trigger POST /api/v1/uploads/bulk
  const startBulkUpload = async () => {
    if (selectedFiles.length === 0 || !selectedExamId) return
    setLoading(true)
    setError('')
    setStartTime(Date.now())
    setStep(3)

    try {
      const formData = new FormData()
      formData.append('exam_id', selectedExamId)
      selectedFiles.forEach(file => {
        formData.append('files', file)
      })

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = ''
      const response = await fetch(`${API_BASE}/api/v1/uploads/bulk`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error('Failed to upload the bulk submissions.')
      }

      const data = await response.json()
      setJobId(data.job_id)
      setSubmissionIds(data.submission_ids)
      setJobStatus({
        status: 'processing',
        processed: 0,
        total: data.total
      })
    } catch (err: any) {
      setError(err.message || 'Bulk upload request failed.')
      setStep(2)
      setLoading(false)
    }
  }

  // Poll bulk status and submission details
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (step === 3 && jobId) {
      const pollStatus = async () => {
        try {
          const token = localStorage.getItem('sp_token') || ''
          const API_BASE = ''

          // 1. Get job status
          const statusRes = await fetch(`${API_BASE}/api/v1/uploads/bulk/status/${jobId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (!statusRes.ok) throw new Error('Status poll failed')
          const statusData = await statusRes.json()
          setJobStatus(statusData)

          // 2. Fetch submissions details to render student list
          const subsRes = await fetch(`${API_BASE}/api/v1/submissions?exam_id=${selectedExamId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (subsRes.ok) {
            const subsData = await subsRes.json()
            const filteredSubs = subsData.filter((s: any) => submissionIds.includes(s.id))
            setSubmissionsList(filteredSubs)
          }

          // 3. Complete step transition
          if (statusData.status === 'complete') {
            clearInterval(interval)
            const endTime = Date.now()
            const diffMs = endTime - (startTime || endTime)
            const min = Math.floor(diffMs / 60000)
            const sec = ((diffMs % 60000) / 1000).toFixed(0)
            setDuration(min > 0 ? `${min}m ${sec}s` : `${sec}s`)

            // Calculate flagged count
            const flagged = submissionsList.filter(s => s.status === 'Flagged').length
            setFlaggedCount(flagged)
            setStep(4)
          }
        } catch (err) {
          console.error('Error polling status:', err)
        }
      }

      // Initial call and set interval
      pollStatus()
      interval = setInterval(pollStatus, 2000)
    }

    return () => clearInterval(interval)
  }, [step, jobId, submissionIds, selectedExamId, submissionsList, startTime])

  // Export CSV helper
  const handleExportCSV = () => {
    const token = localStorage.getItem('sp_token') || ''
    const API_BASE = ''
    window.open(`${API_BASE}/api/v1/exams/${selectedExamId}/export/csv?token=${token}`, '_blank')
  }

  const selectedExam = exams.find(e => e.id === selectedExamId)

  return (
    <div className="glass-card rounded-2xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.04] pb-4">
        <div>
          <h3 className="text-base font-semibold text-white">Bulk Student Submissions Upload</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Step {step} of 4 — {step === 1 ? 'Select Exam' : step === 2 ? 'Upload Files' : step === 3 ? 'AI Ingestion' : 'Summary'}
          </p>
        </div>
        <button onClick={onCancel} className="text-slate-500 hover:text-white cursor-pointer transition-colors">
          Cancel
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2.5 bg-red-500/10 border border-red-500/20 rounded-xl p-3.5 text-xs text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* STEP 1: Select Exam */}
      {step === 1 && (
        <div className="space-y-6">
          {loading ? (
            <div className="flex justify-center items-center py-10">
              <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
            </div>
          ) : exams.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-sm">
              Please create an exam first before uploading answer sheets.
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5">Select Exam Target</label>
                <select
                  value={selectedExamId}
                  onChange={(e) => setSelectedExamId(e.target.value)}
                  className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                >
                  {exams.map(e => (
                    <option key={e.id} value={e.id} className="bg-zinc-950">{e.title}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 border-t border-white/[0.04] pt-4">
            <Button variant="ghost" size="sm" onClick={onCancel} className="text-slate-400 hover:text-white">
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!selectedExamId || loading}
              onClick={() => setStep(2)}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium disabled:opacity-50"
            >
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 2: Upload Files */}
      {step === 2 && (
        <div className="space-y-6">
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="border border-dashed border-white/[0.08] hover:border-cyan-500/30 rounded-2xl p-10 text-center cursor-pointer transition-all bg-white/[0.01] hover:bg-cyan-500/[0.01] space-y-4"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.tiff"
              className="hidden"
            />
            <div className="flex justify-center">
              <UploadCloud className="h-10 w-10 text-slate-500" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">Drag & drop student sheets here</p>
              <p className="text-xs text-slate-500 mt-1">Upload up to 50 answer sheets (.pdf, .jpg, .png, .tiff)</p>
            </div>
            {selectedFiles.length > 0 && (
              <span className="inline-block bg-cyan-500/10 text-cyan-400 text-xs px-3 py-1 rounded-full font-medium">
                {selectedFiles.length} files selected
              </span>
            )}
          </div>

          {selectedFiles.length > 0 && (
            <div className="max-h-[200px] overflow-y-auto space-y-2 no-scrollbar">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between bg-white/[0.02] border border-white/[0.04] p-3 rounded-xl text-xs">
                  <div className="flex items-center gap-2 text-slate-300">
                    <FileText className="h-4 w-4 text-slate-500" />
                    <span className="max-w-[250px] truncate">{file.name}</span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                    className="text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-between items-center border-t border-white/[0.04] pt-4">
            <Button variant="ghost" size="sm" onClick={() => setStep(1)} className="text-slate-400 hover:text-white">
              Back
            </Button>
            <Button
              size="sm"
              disabled={selectedFiles.length === 0 || loading}
              onClick={startBulkUpload}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium disabled:opacity-50"
            >
              Start Ingestion <Play className="h-4 w-4 ml-2 fill-current" />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 3: Processing view */}
      {step === 3 && (
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
              <span>Processing {jobStatus.processed} / {jobStatus.total} answer sheets...</span>
              <span>{Math.round((jobStatus.processed / (jobStatus.total || 1)) * 100)}%</span>
            </div>
            <div className="h-2 w-full bg-white/[0.04] rounded-full overflow-hidden border border-white/[0.08]">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${(jobStatus.processed / (jobStatus.total || 1)) * 100}%` }}
              />
            </div>
          </div>

          <div className="max-h-[300px] overflow-y-auto space-y-2 no-scrollbar">
            {submissionsList.length === 0 ? (
              <div className="flex items-center justify-center py-6 text-xs text-slate-500">
                <Loader2 className="h-4 w-4 text-cyan-400 animate-spin mr-2" /> Initializing grading workers...
              </div>
            ) : (
              submissionsList.map((sub) => {
                const isPending = sub.status === 'Pending'
                const isFlagged = sub.status === 'Flagged'
                
                return (
                  <div key={sub.id} className="flex items-center justify-between bg-white/[0.02] border border-white/[0.04] p-3 rounded-xl text-xs">
                    <span className="text-slate-300 font-medium">{sub.student_name}</span>
                    <span className="flex items-center gap-2">
                      {isPending ? (
                        <span className="text-yellow-400 flex items-center gap-1.5">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing...
                        </span>
                      ) : (
                        <span className="text-slate-400 flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                          Scored {sub.total_score} {selectedExam ? `/${selectedExam.total_marks}` : ''}
                          {isFlagged && <span className="text-yellow-500 font-semibold ml-1">(flagged)</span>}
                        </span>
                      )}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* STEP 4: Summary */}
      {step === 4 && (
        <div className="space-y-6">
          <div className="text-center py-6 space-y-3">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mb-2">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h4 className="text-lg font-bold text-white">Bulk Ingestion Completed!</h4>
            <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed">
              {jobStatus.total} exam papers have been successfully processed, digitized, and scored by ScorePilot AI in <span className="text-cyan-400 font-semibold">{duration}</span>.
            </p>
            {flaggedCount > 0 && (
              <p className="text-xs text-yellow-400/90 bg-yellow-500/10 border border-yellow-500/20 inline-block px-3.5 py-1 rounded-full">
                ⚠️ {flaggedCount} submissions flagged for human review.
              </p>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-3 border-t border-white/[0.04] pt-4">
            <Button
              onClick={onSuccess}
              className="flex-1 bg-cyan-500 hover:bg-cyan-400 text-black font-medium justify-center"
            >
              <Eye className="h-4 w-4 mr-2" /> View Results
            </Button>
            <Button
              variant="outline"
              onClick={handleExportCSV}
              className="flex-1 border-white/[0.08] text-slate-300 hover:bg-white/[0.04] hover:text-white justify-center"
            >
              <Download className="h-4 w-4 mr-2" /> Export CSV
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
