import { clsx } from 'clsx'
import { useId } from 'react'

export default function Input({
  label, error, icon: Icon, rightElement, className, ...rest
}) {
  const generatedId = useId()
  const inputId = rest.id || generatedId

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-slate-300">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2
            text-slate-400 pointer-events-none">
            <Icon size={16}/>
          </div>
        )}
        <input
          id={inputId}
          className={clsx(
            'w-full bg-slate-800 border border-border rounded-xl',
            'px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500',
            'focus:outline-none focus:ring-2 focus:ring-brand-500',
            'focus:border-transparent transition-all',
            Icon && 'pl-10',
            rightElement && 'pr-11',
            error && 'border-red-500 focus:ring-red-500',
            className
          )}
          {...rest}
        />
        {rightElement && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2">
            {rightElement}
          </div>
        )}
      </div>
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  )
}
