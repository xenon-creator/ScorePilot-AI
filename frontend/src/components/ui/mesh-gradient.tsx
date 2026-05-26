'use client'

import { cn } from '@/lib/utils'

export function MeshGradient({ className }: { className?: string }) {
  return (
    <div className={cn('absolute inset-0 overflow-hidden', className)} aria-hidden>
      {/* Deep base */}
      <div className="absolute inset-0 bg-black" />

      {/* Cyan orb - top right */}
      <div
        className="absolute -top-1/4 -right-1/4 w-[600px] h-[600px] rounded-full opacity-20"
        style={{
          background: 'radial-gradient(circle, rgba(6, 182, 212, 0.4) 0%, transparent 70%)',
          animation: 'mesh-drift 15s ease-in-out infinite',
        }}
      />

      {/* Violet orb - bottom left */}
      <div
        className="absolute -bottom-1/4 -left-1/4 w-[500px] h-[500px] rounded-full opacity-15"
        style={{
          background: 'radial-gradient(circle, rgba(139, 92, 246, 0.4) 0%, transparent 70%)',
          animation: 'mesh-drift 20s ease-in-out infinite reverse',
        }}
      />

      {/* Blue orb - center */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-10"
        style={{
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, transparent 70%)',
          animation: 'mesh-drift 25s ease-in-out infinite',
          animationDelay: '5s',
        }}
      />

      {/* Emerald accent - subtle */}
      <div
        className="absolute top-3/4 right-1/3 w-[300px] h-[300px] rounded-full opacity-10"
        style={{
          background: 'radial-gradient(circle, rgba(16, 185, 129, 0.3) 0%, transparent 70%)',
          animation: 'mesh-drift 18s ease-in-out infinite',
          animationDelay: '10s',
        }}
      />

      {/* Noise overlay for texture */}
      <div
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
        }}
      />

      {/* Top-down gradient fade */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/50 via-transparent to-black" />
    </div>
  )
}
