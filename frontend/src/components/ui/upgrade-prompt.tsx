'use client'

import React, { useState } from 'react'
import { Rocket, X, Loader2, Sparkles, AlertCircle } from 'lucide-react'
import { Button } from './button'

interface UpgradePromptProps {
  papersUsed: number
  papersLimit: number
  onSuccess: () => void
  onClose: () => void
}

export function UpgradePrompt({ papersUsed, papersLimit, onSuccess, onClose }: UpgradePromptProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => resolve(true)
      script.onerror = () => resolve(false)
      document.body.appendChild(script)
    })
  }

  const handleUpgrade = async () => {
    setLoading(true)
    setError('')
    try {
      const scriptLoaded = await loadRazorpayScript()
      if (!scriptLoaded) {
        throw new Error('Razorpay SDK failed to load. Please verify your internet connection.')
      }

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = ''

      // 1. Create order
      const orderRes = await fetch(`${API_BASE}/api/v1/subscription/create-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ plan: 'starter' })
      })

      const orderData = await orderRes.json()

      if (orderData.error === 'payments_not_configured') {
        throw new Error('Online payments are currently not configured. Please contact support.')
      }

      if (!orderRes.ok || !orderData.subscription_id) {
        throw new Error(orderData.detail || 'Failed to create subscription order.')
      }

      // 2. Open Razorpay Checkout overlay
      const options = {
        key: orderData.razorpay_key,
        subscription_id: orderData.subscription_id,
        name: 'ScorePilot AI',
        description: 'Starter Subscription Plan Upgrade',
        image: 'https://scorepilot.ai/logo.png',
        handler: async function (response: any) {
          setLoading(true)
          try {
            // 3. Verify payment signature on backend
            const verifyRes = await fetch(`${API_BASE}/api/v1/subscription/verify-payment`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
              },
              body: JSON.stringify({
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_subscription_id: response.razorpay_subscription_id,
                razorpay_signature: response.razorpay_signature
              })
            })

            const verifyData = await verifyRes.json()
            if (verifyRes.ok && verifyData.success) {
              alert("You're now on Starter plan! 🎉")
              onSuccess()
            } else {
              throw new Error(verifyData.detail || 'Payment verification failed.')
            }
          } catch (verErr: any) {
            setError(verErr.message || 'Payment verification failed.')
          } finally {
            setLoading(false)
          }
        },
        prefill: {
          name: '',
          email: ''
        },
        theme: {
          color: '#06b6d4'
        }
      }

      const rzp = new (window as any).Razorpay(options)
      rzp.open()
    } catch (err: any) {
      setError(err.message || 'Upgrade session failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="glass-card w-full max-w-md rounded-3xl p-6 border border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.15)] relative space-y-6">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-white cursor-pointer transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Content */}
        <div className="text-center space-y-4">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Rocket className="h-6 w-6" />
          </div>
          
          <div className="space-y-1">
            <h4 className="text-lg font-bold text-white tracking-tight flex items-center justify-center gap-1.5">
              Upgrade to Starter <Sparkles className="h-4 w-4 text-cyan-400" />
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed max-w-xs mx-auto">
              You&apos;ve used <span className="text-white font-semibold">{papersUsed}/{papersLimit}</span> free papers. Upgrade to grade more exams.
            </p>
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-[10px] text-red-400">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Plan Breakdown */}
        <div className="bg-white/[0.02] border border-white/[0.04] p-4 rounded-2xl space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Upgrade to Starter Plan</span>
            <span className="text-white font-bold">₹999/month</span>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed">
            Includes 200 paper evaluations per month, AI scoring across MCQ + Short + Essay formats, Priority Support, CSV/PDF exporting, and Multi-language OCR.
          </p>
        </div>

        {/* Actions */}
        <div className="space-y-2.5">
          <Button
            disabled={loading}
            onClick={handleUpgrade}
            className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-semibold py-4 text-xs rounded-xl flex justify-center items-center cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Upgrading...
              </>
            ) : (
              'Upgrade Now'
            )}
          </Button>

          <div className="text-center">
            <button
              onClick={onClose}
              className="text-[10px] text-slate-500 hover:text-slate-300 hover:underline bg-transparent border-0 cursor-pointer"
            >
              Maybe Later
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
