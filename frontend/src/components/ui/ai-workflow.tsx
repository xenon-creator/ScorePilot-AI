'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Upload, ScanText, BrainCircuit, UserCheck, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'

const steps = [
  {
    icon: Upload,
    title: 'Upload Papers',
    description: 'Batch upload scanned answer sheets, PDFs, or images. Supports 50+ formats with automatic orientation correction.',
    accent: 'cyan',
  },
  {
    icon: ScanText,
    title: 'OCR Extraction',
    description: 'AI-powered handwriting recognition extracts student responses with 98.7% accuracy across multiple languages.',
    accent: 'blue',
  },
  {
    icon: BrainCircuit,
    title: 'AI Scoring',
    description: 'Semantic analysis engine compares responses against rubrics using transformer-based models for nuanced evaluation.',
    accent: 'violet',
  },
  {
    icon: UserCheck,
    title: 'Human Review',
    description: 'Educators review AI suggestions with full explainability. Override, adjust, or approve scores with confidence indicators.',
    accent: 'emerald',
  },
  {
    icon: BarChart3,
    title: 'Analytics Dashboard',
    description: 'Real-time performance insights, score distributions, and AI accuracy metrics across cohorts and assessments.',
    accent: 'cyan',
  },
]

const accentColors: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  cyan: { bg: 'bg-cyan-400/10', text: 'text-cyan-400', border: 'border-cyan-400/20', glow: 'shadow-cyan-500/10' },
  blue: { bg: 'bg-blue-400/10', text: 'text-blue-400', border: 'border-blue-400/20', glow: 'shadow-blue-500/10' },
  violet: { bg: 'bg-violet-400/10', text: 'text-violet-400', border: 'border-violet-400/20', glow: 'shadow-violet-500/10' },
  emerald: { bg: 'bg-emerald-400/10', text: 'text-emerald-400', border: 'border-emerald-400/20', glow: 'shadow-emerald-500/10' },
}

export function AIWorkflow() {
  const [hoveredIndex, setHoveredIndex] = React.useState<number | null>(null)

  return (
    <section id="workflow" className="relative py-24 md:py-32 lg:py-40">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <span className="text-sm font-medium text-cyan-400 uppercase tracking-widest">How It Works</span>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl lg:text-6xl">
            From paper to insight<br />
            <span className="text-gradient-cyan">in five steps.</span>
          </h2>
          <p className="mt-6 mx-auto max-w-2xl text-lg text-slate-400">
            A seamless pipeline that transforms handwritten exams into actionable academic intelligence.
          </p>
        </motion.div>

        {/* Workflow steps */}
        <div className="relative">
          {/* Connecting line (desktop) */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-white/[0.08] to-transparent hidden lg:block" />

          {/* Connecting line (mobile) - hidden when stacked vertically and centered */}
          <div className="absolute left-8 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-white/[0.08] to-transparent hidden lg:hidden" />

          <div className="space-y-8 lg:space-y-16">
            {steps.map((step, index) => {
              const colors = accentColors[step.accent]
              const isEven = index % 2 === 0

              return (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className={cn(
                    'relative flex flex-col items-center gap-4 lg:gap-0 lg:grid lg:grid-cols-2',
                  )}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  {/* Step icon on the line */}
                  <div className="relative z-10 flex-shrink-0 lg:absolute lg:left-1/2 lg:-translate-x-1/2">
                    <div 
                      className={cn(
                        'flex h-12 w-12 md:h-14 md:w-14 items-center justify-center rounded-2xl border shadow-lg transition-shadow duration-300',
                        colors.bg, colors.border, `shadow-2xl ${colors.glow}`,
                        'bg-zinc-950'
                      )}
                      style={{
                        boxShadow: hoveredIndex === index ? '0 0 16px oklch(0.75 0.15 200 / 30%)' : undefined
                      }}
                    >
                      <step.icon className={cn('h-6 w-6', colors.text)} />
                    </div>
                  </div>

                  {/* Content card - alternating sides on desktop */}
                  <div className={cn(
                    'w-full flex justify-center lg:flex',
                    isEven ? 'lg:col-start-1 lg:justify-end lg:pr-20' : 'lg:col-start-2 lg:pl-20',
                  )}>
                    <div className="glass-card glass-card-hover rounded-2xl p-6 w-full max-w-md text-left">
                      <div className="flex items-center gap-3 mb-3">
                        <span className={cn('text-xs font-mono uppercase tracking-wider', colors.text)}>
                          Step {String(index + 1).padStart(2, '0')}
                        </span>
                      </div>
                      <h3 className="text-xl font-semibold text-white tracking-tight">{step.title}</h3>
                      <p className="mt-2 text-sm text-slate-400 leading-relaxed">{step.description}</p>
                    </div>
                  </div>

                  {/* Empty column for alternating layout */}
                  {isEven && <div className="hidden lg:block lg:col-start-2" />}
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
