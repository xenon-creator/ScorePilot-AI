'use client'

import React, { useState, useRef } from 'react'
import { UploadCloud, Trash2, Plus, ArrowRight, ArrowLeft, Loader2, Sparkles, BookOpen, AlertCircle } from 'lucide-react'
import { Button } from './button'

interface QuestionItem {
  text: string
  type: 'MCQ' | 'Short' | 'Long'
  max_marks: number
  model_answer: string
}

interface UploadQuestionPaperProps {
  onSuccess: (exam: any) => void
  onCancel: () => void
}

export function UploadQuestionPaper({ onSuccess, onCancel }: UploadQuestionPaperProps) {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  // Step 1: Upload state
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Step 2: Review state
  const [questions, setQuestions] = useState<QuestionItem[]>([])

  // Step 3: Metadata state
  const [metadata, setMetadata] = useState({
    title: '',
    subject: '',
    language: 'en'
  })

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const startOcr = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = ''
      const response = await fetch(`${API_BASE}/api/v1/exams/upload-paper`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error('Failed to extract questions from the question paper.')
      }

      const data = await response.json()
      
      // Map extracted questions to Step 2 editable structure
      const parsedQuestions: QuestionItem[] = data.questions.map((q: any) => ({
        text: q.text || '',
        type: q.marks_hint === 1 ? 'MCQ' : q.marks_hint <= 5 ? 'Short' : 'Long',
        max_marks: q.marks_hint || 10,
        model_answer: ''
      }))

      setQuestions(parsedQuestions.length > 0 ? parsedQuestions : [
        { text: '', type: 'Short', max_marks: 10, model_answer: '' }
      ])
      setStep(2)
    } catch (err: any) {
      setError(err.message || 'Error occurred during OCR extraction.')
    } finally {
      setLoading(false)
    }
  }

  const updateQuestion = (index: number, fields: Partial<QuestionItem>) => {
    setQuestions(prev => prev.map((q, idx) => idx === index ? { ...q, ...fields } : q))
  }

  const addQuestion = () => {
    setQuestions(prev => [
      ...prev,
      { text: '', type: 'Short', max_marks: 10, model_answer: '' }
    ])
  }

  const removeQuestion = (index: number) => {
    setQuestions(prev => prev.filter((_, idx) => idx !== index))
  }

  const createExam = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!metadata.title.trim() || !metadata.subject.trim()) {
      setError('Exam title and subject are required.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const payload = {
        title: metadata.title,
        subject: metadata.subject,
        language: metadata.language,
        questions: questions.map(q => ({
          text: q.text,
          type: q.type,
          max_marks: q.max_marks,
          model_answer: q.model_answer
        }))
      }

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = ''
      const response = await fetch(`${API_BASE}/api/v1/exams/from-paper`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error('Failed to create the exam.')
      }

      const createdExam = await response.json()
      onSuccess(createdExam)
    } catch (err: any) {
      setError(err.message || 'Failed to create exam.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass-card rounded-2xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.04] pb-4">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-400" />
            Create Exam via Question Paper OCR
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Step {step} of 3 — {step === 1 ? 'Upload Paper' : step === 2 ? 'Review Questions' : 'Exam Details'}
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

      {/* STEP 1: Upload file */}
      {step === 1 && (
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
              accept=".pdf,.jpg,.jpeg,.png,.tiff"
              className="hidden"
            />
            <div className="flex justify-center">
              <UploadCloud className="h-10 w-10 text-slate-500" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">Drag & drop question paper here</p>
              <p className="text-xs text-slate-500 mt-1">Supports PDF, JPG, PNG, or TIFF files up to 10MB</p>
            </div>
            {file && (
              <div className="inline-flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] px-3.5 py-1.5 rounded-full text-xs text-cyan-400">
                <BookOpen className="h-3.5 w-3.5" />
                <span className="max-w-[200px] truncate">{file.name}</span>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 border-t border-white/[0.04] pt-4">
            <Button variant="ghost" size="sm" onClick={onCancel} className="text-slate-400 hover:text-white">
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!file || loading}
              onClick={startOcr}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Extracting Questions...
                </>
              ) : (
                <>
                  Next <ArrowRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* STEP 2: Review questions */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="space-y-4 max-h-[450px] overflow-y-auto pr-1 no-scrollbar">
            {questions.map((q, idx) => (
              <div key={idx} className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 space-y-4 relative">
                <button
                  type="button"
                  onClick={() => removeQuestion(idx)}
                  className="absolute top-3 right-3 text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400">
                  <span>Question {idx + 1}</span>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Question Text</label>
                    <input
                      type="text" required
                      value={q.text}
                      onChange={(e) => updateQuestion(idx, { text: e.target.value })}
                      placeholder="Enter the question text"
                      className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Type</label>
                      <select
                        value={q.type}
                        onChange={(e) => updateQuestion(idx, { type: e.target.value as any })}
                        className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                      >
                        <option value="MCQ" className="bg-zinc-950">Multiple Choice (MCQ)</option>
                        <option value="Short" className="bg-zinc-950">Short Answer</option>
                        <option value="Long" className="bg-zinc-950">Long Answer / Essay</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Max Marks</label>
                      <input
                        type="number" min={1} required
                        value={q.max_marks}
                        onChange={(e) => updateQuestion(idx, { max_marks: Number(e.target.value) })}
                        className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Model Answer / Evaluation Criteria</label>
                    <textarea
                      rows={2} required
                      value={q.model_answer}
                      onChange={(e) => updateQuestion(idx, { model_answer: e.target.value })}
                      placeholder="Describe the correct answer to guide AI grading"
                      className="w-full rounded-xl bg-white/[0.04] border border-white/[0.08] p-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 font-sans leading-relaxed"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Button
            type="button" variant="outline" size="sm" onClick={addQuestion}
            className="w-full border-dashed border-white/[0.08] text-cyan-400 hover:bg-white/[0.04] cursor-pointer"
          >
            <Plus className="h-4 w-4 mr-2" /> Add Question
          </Button>

          <div className="flex justify-between items-center border-t border-white/[0.04] pt-4">
            <Button variant="ghost" size="sm" onClick={() => setStep(1)} className="text-slate-400 hover:text-white">
              <ArrowLeft className="h-4 w-4 mr-2" /> Back
            </Button>
            <Button
              size="sm"
              onClick={() => setStep(3)}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium"
            >
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 3: Exam details */}
      {step === 3 && (
        <form onSubmit={createExam} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5">Exam Title</label>
              <input
                type="text" placeholder="e.g. Biology Cell Structure Exam" required
                value={metadata.title}
                onChange={(e) => setMetadata(prev => ({ ...prev, title: e.target.value }))}
                className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5">Subject</label>
              <input
                type="text" placeholder="e.g. Biology" required
                value={metadata.subject}
                onChange={(e) => setMetadata(prev => ({ ...prev, subject: e.target.value }))}
                className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
              />
            </div>
          </div>

          <div className="flex justify-between items-center border-t border-white/[0.04] pt-4">
            <Button type="button" variant="ghost" size="sm" onClick={() => setStep(2)} className="text-slate-400 hover:text-white">
              <ArrowLeft className="h-4 w-4 mr-2" /> Back
            </Button>
            <Button
              type="submit" size="sm" disabled={loading}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating Exam...
                </>
              ) : (
                'Create Exam'
              )}
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}
