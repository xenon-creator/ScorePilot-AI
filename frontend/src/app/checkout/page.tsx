'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { CreditCard, ArrowLeft, Check, Sparkles, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HeroHeader } from '@/components/ui/hero-section-2'
import { Footer } from '@/components/ui/footer'
import { MeshGradient } from '@/components/ui/mesh-gradient'

interface Package {
  id: string
  name: string
  credits: number
  price_inr: number
  description: string
}

const CREDIT_PACKAGES: Package[] = [
  {
    id: 'pkg_basic',
    name: 'Basic Bundle',
    credits: 100,
    price_inr: 199,
    description: 'Perfect for grading short tests and quizzes.'
  },
  {
    id: 'pkg_standard',
    name: 'Standard Bundle',
    credits: 500,
    price_inr: 799,
    description: 'Great for midterm or final exams across classes.'
  },
  {
    id: 'pkg_premium',
    name: 'Premium Bundle',
    credits: 1200,
    price_inr: 1499,
    description: 'Best value for active departments and large courses.'
  }
]

export default function CheckoutPage() {
  const router = useRouter()
  const [selectedPkg, setSelectedPkg] = useState<string>('pkg_standard')
  const [customAmount, setCustomAmount] = useState<string>('')
  const [isCustom, setIsCustom] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<boolean>(false)
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false)
  const [paymentDetails, setPaymentDetails] = useState<any>(null)

  useEffect(() => {
    // Check user auth
    const token = localStorage.getItem('sp_token')
    if (!token) {
      router.push('/login?redirect=/checkout')
    } else {
      setIsLoggedIn(true)
    }
  }, [router])

  const loadRazorpayScript = (): Promise<boolean> => {
    return new Promise((resolve) => {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => resolve(true)
      script.onerror = () => resolve(false)
      document.body.appendChild(script)
    })
  }

  const handlePayment = async () => {
    setError('')
    setSuccess(false)
    setLoading(true)

    try {
      const scriptLoaded = await loadRazorpayScript()
      if (!scriptLoaded) {
        throw new Error('Razorpay SDK failed to load. Please verify your connection.')
      }

      // Determine amount in paise
      let amountInPaise = 0
      if (isCustom) {
        const val = parseFloat(customAmount)
        if (isNaN(val) || val <= 0) {
          throw new Error('Please enter a valid amount.')
        }
        amountInPaise = Math.round(val * 100)
      } else {
        const pkg = CREDIT_PACKAGES.find(p => p.id === selectedPkg)
        if (!pkg) throw new Error('Invalid package selected.')
        amountInPaise = pkg.price_inr * 100
      }

      if (amountInPaise < 100) {
        throw new Error('Amount must be at least ₹1.00 (100 paise).')
      }

      const token = localStorage.getItem('sp_token') || ''
      const API_BASE = ''

      // 1. Create Order on Backend
      const orderRes = await fetch(`${API_BASE}/api/create-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          amount: amountInPaise,
          currency: 'INR',
          receipt: `rcpt_${Date.now()}`
        })
      })

      const orderData = await orderRes.json()

      if (!orderRes.ok) {
        if (orderRes.status === 401) {
          throw new Error('Authentication expired. Please log in again.')
        }
        throw new Error(orderData.detail || 'Failed to create order on the server.')
      }

      // 2. Open Razorpay Checkout Modal
      const razorpayKey = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID
      if (!razorpayKey) {
        throw new Error('Razorpay client Key ID is not configured on the frontend environment.')
      }

      const options = {
        key: razorpayKey,
        amount: orderData.amount,
        currency: orderData.currency,
        name: 'ScorePilot AI',
        description: isCustom 
          ? 'Custom Credits Purchase' 
          : `${CREDIT_PACKAGES.find(p => p.id === selectedPkg)?.name} Credits`,
        image: 'https://scorepilot.ai/logo.png',
        order_id: orderData.order_id,
        handler: async function (response: any) {
          setLoading(true)
          try {
            // 3. Verify Payment on Backend
            const verifyRes = await fetch(`${API_BASE}/api/verify-payment`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
              },
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature
              })
            })

            const verifyData = await verifyRes.json()

            if (verifyRes.ok && verifyData.success) {
              setSuccess(true)
              setPaymentDetails({
                order_id: response.razorpay_order_id,
                payment_id: response.razorpay_payment_id,
                amount: (orderData.amount / 100).toFixed(2)
              })
            } else {
              throw new Error(verifyData.detail || 'Payment verification failed.')
            }
          } catch (verErr: any) {
            setError(verErr.message || 'Payment verification failed.')
          } finally {
            setLoading(false)
          }
        },
        modal: {
          ondismiss: function () {
            setError('Payment cancelled by user.')
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
      rzp.on('payment.failed', function (resp: any) {
        setError(resp.error.description || 'Payment failed.')
        setLoading(false)
      })
      rzp.open()
    } catch (err: any) {
      setError(err.message || 'Checkout failed to initialize.')
      setLoading(false)
    }
  }

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background relative flex flex-col justify-between overflow-x-hidden">
      <HeroHeader />
      <MeshGradient className="-z-10" />

      <main className="flex-grow pt-32 pb-20 px-6 max-w-4xl mx-auto w-full space-y-10">
        {/* Navigation back */}
        <div>
          <Link href="/pricing" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Pricing Plans
          </Link>
        </div>

        {/* Title / Description */}
        <div className="space-y-4">
          <span className="inline-flex items-center gap-1.5 bg-cyan-500/10 text-cyan-400 text-xs px-3 py-1 rounded-full font-semibold border border-cyan-500/20">
            <Sparkles className="h-3 w-3" /> One-Time Purchase
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Purchase <span className="text-gradient-cyan">Credits</span>
          </h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Need extra grading credits without a recurring subscription? Purchase credits on-demand.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-2xl px-5 py-4 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && paymentDetails && (
          <div className="glass-card rounded-3xl p-8 border border-emerald-500/30 shadow-[0_0_35px_rgba(16,185,129,0.1)] space-y-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-emerald-500/10 border border-emerald-500/20 rounded-full flex items-center justify-center text-emerald-400">
                <Check className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Payment Successful! 🎉</h3>
                <p className="text-xs text-slate-400">Your order has been verified and processed successfully.</p>
              </div>
            </div>

            <div className="border-t border-white/[0.04] pt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-slate-500 block mb-1">Order ID</span>
                <span className="text-slate-300 font-mono select-all">{paymentDetails.order_id}</span>
              </div>
              <div>
                <span className="text-slate-500 block mb-1">Payment ID</span>
                <span className="text-slate-300 font-mono select-all">{paymentDetails.payment_id}</span>
              </div>
              <div>
                <span className="text-slate-500 block mb-1">Amount Paid</span>
                <span className="text-white font-bold">₹{paymentDetails.amount}</span>
              </div>
            </div>

            <div className="pt-2 flex gap-3">
              <Button asChild className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold rounded-xl text-xs px-6 py-4">
                <Link href="/dashboard">Go to Dashboard</Link>
              </Button>
              <Button variant="outline" className="border-white/[0.08] hover:bg-white/[0.04] text-slate-300 rounded-xl text-xs px-6 py-4" onClick={() => setSuccess(false)}>
                Buy More Credits
              </Button>
            </div>
          </div>
        )}

        {!success && (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
            {/* Packages Selector */}
            <div className="lg:col-span-3 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider text-slate-400">Choose Package</h3>
              
              <div className="space-y-3">
                {CREDIT_PACKAGES.map((pkg) => (
                  <div
                    key={pkg.id}
                    onClick={() => {
                      setIsCustom(false)
                      setSelectedPkg(pkg.id)
                    }}
                    className={`glass-card p-5 rounded-2xl border cursor-pointer transition-all flex justify-between items-center ${
                      !isCustom && selectedPkg === pkg.id
                        ? 'border-cyan-500/50 bg-cyan-500/[0.02] shadow-[0_0_20px_rgba(6,182,212,0.08)]'
                        : 'border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.01]'
                    }`}
                  >
                    <div className="space-y-1 pr-4">
                      <h4 className="text-sm font-bold text-white">{pkg.name}</h4>
                      <p className="text-xs text-slate-400 leading-relaxed">{pkg.description}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-lg font-extrabold text-white block">₹{pkg.price_inr}</span>
                      <span className="text-[10px] text-cyan-400 font-semibold">{pkg.credits} credits</span>
                    </div>
                  </div>
                ))}

                {/* Custom Option */}
                <div
                  onClick={() => setIsCustom(true)}
                  className={`glass-card p-5 rounded-2xl border cursor-pointer transition-all ${
                    isCustom
                      ? 'border-cyan-500/50 bg-cyan-500/[0.02] shadow-[0_0_20px_rgba(6,182,212,0.08)]'
                      : 'border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.01]'
                  }`}
                >
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="text-sm font-bold text-white">Custom Amount</h4>
                    <span className="text-[10px] text-slate-500">Min ₹1.00</span>
                  </div>

                  {isCustom && (
                    <div className="flex gap-2">
                      <div className="relative flex-grow">
                        <span className="absolute left-4 top-2.5 text-sm font-semibold text-slate-500">₹</span>
                        <input
                          type="number"
                          min="1"
                          step="any"
                          placeholder="Enter amount"
                          value={customAmount}
                          onChange={(e) => setCustomAmount(e.target.value)}
                          className="w-full h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] pl-8 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Order Summary & Button */}
            <div className="lg:col-span-2">
              <div className="glass-card rounded-2xl p-6 border border-white/[0.06] space-y-6">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider text-slate-400">Order Summary</h3>
                
                <div className="space-y-4 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Item</span>
                    <span className="text-slate-300 font-medium">
                      {isCustom 
                        ? 'Custom Credits Purchase' 
                        : `${CREDIT_PACKAGES.find(p => p.id === selectedPkg)?.name} (${CREDIT_PACKAGES.find(p => p.id === selectedPkg)?.credits} Credits)`
                      }
                    </span>
                  </div>
                  
                  <div className="flex justify-between">
                    <span className="text-slate-500">Currency</span>
                    <span className="text-slate-300 uppercase">INR</span>
                  </div>

                  <div className="border-t border-white/[0.04] pt-4 flex justify-between items-baseline">
                    <span className="text-sm text-slate-400 font-semibold">Total Amount</span>
                    <span className="text-2xl font-black text-white">
                      ₹{isCustom 
                        ? (parseFloat(customAmount) || 0).toLocaleString() 
                        : (CREDIT_PACKAGES.find(p => p.id === selectedPkg)?.price_inr || 0).toLocaleString()
                      }
                    </span>
                  </div>
                </div>

                <Button
                  disabled={loading}
                  onClick={handlePayment}
                  className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold py-5 rounded-xl text-xs flex justify-center items-center cursor-pointer shadow-lg shadow-cyan-500/10"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Processing...
                    </>
                  ) : (
                    <>
                      <CreditCard className="h-4 w-4 mr-2" /> Pay with Razorpay
                    </>
                  )}
                </Button>

                <p className="text-[10px] text-slate-500 text-center leading-relaxed">
                  Payments are secure and encrypted. By completing purchase, you agree to our Terms of Service.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  )
}
