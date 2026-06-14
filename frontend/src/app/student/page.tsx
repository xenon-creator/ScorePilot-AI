"use client"

import { useState } from "react"

interface Answer {
  question_number: number
  question_text: string
  student_answer: string
  ai_score: number
  final_score: number
  ai_confidence: number
  ai_reasoning: string
  max_marks: number
}

interface Submission {
  submission_id: string
  exam_title: string
  student_name: string
  status: string
  total_score: number
  max_score: number
  ai_confidence: number
  uploaded_at: string
  answers: Answer[]
}

export default function StudentPortalPage() {
  const [name, setName] = useState("")
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<Submission[]>([])
  const [error, setError] = useState("")
  const [searched, setSearched] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    setLoading(true)
    setError("")
    setSearched(true)
    try {
      const API_BASE = ""
      const res = await fetch(`${API_BASE}/api/v1/student/results?student_name=${encodeURIComponent(name.trim())}`)
      if (!res.ok) {
        throw new Error(`Failed to fetch: ${res.statusText}`)
      }
      const data = await res.json()
      setResults(data)
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#07070a] text-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent sm:text-5xl">
            ScorePilot AI Student Portal
          </h1>
          <p className="mt-3 text-lg text-gray-400">
            Enter your name to see your graded exams and detailed AI evaluation feedback.
          </p>
        </div>

        {/* Search Form */}
        <div className="bg-[#111115] border border-white/5 rounded-2xl p-6 mb-8 shadow-xl">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
            <input
              type="text"
              placeholder="e.g. Charlie Test Results"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 bg-[#16161b] border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-cyan-500 hover:bg-cyan-400 disabled:bg-cyan-800 text-black font-semibold px-6 py-3 rounded-xl transition-all shadow-md active:scale-95"
            >
              {loading ? "Searching..." : "Retrieve Grades"}
            </button>
          </form>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-950/50 border border-red-500/20 text-red-300 rounded-xl p-4 mb-8 text-center">
            {error}
          </div>
        )}

        {/* Results list */}
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-500"></div>
          </div>
        ) : searched && results.length === 0 ? (
          <div className="text-center py-12 text-gray-400 bg-[#111115] border border-white/5 rounded-2xl">
            No graded submissions found for "{name}".
          </div>
        ) : (
          <div className="space-y-8">
            {results.map((sub) => (
              <div
                key={sub.submission_id}
                className="bg-[#111115] border border-white/5 rounded-2xl p-6 shadow-lg overflow-hidden"
              >
                {/* Submission Header Card */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-white/5 pb-4 mb-6 gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-white">{sub.exam_title}</h2>
                    <p className="text-sm text-gray-400 mt-1">
                      Student: <span className="text-cyan-400 font-semibold">{sub.student_name}</span> | ID: {sub.submission_id.slice(0, 8)}...
                    </p>
                  </div>
                  <div className="bg-[#16161b] border border-white/10 rounded-xl p-3 text-right">
                    <span className="text-xs text-gray-500 uppercase block font-semibold tracking-wider">Score</span>
                    <span className="text-3xl font-extrabold text-cyan-400">
                      {sub.total_score}
                      <span className="text-base text-gray-500 font-normal"> / {sub.max_score}</span>
                    </span>
                  </div>
                </div>

                {/* Question breakdown */}
                <h3 className="text-lg font-semibold text-gray-200 mb-4">Question Breakdown</h3>
                <div className="space-y-4">
                  {sub.answers.map((ans) => (
                    <div
                      key={ans.question_number}
                      className="bg-[#16161b] border border-white/5 rounded-xl p-4"
                    >
                      <div className="flex justify-between items-start mb-2 gap-4">
                        <span className="text-xs font-bold text-cyan-400 bg-cyan-950/40 px-2.5 py-1 rounded-md uppercase tracking-wider">
                          Q{ans.question_number}
                        </span>
                        <span className="text-sm font-semibold text-white">
                          Marks: <span className="text-cyan-400">{ans.final_score}</span> / {ans.max_marks}
                        </span>
                      </div>
                      
                      <div className="text-gray-300 text-sm font-semibold mb-3 leading-relaxed">
                        {ans.question_text}
                      </div>

                      <div className="bg-[#0b0f19] rounded-lg p-3 border border-white/5 mb-3">
                        <span className="text-xs text-gray-500 block mb-1">Your Answer:</span>
                        <p className="text-sm text-gray-300 leading-relaxed font-mono whitespace-pre-wrap">
                          {ans.student_answer || "(No answer provided)"}
                        </p>
                      </div>

                      <div className="bg-cyan-950/10 rounded-lg p-3 border border-cyan-500/10">
                        <span className="text-xs text-cyan-400 font-semibold block mb-1">AI Evaluator Feedback:</span>
                        <p className="text-sm text-cyan-200/90 leading-relaxed">
                          {ans.ai_reasoning}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
