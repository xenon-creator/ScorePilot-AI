'use client'

import React from 'react'
import Link from 'next/link'
import { Menu, X, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AnimatedGroup } from '@/components/ui/animated-group'
import { MeshGradient } from '@/components/ui/mesh-gradient'
import { cn } from '@/lib/utils'
import { useScroll } from 'motion/react'

const transitionVariants = {
    item: {
        hidden: {
            opacity: 0,
            filter: 'blur(12px)',
            y: 12,
        },
        visible: {
            opacity: 1,
            filter: 'blur(0px)',
            y: 0,
            transition: {
                type: 'spring' as const,
                bounce: 0.3,
                duration: 1.5,
            },
        },
    },
}

export function HeroSection() {
    const [showScrollArrow, setShowScrollArrow] = React.useState(true)

    React.useEffect(() => {
        const handleScroll = () => {
            if (window.scrollY > 100) {
                setShowScrollArrow(false)
            } else {
                setShowScrollArrow(true)
            }
        }
        window.addEventListener('scroll', handleScroll, { passive: true })
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    return (
        <>
            <HeroHeader />
            <main className="overflow-hidden">
                <section>
                    <div className="relative pt-32">
                        <MeshGradient className="-z-10" />
                        <div className="mx-auto max-w-6xl px-6">
                            <div className="sm:mx-auto lg:mr-auto">
                                <AnimatedGroup
                                    variants={{
                                        container: {
                                            visible: {
                                                transition: {
                                                    staggerChildren: 0.05,
                                                    delayChildren: 0.75,
                                                },
                                            },
                                        },
                                        ...transitionVariants,
                                    }}
                                >
                                    <h1
                                        className="mt-8 max-w-3xl text-balance text-[36px] sm:text-5xl font-semibold tracking-tight md:text-6xl lg:text-7xl lg:mt-16">
                                        Transforming academic evaluation{' '}
                                        <span className="text-gradient-cyan">through intelligent AI scoring.</span>
                                    </h1>
                                    <p
                                        className="mt-8 max-w-2xl text-pretty text-lg text-slate-400 md:text-xl">
                                        ScorePilot AI automates exam evaluation with OCR extraction, semantic analysis, and explainable scoring — giving educators superhuman grading precision.
                                    </p>
                                    <div className="mt-12 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                                        <div
                                            key={1}
                                            className="bg-cyan-400/10 rounded-[14px] border border-cyan-400/20 p-0.5 w-full sm:w-auto">
                                            <Button
                                                asChild
                                                size="lg"
                                                className="rounded-xl px-6 text-base bg-cyan-500 hover:bg-cyan-400 text-black font-medium border-0 w-full justify-center">
                                                <Link href="/signup" className="w-full text-center">
                                                    <span className="text-nowrap">Get Early Access</span>
                                                </Link>
                                            </Button>
                                        </div>
                                        <Button
                                            key={2}
                                            asChild
                                            size="lg"
                                            variant="ghost"
                                            className="h-[42px] rounded-xl px-5 text-base text-slate-300 hover:text-white w-full sm:w-auto justify-center">
                                            <Link href="#workflow" className="flex items-center justify-center">
                                                <Play className="mr-2 h-4 w-4" />
                                                <span className="text-nowrap">Watch Demo</span>
                                            </Link>
                                        </Button>
                                    </div>
                                    <div className={cn("scroll-indicator", !showScrollArrow && "hidden")}>
                                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                                            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                                        </svg>
                                    </div>
                                </AnimatedGroup>
                            </div>
                        </div>
                        <AnimatedGroup
                            variants={{
                                container: {
                                    visible: {
                                        transition: {
                                            staggerChildren: 0.05,
                                            delayChildren: 0.75,
                                        },
                                    },
                                },
                                ...transitionVariants,
                            }}>
                            <div className="relative mt-10 px-2">
                                <div
                                    aria-hidden
                                    className="bg-gradient-to-b from-transparent via-transparent to-black absolute inset-0 z-10"
                                />
                                <div className="glass-card relative mx-auto max-w-5xl overflow-hidden rounded-2xl p-6 md:p-8">
                                    {/* Mock AI Scoring Dashboard */}
                                    <div className="flex overflow-x-auto md:grid md:grid-cols-3 gap-4 no-scrollbar scroll-smooth pb-4 md:pb-0">
                                        {/* Score Card */}
                                        <div className="glass-card rounded-xl p-5 min-w-[280px] sm:min-w-[320px] md:min-w-0 flex-shrink-0 md:flex-shrink w-[280px] sm:w-[320px] md:w-full">
                                            <div className="flex items-center justify-between mb-4">
                                                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">AI Score</span>
                                                <span className="text-xs text-emerald-400 font-medium">● Live</span>
                                            </div>
                                            <div className="text-4xl font-bold text-white">87<span className="text-lg text-slate-500">/100</span></div>
                                            <div className="mt-3 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                                <div className="h-full w-[87%] rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" />
                                            </div>
                                            <p className="mt-3 text-xs text-slate-500">Confidence: 94.2%</p>
                                        </div>

                                        {/* OCR Extraction */}
                                        <div className="glass-card rounded-xl p-5 min-w-[280px] sm:min-w-[320px] md:min-w-0 flex-shrink-0 md:flex-shrink w-[280px] sm:w-[320px] md:w-full">
                                            <div className="flex items-center justify-between mb-4">
                                                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">OCR Extract</span>
                                                <span className="text-xs text-cyan-400 font-medium">Processing</span>
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-2 rounded bg-white/[0.06] w-full"><div className="h-full rounded bg-cyan-500/30 w-[92%]" /></div>
                                                <div className="h-2 rounded bg-white/[0.06] w-4/5"><div className="h-full rounded bg-cyan-500/30 w-[88%]" /></div>
                                                <div className="h-2 rounded bg-white/[0.06] w-full"><div className="h-full rounded bg-cyan-500/30 w-[95%]" /></div>
                                                <div className="h-2 rounded bg-white/[0.06] w-3/4"><div className="h-full rounded bg-cyan-500/30 w-[78%]" /></div>
                                                <div className="h-2 rounded bg-white/[0.06] w-5/6"><div className="h-full rounded bg-cyan-500/30 w-[90%]" /></div>
                                            </div>
                                            <p className="mt-3 text-xs text-slate-500">5 fields extracted</p>
                                        </div>

                                        {/* Semantic Match */}
                                        <div className="glass-card rounded-xl p-5 min-w-[280px] sm:min-w-[320px] md:min-w-0 flex-shrink-0 md:flex-shrink w-[280px] sm:w-[320px] md:w-full">
                                            <div className="flex items-center justify-between mb-4">
                                                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Semantic Match</span>
                                                <span className="text-xs text-violet-400 font-medium">Analyzed</span>
                                            </div>
                                            <div className="space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs text-slate-400">Key Concept A</span>
                                                    <span className="text-xs font-medium text-emerald-400">96%</span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs text-slate-400">Key Concept B</span>
                                                    <span className="text-xs font-medium text-emerald-400">91%</span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs text-slate-400">Key Concept C</span>
                                                    <span className="text-xs font-medium text-yellow-400">73%</span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs text-slate-400">Key Concept D</span>
                                                    <span className="text-xs font-medium text-emerald-400">88%</span>
                                                </div>
                                            </div>
                                            <p className="mt-3 text-xs text-slate-500">Rubric coverage: 87%</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </AnimatedGroup>
                    </div>
                </section>

            </main>
        </>
    )
}

const menuItems = [
    { name: 'Platform', href: '#platform' },
    { name: 'How It Works', href: '#workflow' },
    { name: 'Scoring', href: '#scoring' },
    { name: 'Analytics', href: '#analytics' },
    { name: 'Pricing', href: '/pricing' },
]


export const HeroHeader = () => {
    const [menuState, setMenuState] = React.useState(false)
    const [scrolled, setScrolled] = React.useState(false)

    const { scrollYProgress } = useScroll()

    React.useEffect(() => {
        const unsubscribe = scrollYProgress.on('change', (latest) => {
            setScrolled(latest > 0.05)
        })
        return () => unsubscribe()
    }, [scrollYProgress])

    return (
        <header>
            <nav
                data-state={menuState && 'active'}
                className={cn('group fixed z-20 w-full transition-all duration-300', scrolled ? 'bg-black/60 backdrop-blur-2xl border-b border-white/[0.06]' : 'border-b border-transparent')}>
                <div className="mx-auto max-w-6xl px-6 transition-all duration-300">
                    <div className="relative flex flex-wrap items-center justify-between gap-6 py-3 lg:gap-0 lg:py-4">
                        <div className="flex w-full items-center justify-between gap-12 lg:w-auto">
                            <Link
                                href="/"
                                aria-label="home"
                                className="flex items-center space-x-2">
                                <Logo />
                            </Link>

                            <button
                                onClick={() => setMenuState(!menuState)}
                                aria-label={menuState == true ? 'Close Menu' : 'Open Menu'}
                                className="relative z-20 -m-2.5 -mr-4 block cursor-pointer p-2.5 lg:hidden">
                                <Menu className="group-data-[state=active]:rotate-180 group-data-[state=active]:scale-0 group-data-[state=active]:opacity-0 m-auto size-6 text-white duration-200" />
                                <X className="group-data-[state=active]:rotate-0 group-data-[state=active]:scale-100 group-data-[state=active]:opacity-100 absolute inset-0 m-auto size-6 text-white -rotate-180 scale-0 opacity-0 duration-200" />
                            </button>

                            <div className="hidden lg:block">
                                <ul className="flex gap-8 text-sm">
                                    {menuItems.map((item, index) => (
                                        <li key={index}>
                                            <Link
                                                href={item.href}
                                                className="text-slate-400 hover:text-white block duration-200">
                                                <span>{item.name}</span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>

                        <div className="bg-zinc-950/95 backdrop-blur-2xl group-data-[state=active]:block lg:group-data-[state=active]:flex mb-6 hidden w-full flex-wrap items-center justify-end space-y-8 rounded-3xl border border-white/[0.08] p-6 shadow-2xl shadow-black/40 md:flex-nowrap lg:m-0 lg:flex lg:w-fit lg:gap-6 lg:space-y-0 lg:border-transparent lg:bg-transparent lg:p-0 lg:shadow-none lg:backdrop-blur-none">
                            <div className="lg:hidden">
                                <ul className="space-y-6 text-base">
                                    {menuItems.map((item, index) => (
                                        <li key={index}>
                                            <Link
                                                href={item.href}
                                                className="text-slate-400 hover:text-white block duration-200">
                                                <span>{item.name}</span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="flex w-full flex-col space-y-3 sm:flex-row sm:gap-3 sm:space-y-0 md:w-fit">
                                <Button
                                    asChild
                                    variant="outline"
                                    size="sm"
                                    className="border-white/[0.1] text-slate-300 hover:text-white hover:border-white/[0.2]">
                                    <Link href="/login">
                                        <span>Login</span>
                                    </Link>
                                </Button>
                                <Button
                                    asChild
                                    size="sm"
                                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-medium">
                                    <Link href="/signup">
                                        <span>Sign Up</span>
                                    </Link>
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </nav>
        </header>
    )
}

const Logo = ({ className }: { className?: string }) => {
    return (
        <div className={cn('flex items-center gap-2', className)}>
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
    )
}
