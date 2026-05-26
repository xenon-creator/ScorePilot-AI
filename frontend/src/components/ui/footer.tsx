import Link from 'next/link'
import { cn } from '@/lib/utils'

const footerLinks = {
  Product: ['Platform', 'Pricing', 'Integrations', 'Changelog', 'Documentation'],
  Research: ['AI Scoring', 'OCR Technology', 'Semantic Analysis', 'Case Studies', 'Benchmarks'],
  Company: ['About', 'Careers', 'Blog', 'Press Kit', 'Contact'],
  Legal: ['Privacy Policy', 'Terms of Service', 'Security', 'Compliance'],
}

export function Footer() {
  return (
    <footer className="relative border-t border-white/[0.06]">
      {/* Gradient line at top */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />

      <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 md:gap-12">
          {/* Brand column */}
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="relative flex h-7 w-7 items-center justify-center">
                <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 opacity-80" />
                <svg viewBox="0 0 24 24" fill="none" className="relative z-10 h-4 w-4 text-black" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <span className="text-lg font-semibold tracking-tight text-white">ScorePilot<span className="text-cyan-400">AI</span></span>
            </div>
            <p className="text-sm text-slate-500 leading-relaxed">
              The future operating system for AI-powered academic evaluation.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h4 className="text-sm font-medium text-white mb-4">{category}</h4>
              <ul className="space-y-2.5">
                {links.map((link) => (
                  <li key={link}>
                    <Link
                      href="#"
                      className="text-sm text-slate-500 hover:text-slate-300 transition-colors duration-200"
                    >
                      {link}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-16 pt-8 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-slate-600">
            © {new Date().getFullYear()} ScorePilot AI. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="#" className="text-xs text-slate-600 hover:text-slate-400 transition-colors">Privacy</Link>
            <Link href="#" className="text-xs text-slate-600 hover:text-slate-400 transition-colors">Terms</Link>
            <Link href="#" className="text-xs text-slate-600 hover:text-slate-400 transition-colors">Security</Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
