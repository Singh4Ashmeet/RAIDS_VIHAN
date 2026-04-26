import { clsx } from 'clsx'

export function SkeletonLine({ className }) {
  return (
    <div className={clsx(
      'h-4 bg-slate-700/60 rounded animate-pulse', className
    )}/>
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-card border border-border rounded-xl p-6
      space-y-3">
      <SkeletonLine className="w-1/3"/>
      <SkeletonLine className="w-full"/>
      <SkeletonLine className="w-2/3"/>
    </div>
  )
}

export default function Skeleton({ count = 3, className }) {
  if (className) {
    return (
      <div className={clsx(
        'animate-pulse bg-slate-700/60',
        className
      )}/>
    )
  }

  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i}/>
      ))}
    </div>
  )
}
