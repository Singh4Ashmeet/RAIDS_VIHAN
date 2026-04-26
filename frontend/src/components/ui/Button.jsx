import { clsx } from 'clsx'

const variants = {
  primary:   'bg-brand-600 hover:bg-brand-700 text-white',
  secondary: 'bg-slate-700 hover:bg-slate-600 text-slate-100',
  ghost:     'bg-transparent hover:bg-slate-800 text-slate-300',
  danger:    'bg-red-600 hover:bg-red-700 text-white',
}
const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({
  variant = 'primary', size = 'md', loading = false,
  icon: Icon, children, className, ...rest
}) {
  return (
    <button
      disabled={loading || rest.disabled}
      className={clsx(
        'inline-flex items-center justify-center gap-2',
        'font-medium rounded-xl transition-colors duration-150',
        'focus:outline-none focus:ring-2 focus:ring-brand-500',
        'focus:ring-offset-2 focus:ring-offset-surface',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant], sizes[size], className
      )}
      {...rest}
    >
      {loading ? (
        <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"
          fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10"
            stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      ) : Icon ? <Icon size={16}/> : null}
      {children}
    </button>
  )
}
