export function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-4 p-6">
      <div className="h-8 bg-white/5 rounded w-48" />
      <div className="h-4 bg-white/5 rounded w-32" />
      <div className="grid grid-cols-3 gap-4 mt-8">
        {[1,2,3].map(i => (
          <div key={i} className="h-32 bg-white/5 rounded-xl" />
        ))}
      </div>
      <div className="space-y-3 mt-6">
        {[1,2,3].map(i => (
          <div key={i} className="h-16 bg-white/5 rounded-lg" />
        ))}
      </div>
    </div>
  )
}
