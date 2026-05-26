'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Users, Zap, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

const metrics = [
  { label: 'Papers Graded', value: '12,847', change: '+2,340 this week', icon: Users, accent: 'cyan' },
  { label: 'Average Score', value: '73.4', change: '+4.2 vs last term', icon: TrendingUp, accent: 'emerald' },
  { label: 'AI Accuracy', value: '96.8%', change: '+1.3% improvement', icon: Zap, accent: 'violet' },
  { label: 'Avg Review Time', value: '18s', change: '-42% with AI assist', icon: Clock, accent: 'blue' },
]

const accentMap: Record<string, { bg: string; text: string; border: string }> = {
  cyan: { bg: 'bg-cyan-400/10', text: 'text-cyan-400', border: 'border-cyan-400/20' },
  emerald: { bg: 'bg-emerald-400/10', text: 'text-emerald-400', border: 'border-emerald-400/20' },
  violet: { bg: 'bg-violet-400/10', text: 'text-violet-400', border: 'border-violet-400/20' },
  blue: { bg: 'bg-blue-400/10', text: 'text-blue-400', border: 'border-blue-400/20' },
}

const scoreDistribution = [
  { range: '90-100', count: 18, percentage: 15 },
  { range: '80-89', count: 31, percentage: 26 },
  { range: '70-79', count: 28, percentage: 23 },
  { range: '60-69', count: 22, percentage: 18 },
  { range: '50-59', count: 12, percentage: 10 },
  { range: '0-49', count: 9, percentage: 8 },
]

export function AnalyticsSection() {
  return (
    <section id="analytics" className="relative py-24 md:py-32 lg:py-40">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <span className="text-sm font-medium text-blue-400 uppercase tracking-widest">Analytics</span>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl lg:text-6xl">
            Insights that<br />
            <span className="text-gradient-cyan">drive decisions.</span>
          </h2>
          <p className="mt-6 mx-auto max-w-2xl text-lg text-slate-400">
            Real-time analytics across cohorts, assessments, and AI performance — all in one elegant dashboard.
          </p>
        </motion.div>

        {/* Metrics grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {metrics.map((metric, index) => {
            const colors = accentMap[metric.accent]
            return (
              <motion.div
                key={metric.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="glass-card glass-card-hover rounded-2xl p-6"
              >
                <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl border mb-4', colors.bg, colors.border)}>
                  <metric.icon className={cn('h-5 w-5', colors.text)} />
                </div>
                <p className="text-3xl font-bold text-white tracking-tight">{metric.value}</p>
                <p className="text-sm text-slate-400 mt-1">{metric.label}</p>
                <p className={cn('text-xs mt-2 font-medium', colors.text)}>{metric.change}</p>
              </motion.div>
            )
          })}
        </div>

        {/* Score distribution + Pass/Fail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Score Distribution */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6 }}
            className="glass-card rounded-2xl p-8 lg:col-span-2"
          >
            <h3 className="text-lg font-semibold text-white mb-6">Score Distribution</h3>
            <div className="space-y-3">
              {scoreDistribution.map((item) => (
                <div key={item.range} className="flex items-center gap-4">
                  <span className="text-xs text-slate-500 w-14 text-right font-mono">{item.range}</span>
                  <div className="flex-1 h-6 rounded-lg bg-white/[0.04] overflow-hidden">
                    <motion.div
                      className={cn(
                        'h-full rounded-lg flex items-center justify-end pr-3',
                        item.percentage >= 20 ? 'bg-gradient-to-r from-cyan-500/40 to-cyan-400/60' :
                        item.percentage >= 15 ? 'bg-gradient-to-r from-blue-500/40 to-blue-400/60' :
                        item.percentage >= 10 ? 'bg-gradient-to-r from-violet-500/40 to-violet-400/60' :
                        'bg-gradient-to-r from-slate-500/30 to-slate-400/40'
                      )}
                      initial={{ width: 0 }}
                      whileInView={{ width: `${item.percentage * 3.5}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 1, delay: 0.3 }}
                    >
                      <span className="text-[10px] font-medium text-white/80">{item.count}</span>
                    </motion.div>
                  </div>
                  <span className="text-xs text-slate-500 w-10 font-mono">{item.percentage}%</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Pass/Fail Ratio */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="glass-card rounded-2xl p-8"
          >
            <h3 className="text-lg font-semibold text-white mb-6">Pass / Fail Ratio</h3>
            <div className="flex items-center justify-center py-4">
              <div className="relative h-36 w-36">
                <svg className="h-full w-full -rotate-90" viewBox="0 0 128 128">
                  <circle cx="64" cy="64" r="52" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="12" />
                  <circle
                    cx="64" cy="64" r="52" fill="none"
                    stroke="#06b6d4"
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${0.82 * 326.726} ${326.726}`}
                  />
                  <circle
                    cx="64" cy="64" r="52" fill="none"
                    stroke="rgba(239,68,68,0.5)"
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${0.18 * 326.726} ${326.726}`}
                    strokeDashoffset={`${-0.82 * 326.726}`}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-white">82%</span>
                  <span className="text-xs text-slate-500">pass rate</span>
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-center gap-6">
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
                <span className="text-xs text-slate-400">Pass (99)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400/60" />
                <span className="text-xs text-slate-400">Fail (21)</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
