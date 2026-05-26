'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, ArrowRight, ThumbsUp, ThumbsDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export function HumanReview() {
  return (
    <section className="relative py-24 md:py-32 lg:py-40">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <span className="text-sm font-medium text-emerald-400 uppercase tracking-widest">Human-in-the-Loop</span>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl lg:text-6xl">
            AI assists.<br />
            <span className="text-gradient-cyan">You decide.</span>
          </h2>
          <p className="mt-6 mx-auto max-w-2xl text-lg text-slate-400">
            Full transparency and control. Every AI score comes with an explanation, and teachers always have the final word.
          </p>
        </motion.div>

        {/* Review interface mock */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.8 }}
          className="glass-card rounded-2xl overflow-hidden"
        >
          {/* Top bar */}
          <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-white">Review Queue</span>
              <span className="text-xs text-slate-500 bg-white/[0.06] px-2.5 py-1 rounded-full">24 remaining</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Paper 17 of 41</span>
              <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
            {/* Student Answer Panel */}
            <div className="p-6 md:p-8">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Student Response</span>
                <span className="text-xs text-slate-500">Q3 — Calculus</span>
              </div>
              <div className="glass-card rounded-xl p-5">
                <p className="text-sm text-slate-300 leading-relaxed font-mono">
                  To find the derivative of f(x) = x³sin(x), I used the product rule:
                  <br /><br />
                  f&apos;(x) = 3x²sin(x) + x³cos(x)
                  <br /><br />
                  Setting f&apos;(x) = 0:
                  <br />
                  x²(3sin(x) + xcos(x)) = 0
                  <br />
                  x = 0 or 3sin(x) + xcos(x) = 0
                </p>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-xs px-2 py-1 rounded bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">Product Rule ✓</span>
                <span className="text-xs px-2 py-1 rounded bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">Differentiation ✓</span>
                <span className="text-xs px-2 py-1 rounded bg-yellow-400/10 text-yellow-400 border border-yellow-400/20">Incomplete</span>
              </div>
            </div>

            {/* AI Assessment Panel */}
            <div className="p-6 md:p-8">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">AI Assessment</span>
                <span className="text-xs text-cyan-400 font-medium">Confidence: 91%</span>
              </div>

              {/* AI Score */}
              <div className="glass-card rounded-xl p-5 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-slate-400">AI Suggested Score</span>
                  <span className="text-2xl font-bold text-white">8<span className="text-sm text-slate-500">/10</span></span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Student correctly applied the product rule and found the derivative. Critical points partially identified — missing analysis of the transcendental equation.
                </p>
              </div>

              {/* Teacher Actions */}
              <div className="space-y-3">
                <div className="flex gap-2">
                  <button className="flex-1 flex items-center justify-center gap-2 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-400/20 text-sm font-medium hover:bg-emerald-500/20 transition-colors cursor-pointer">
                    <ThumbsUp className="h-4 w-4" />
                    Approve
                  </button>
                  <button className="flex-1 flex items-center justify-center gap-2 h-10 rounded-xl bg-orange-500/10 text-orange-400 border border-orange-400/20 text-sm font-medium hover:bg-orange-500/20 transition-colors cursor-pointer">
                    <ThumbsDown className="h-4 w-4" />
                    Adjust
                  </button>
                </div>
                <button className="w-full flex items-center justify-center gap-2 h-10 rounded-xl bg-white/[0.03] text-slate-400 border border-white/[0.08] text-sm hover:bg-white/[0.06] transition-colors cursor-pointer">
                  <MessageSquare className="h-4 w-4" />
                  Add Note
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
