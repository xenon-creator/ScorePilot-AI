'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Sparkles, Target, Eye, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ScoringShowcase() {
  return (
    <section id="scoring" className="relative py-24 md:py-32 lg:py-40">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <span className="text-sm font-medium text-violet-400 uppercase tracking-widest">AI Intelligence</span>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl lg:text-6xl">
            Scoring that<br />
            <span className="text-gradient-violet">understands meaning.</span>
          </h2>
          <p className="mt-6 mx-auto max-w-2xl text-lg text-slate-400">
            Go beyond keyword matching. ScorePilot uses transformer-based semantic analysis to evaluate the quality of reasoning, not just surface-level answers.
          </p>
        </motion.div>

        {/* Scoring panels grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Confidence Meter */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6 }}
            className="glass-card glass-card-hover rounded-2xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/10 border border-cyan-400/20">
                <Target className="h-5 w-5 text-cyan-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Confidence Score</h3>
                <p className="text-xs text-slate-500">Real-time evaluation certainty</p>
              </div>
            </div>
            {/* Circular confidence meter */}
            <div className="flex items-center justify-center py-6">
              <div className="relative h-40 w-40">
                <svg className="h-full w-full -rotate-90" viewBox="0 0 128 128">
                  <circle cx="64" cy="64" r="56" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
                  <circle
                    cx="64" cy="64" r="56" fill="none"
                    stroke="url(#confidence-gradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${0.942 * 351.858} ${351.858}`}
                  />
                  <defs>
                    <linearGradient id="confidence-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#06b6d4" />
                      <stop offset="100%" stopColor="#3b82f6" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-white">94.2%</span>
                  <span className="text-xs text-slate-500 mt-1">confidence</span>
                </div>
              </div>
            </div>
            <p className="text-center text-sm text-slate-400">Model certainty for current evaluation batch</p>
          </motion.div>

          {/* Rubric Matching */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="glass-card glass-card-hover rounded-2xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-400/10 border border-violet-400/20">
                <Sparkles className="h-5 w-5 text-violet-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Rubric Matching</h3>
                <p className="text-xs text-slate-500">Criteria-level analysis</p>
              </div>
            </div>
            <div className="space-y-4">
              {[
                { criteria: 'Problem Understanding', score: 95, status: 'Excellent' },
                { criteria: 'Solution Approach', score: 88, status: 'Strong' },
                { criteria: 'Mathematical Accuracy', score: 92, status: 'Excellent' },
                { criteria: 'Explanation Quality', score: 76, status: 'Good' },
                { criteria: 'Edge Case Handling', score: 64, status: 'Developing' },
              ].map((item) => (
                <div key={item.criteria}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-slate-300">{item.criteria}</span>
                    <span className={cn(
                      'text-xs font-medium',
                      item.score >= 90 ? 'text-emerald-400' : item.score >= 75 ? 'text-yellow-400' : 'text-orange-400'
                    )}>{item.status}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-1000',
                        item.score >= 90 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
                        item.score >= 75 ? 'bg-gradient-to-r from-yellow-500 to-yellow-400' :
                        'bg-gradient-to-r from-orange-500 to-orange-400'
                      )}
                      style={{ width: `${item.score}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Explainable AI */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="glass-card glass-card-hover rounded-2xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-400/10 border border-emerald-400/20">
                <Eye className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Explainable AI</h3>
                <p className="text-xs text-slate-500">Transparent reasoning</p>
              </div>
            </div>
            <div className="space-y-3">
              <div className="glass-card rounded-xl p-4">
                <p className="text-xs text-slate-500 mb-1">AI Reasoning</p>
                <p className="text-sm text-slate-300 leading-relaxed">
                  &quot;The student correctly identified the derivative using the chain rule but omitted the constant of integration in the final step. Partial credit awarded for methodology.&quot;
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-card rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-white">7</p>
                  <p className="text-xs text-slate-500 mt-1">Points Awarded</p>
                </div>
                <div className="glass-card rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-white">10</p>
                  <p className="text-xs text-slate-500 mt-1">Max Points</p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* OCR Confidence */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="glass-card glass-card-hover rounded-2xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-400/10 border border-blue-400/20">
                <ShieldCheck className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">OCR Confidence</h3>
                <p className="text-xs text-slate-500">Extraction reliability</p>
              </div>
            </div>
            <div className="space-y-3">
              {[
                { field: 'Student Name', confidence: 99.8, value: 'Sarah Chen' },
                { field: 'Question 1', confidence: 97.2, value: 'dx/dt = 2x + 3...' },
                { field: 'Question 2', confidence: 94.5, value: '∫ sin(x)dx = ...' },
                { field: 'Question 3', confidence: 88.1, value: 'lim x→0 f(x)...' },
                { field: 'Question 4', confidence: 91.3, value: 'det(A) = ad-bc...' },
              ].map((item) => (
                <div key={item.field} className="flex items-center justify-between py-1">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-500">{item.field}</p>
                    <p className="text-sm text-slate-300 truncate">{item.value}</p>
                  </div>
                  <span className={cn(
                    'text-xs font-mono font-medium ml-4',
                    item.confidence >= 95 ? 'text-emerald-400' : item.confidence >= 90 ? 'text-yellow-400' : 'text-orange-400'
                  )}>
                    {item.confidence}%
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
