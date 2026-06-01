'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Check, HelpCircle, Sparkles, Loader2, CreditCard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HeroHeader } from '@/components/ui/hero-section-2'
import { Footer } from '@/components/ui/footer'
import { MeshGradient } from '@/components/ui/mesh-gradient'

interface Plan {
  name: string
  price_inr: number
  papers_limit: number
  features: string[]
  razorpay_plan_id: string | null
}

const FAQ_ITEMS = [
  {
    q: 'Can I cancel anytime?',
    a: 'Yes, absolutely. You can cancel your subscription at any time directly from your dashboard settings. You will retain premium access until the end of your billing cycle.'
  },
  {
    q: 'What counts as one paper?',
    a: 'One student submission (single file or multiple pages) that you scan or upload to be graded by ScorePilot AI counts as one paper.'
  },
  {
    q: 'Do unused papers roll over to the next month?',
    a: 'No, unused paper limits reset at the start of each monthly billing cycle. This ensures optimal grading availability for all educators.'
  },
  {
    q: 'Is there a free trial?',
    a: 'Yes! We offer a Free Plan with 5 papers free forever. No credit card or payment setup is required to get started.'
  }
]

export default function PricingPage() {
  const router = useRouter()
  const [plans, setPlans] = useState<Record<string, Plan> | null>(null)
  const [isAnnual, setIsAnnual] = useState(false)
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  useEffect(() => {
    // Check if user is logged in
    const token = localStorage.getItem('sp_token')
    setIsLoggedIn(!!token)

    // Fetch plans from backend
    const fetchPlans = async () => {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${API_BASE}/api/v1/subscription/plans`)
        if (!res.ok) throw new Error('Failed to load plans.')
        const data = await res.json()
        setPlans(data)
      } catch (err: any) {
        console.error('Error fetching plans:', err)
        // Fallback pricing if server is not fully reachable yet
        setPlans({
          free: {
            name: 'Free',
            price_inr: 0,
            papers_limit: 5,
            features: ['5 papers per month', 'AI scoring (MCQ + Short answer)', 'Basic analytics', 'Email support'],
            razorpay_plan_id: null
          },
          starter: {
            name: 'Starter',
            price_inr: 999,
            papers_limit: 200,
            features: ['200 papers per month', 'AI scoring (all types)', 'Full analytics dashboard', 'Export CSV + PDF', 'Priority support', 'Multi-language OCR'],
            razorpay_plan_id: 'plan_starter'
          },
          pro: {
            name: 'Pro',
            price_inr: 2499,
            papers_limit: 999999,
            features: ['Unlimited papers', 'Everything in Starter', 'Bulk upload (50 papers at once)', 'Student performance tracking', 'Custom branding', 'Dedicated support', 'API access'],
            razorpay_plan_id: 'plan_pro'
          }
        })
      }
    }
    fetchPlans()
  }, [])

  // Dynamic script injection for Razorpay Checkout
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
    if (!isLoggedIn) {
      router.push('/login?redirect=/pricing')
      return
    }

    setLoadingPlan(planKey)
    setError('')

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

      if (orderData.error === 'payments_not_configured') {
        throw new Error('Online payments are currently not configured. Please contact the administrator.')
      }

      if (!orderRes.ok || !orderData.subscription_id) {
        throw new Error(orderData.detail || 'Failed to create subscription checkout.')
      }

      // 2. Open Razorpay Checkout overlay
      const options = {
        key: orderData.razorpay_key,
        subscription_id: orderData.subscription_id,
        name: 'ScorePilot AI',
        description: `${plans?.[planKey]?.name} Subscription Plan`,
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
              alert(`Success! You have successfully upgraded to the ${plans?.[planKey]?.name} plan! 🎉`)
              router.push('/dashboard')
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

  const getPriceDisplay = (basePrice: number) => {
    if (basePrice === 0) return '₹0'
    const finalPrice = isAnnual ? Math.round(basePrice * 0.8) : basePrice
    return `₹${finalPrice.toLocaleString()}`
  }

  return (
    <div className="min-h-screen bg-background relative flex flex-col justify-between overflow-x-hidden">
      <HeroHeader />
      <MeshGradient className="-z-10" />

      {/* Main pricing grid */}
      <main className="flex-grow pt-32 pb-20 px-6 max-w-6xl mx-auto w-full space-y-20">
        
        {/* Title / Description */}
        <div className="text-center space-y-4 max-w-2xl mx-auto">
          <span className="inline-flex items-center gap-1.5 bg-cyan-500/10 text-cyan-400 text-xs px-3 py-1 rounded-full font-semibold border border-cyan-500/20">
            <Sparkles className="h-3 w-3" /> Monetization & Pricing
          </span>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
            Simple, Transparent <span className="text-gradient-cyan">Pricing</span>
          </h1>
          <p className="text-slate-400 text-base leading-relaxed">
            Grade exams with high precision and automation. Start free and scale up as your classroom grows.
          </p>

          {/* Toggle */}
          <div className="pt-4 flex items-center justify-center gap-3">
            <span className={`text-xs font-medium transition-colors ${!isAnnual ? 'text-white' : 'text-slate-500'}`}>Monthly Billing</span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className="relative h-6 w-11 rounded-full bg-white/[0.08] border border-white/[0.12] transition-colors focus:outline-none"
            >
              <div
                className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-cyan-400 transition-transform ${
                  isAnnual ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
            <span className={`text-xs font-medium transition-colors flex items-center gap-1.5 ${isAnnual ? 'text-white' : 'text-slate-500'}`}>
              Annual Billing <span className="bg-emerald-500/10 text-emerald-400 text-[10px] px-2 py-0.5 rounded-full font-bold border border-emerald-500/20">Save 20%</span>
            </span>
          </div>
        </div>

        {error && (
          <div className="max-w-md mx-auto flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-2xl px-4 py-3.5 text-xs text-red-400 text-center justify-center">
            <span>{error}</span>
          </div>
        )}

        {/* Pricing Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
          {plans ? (
            Object.entries(plans).map(([key, plan]) => {
              const isFree = key === 'free'
              const isPro = key === 'pro'
              const isStarter = key === 'starter'

              return (
                <div
                  key={key}
                  className={`glass-card rounded-3xl p-8 flex flex-col justify-between transition-all duration-300 relative ${
                    isStarter
                      ? 'border border-cyan-500/40 shadow-[0_0_30px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/20'
                      : 'border border-white/[0.06] hover:border-white/[0.12]'
                  }`}
                >
                  {isStarter && (
                    <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-gradient-to-r from-cyan-500 to-blue-500 text-black text-[10px] font-extrabold px-3.5 py-1 rounded-full uppercase tracking-wider shadow-lg">
                      Most Popular
                    </span>
                  )}

                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-bold text-white tracking-tight">{plan.name}</h3>
                      <p className="text-xs text-slate-500 mt-1">
                        {isFree ? 'For individual educators' : isStarter ? 'For active teachers' : 'For schools & departments'}
                      </p>
                    </div>

                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-extrabold text-white tracking-tight">{getPriceDisplay(plan.price_inr)}</span>
                      <span className="text-xs text-slate-500 font-medium">/month</span>
                    </div>

                    {/* Features List */}
                    <ul className="space-y-3.5 pt-2 border-t border-white/[0.04]">
                      {plan.features.map((feat, idx) => (
                        <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-300">
                          <Check className="h-4 w-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                          <span>{feat}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Button Action */}
                  <div className="mt-8 pt-4">
                    {isFree ? (
                      <Button asChild className="w-full bg-white/[0.04] hover:bg-white/[0.08] text-white border border-white/[0.08] justify-center rounded-xl text-xs py-5">
                        <Link href="/signup">Start Free</Link>
                      </Button>
                    ) : isPro ? (
                      <Button asChild className="w-full bg-white/[0.04] hover:bg-white/[0.08] text-white border border-white/[0.08] justify-center rounded-xl text-xs py-5">
                        <Link href="mailto:sales@scorepilot.ai">Contact Sales</Link>
                      </Button>
                    ) : (
                      <Button
                        disabled={loadingPlan !== null}
                        onClick={() => handleCheckout(key)}
                        className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-semibold justify-center rounded-xl text-xs py-5"
                      >
                        {loadingPlan === key ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Upgrading...
                          </>
                        ) : (
                          <>
                            <CreditCard className="h-4 w-4 mr-2" /> Start Free Trial
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              )
            })
          ) : (
            <div className="col-span-3 flex justify-center py-20">
              <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
            </div>
          )}
        </div>

        {/* FAQs */}
        <div className="border-t border-white/[0.06] pt-16 space-y-12">
          <div className="text-center space-y-3 max-w-xl mx-auto">
            <h2 className="text-2xl font-bold text-white tracking-tight">Frequently Asked Questions</h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              Have questions about billing, integrations, or limits? We have answers.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {FAQ_ITEMS.map((faq, idx) => (
              <div key={idx} className="glass-card rounded-2xl p-6 border border-white/[0.04] space-y-2">
                <h4 className="text-xs font-bold text-white flex items-center gap-2">
                  <HelpCircle className="h-4 w-4 text-cyan-400" /> {faq.q}
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed pl-6">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>

      </main>

      <Footer />
    </div>
  )
}
