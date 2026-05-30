'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { apiLogin, apiSignup, apiGetMe, type User } from '@/lib/api'

interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (username: string, email: string, password: string, role?: string, studentId?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Hydrate from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('sp_token')
    if (savedToken) {
      setToken(savedToken)
      apiGetMe()
        .then((u) => setUser(u))
        .catch(() => {
          // Token expired or invalid
          localStorage.removeItem('sp_token')
          setToken(null)
        })
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password)
    localStorage.setItem('sp_token', res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const signup = useCallback(async (username: string, email: string, password: string, role: string = 'Teacher', studentId?: string) => {
    const res = await apiSignup(username, email, password, role, studentId)
    localStorage.setItem('sp_token', res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('sp_token')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
