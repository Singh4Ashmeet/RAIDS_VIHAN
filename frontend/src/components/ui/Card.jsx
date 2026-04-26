import { clsx } from 'clsx'

export default function Card({
  children, className, glow = false, onClick
}) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'min-w-0 bg-card border border-border rounded-xl p-6 shadow-lg shadow-black/10',
        glow && 'ring-1 ring-brand-500/30 shadow-lg shadow-brand-500/10',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </div>
  )
}
