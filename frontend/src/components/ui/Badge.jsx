import { clsx } from 'clsx'

const variants = {
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  error:   'bg-red-500/20 text-red-400 border-red-500/30',
  info:    'bg-blue-500/20 text-blue-400 border-blue-500/30',
  neutral: 'bg-slate-700/60 text-slate-300 border-border',
}

export default function Badge({ variant = 'neutral', children }) {
  return (
    <span className={clsx(
      'inline-flex items-center text-xs font-medium',
      'px-2.5 py-0.5 rounded-full border',
      variants[variant]
    )}>
      {children}
    </span>
  )
}
