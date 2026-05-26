'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { MeshGradient } from '@/components/ui/mesh-gradient'
import { AlertCircle, Loader2, Mail, Lock, User, Cpu } from 'lucide-react'

const roles = ['Teacher', 'Reviewer', 'Admin']

export default function SignupPage() {
  const router = useRouter()
  const { signup } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('Teacher')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await signup(username, email, password, role)
      router.push('/dashboard')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signup failed')
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
          <h1 className="text-3xl font-semibold tracking-tight text-white">Create your account</h1>
          <p className="mt-2 text-sm text-slate-400">Start grading smarter with AI-powered evaluation</p>
        </div>

        {/* Signup Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="username" className="text-xs font-medium text-slate-400">Username</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-600" />
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="prof_jane"
                required
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-10 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
              />
            </div>
          </div>

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
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                className="w-full h-11 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-10 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Role</label>
            <div className="grid grid-cols-3 gap-2">
              {roles.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRole(r)}
                  className={`h-10 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                    role === r
                      ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-400'
                      : 'bg-white/[0.03] border border-white/[0.06] text-slate-500 hover:text-slate-300 hover:border-white/[0.1]'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full h-11 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-medium text-sm mt-2"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create Account'}
          </Button>
        </form>

        <p className="text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link href="/login" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
