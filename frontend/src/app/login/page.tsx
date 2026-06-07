'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { MeshGradient } from '@/components/ui/mesh-gradient'
import { AlertCircle, Loader2, Mail, Lock, Cpu, Eye, EyeOff } from 'lucide-react'

const quickLogins = [
  { label: 'Admin', email: 'admin@aegis.edu', password: 'admin123', role: 'Admin' },
  { label: 'Teacher', email: 'teacher@aegis.edu', password: 'teacher123', role: 'Teacher' },
  { label: 'Reviewer', email: 'reviewer@aegis.edu', password: 'reviewer123', role: 'Reviewer' },
  { label: 'Student', email: 'student@aegis.edu', password: 'student123', role: 'Student' },
]

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      router.push('/dashboard')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleQuickLogin(ql: typeof quickLogins[0]) {
    setError('')
    setLoading(true)
    try {
      await login(ql.email, ql.password)
      router.push('/dashboard')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center px-6 py-12">
      <MeshGradient className="-z-10" />

      <div className="w-full max-w-md space-y-8">
        {/* Logo */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-2 mb-8">
            <div className="relative flex h-8 w-8 items-center justify-center">
              <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 opacity-80" />
              <Cpu className="relative z-10 h-4 w-4 text-black" />
            </div>
            <span className="text-xl font-semibold tracking-tight text-white">
              ScorePilot<span className="text-cyan-400">AI</span>
            </span>
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight text-white">Welcome back</h1>
          <p className="mt-2 text-sm text-slate-400">Sign in to your evaluation dashboard</p>
        </div>

        {/* Quick Login Personas */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Quick Login</p>
          <div className="grid grid-cols-4 gap-2">
            {quickLogins.map((ql) => (
              <button
                key={ql.label}
                type="button"
                disabled={loading}
                onClick={() => handleQuickLogin(ql)}
                className="glass-card glass-card-hover rounded-xl py-3 px-2 text-center cursor-pointer disabled:opacity-50"
              >
                <div className="text-xs font-semibold text-white">{ql.label}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">{ql.role}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex-1 h-px bg-white/[0.06]" />
          <span className="text-xs text-slate-600">or sign in with email</span>
          <div className="flex-1 h-px bg-white/[0.06]" />
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="email" className="text-xs font-medium text-slate-400">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-600" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@institution.edu"
                required
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-10 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-medium text-slate-400">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-600" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-10 pr-12 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors cursor-pointer"
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full h-11 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-medium text-sm"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Sign In'}
          </Button>
        </form>

        <p className="text-center text-sm text-slate-500">
          Don&apos;t have an account?{' '}
          <Link href="/signup" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}
