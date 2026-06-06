'use client'

import React, { useState } from 'react'
import { X, Check, CreditCard, Loader2, AlertCircle, Sparkles } from 'lucide-react'
import { Button } from './button'

interface PricingModalProps {
  isOpen: boolean
  onClose: () => void
  subStatus: {
    plan: string
    papers_used: number
    papers_limit: number
    can_grade: boolean
    upgrade_required: boolean
    status: string
  } | null
  onSuccess: () => void
}

const PLANS_DATA = {
  free: {
    name: 'Free',
    price_inr: 0,
    papers_limit: 5,
    features: ['5 papers per month', 'AI scoring (MCQ + Short answer)', 'Basic analytics', 'Email support']
  },
  starter: {
    name: 'Starter',
    price_inr: 999,
    papers_limit: 200,
    features: ['200 papers per month', 'AI scoring (all types)', 'Full analytics dashboard', 'Export CSV + PDF', 'Priority support', 'Multi-language OCR']
  },
  pro: {
    name: 'Pro',
    price_inr: 2499,
    papers_limit: 999999,
    features: ['Unlimited papers', 'Everything in Starter', 'Bulk upload (50 papers at once)', 'Student performance tracking', 'Custom branding', 'Dedicated support', 'API access']
  }
}

export function PricingModal({ isOpen, onClose, subStatus, onSuccess }: PricingModalProps) {
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const razorpayKeyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID
  const isKeyConfigured = !!razorpayKeyId

  if (!isOpen) return null

  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => resolve(true)
      script.onerror = () => resolve(false)
      document.body.appendChild(script)
    })
  }

  const handleCheckout = async (planKey: string) => {
    setLoadingPlan(planKey)
    setError('')
    setInfo('')

    if (!isKeyConfigured) {
      setInfo('Payments launching soon! Contact us at support@scorepilot.ai to get early access.')
      setLoadingPlan(null)
      return
    }

    try {
      const resScript = await loadRazorpayScript()
      if (!resScript) {
        throw new Error('Razorpay SDK failed to load. Please check your internet connection.')
      }

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

      // 1. Create order
      const orderRes = await fetch(`${API_BASE}/api/v1/subscription/create-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ plan: planKey })
      })

      const orderData = await orderRes.json()

      if (orderData.error === 'plans_not_configured') {
        setInfo('Payments launching soon! Contact us at support@scorepilot.ai to get early access.')
        return
      }

      if (orderData.error === 'payments_not_configured') {
        throw new Error('Online payments are currently not configured. Please contact the administrator.')
      }

      if (!orderRes.ok || !orderData.subscription_id) {
        throw new Error(orderData.detail || 'Failed to create subscription checkout.')
      }

      // 2. Open Razorpay Checkout overlay
      const options = {
        key: razorpayKeyId,
        subscription_id: orderData.subscription_id,
        name: 'ScorePilot AI',
        description: `${PLANS_DATA[planKey as keyof typeof PLANS_DATA]?.name} Subscription Plan`,
        image: 'https://scorepilot.ai/logo.png',
        handler: async function (response: any) {
          setLoadingPlan(planKey)
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
              alert(`Success! You have successfully upgraded to the ${PLANS_DATA[planKey as keyof typeof PLANS_DATA]?.name} plan! 🎉`)
              onSuccess()
              onClose()
            } else {
              throw new Error(verifyData.detail || 'Signature verification failed.')
            }
          } catch (verErr: any) {
            setError(verErr.message || 'Payment verification failed.')
          } finally {
            setLoadingPlan(null)
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
      setError(err.message || 'Checkout session failed to initialize.')
    } finally {
      setLoadingPlan(null)
    }
  }

  const userPlan = subStatus?.plan?.toLowerCase() || 'free'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-300">
      {/* Clickable Backdrop */}
      <div className="absolute inset-0 cursor-default" onClick={onClose} />

      {/* Modal Wrapper */}
      <div className="glass-card relative w-full max-w-4xl rounded-3xl p-6 md:p-8 border border-white/[0.08] shadow-[0_0_50px_rgba(0,0,0,0.8)] flex flex-col space-y-6 max-h-[90vh] overflow-y-auto z-10">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-white cursor-pointer transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="text-center space-y-2">
          <span className="inline-flex items-center gap-1.5 bg-cyan-500/10 text-cyan-400 text-xs px-3 py-1 rounded-full font-semibold border border-cyan-500/20">
            <Sparkles className="h-3 w-3" /> ScorePilot AI Premium
          </span>
          <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">Choose Your Plan</h2>
          <p className="text-slate-400 text-xs max-w-md mx-auto">
            Scale up your grading capabilities. Upgrade instantly to unlock unlimited evaluations, bulk uploads, and LMS integration.
          </p>
        </div>

        {error && (
          <div className="max-w-md mx-auto flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {info && (
          <div className="max-w-md mx-auto flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-2.5 text-xs text-amber-400">
            <Sparkles className="h-4 w-4 flex-shrink-0 text-amber-400 animate-pulse" />
            <span>{info}</span>
          </div>
        )}

        {/* Pricing Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch pt-2">
          {Object.entries(PLANS_DATA).map(([key, plan]) => {
            const isCurrent = userPlan === key
            const isFree = key === 'free'
            const isPro = key === 'pro'
            const isStarter = key === 'starter'

            return (
              <div
                key={key}
                className={`bg-white/[0.01] border rounded-2xl p-5 flex flex-col justify-between transition-all duration-300 relative ${
                  isStarter
                    ? 'border-cyan-500/40 shadow-[0_0_20px_rgba(6,182,212,0.1)]'
                    : 'border-white/[0.06] hover:border-white/[0.1]'
                }`}
              >
                {isStarter && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-cyan-500 to-blue-500 text-black text-[9px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                    Most Popular
                  </span>
                )}

                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-tight">{plan.name}</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      {isFree ? 'For individual teachers' : isStarter ? 'For active educators' : 'For schools & departments'}
                    </p>
                  </div>

                  <div className="flex items-baseline gap-0.5">
                    <span className="text-2xl font-black text-white">
                      ₹{plan.price_inr.toLocaleString()}
                    </span>
                    <span className="text-[10px] text-slate-500">/month</span>
                  </div>

                  <ul className="space-y-2 pt-2 border-t border-white/[0.04]">
                    {plan.features.map((feat, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-[11px] text-slate-300">
                        <Check className="h-3.5 w-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-6 pt-2">
                  {isCurrent ? (
                    <Button
                      disabled
                      className="w-full bg-white/[0.04] text-slate-400 border border-white/[0.08] justify-center rounded-xl text-xs py-4"
                    >
                      Current Plan
                    </Button>
                  ) : isFree ? (
                    <Button
                      disabled
                      className="w-full bg-white/[0.02] text-slate-500 border border-white/[0.04] justify-center rounded-xl text-xs py-4"
                    >
                      Included
                    </Button>
                  ) : isPro ? (
                    <Button
                      asChild
                      className="w-full bg-white/[0.04] hover:bg-white/[0.08] text-white border border-white/[0.08] justify-center rounded-xl text-xs py-4"
                    >
                      <a href="mailto:sales@scorepilot.ai">Contact Sales</a>
                    </Button>
                  ) : (
                    <Button
                      disabled={loadingPlan !== null}
                      onClick={() => handleCheckout(key)}
                      className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-semibold justify-center rounded-xl text-xs py-4"
                    >
                      {loadingPlan === key ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Upgrading...
                        </>
                      ) : (
                        <>
                          <CreditCard className="h-3.5 w-3.5 mr-1.5" /> Upgrade Plan
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
