import { clsx } from 'clsx'

const map = {
  available:   'bg-emerald-400',
  en_route:    'bg-amber-400',
  at_scene:    'bg-amber-400',
  transporting:'bg-blue-400',
  at_hospital: 'bg-slate-500',
  unavailable: 'bg-slate-500',
  critical:    'bg-red-400',
}
const pulse = ['available','en_route','at_scene','critical']

export default function StatusDot({ status }) {
  const color = map[status] || 'bg-slate-500'
  const doPulse = pulse.includes(status)
  return (
    <span className="relative inline-flex w-2.5 h-2.5">
      {doPulse && (
        <span className={clsx(
          'animate-ping absolute inline-flex h-full w-full',
          'rounded-full opacity-75', color
        )}/>
      )}
      <span className={clsx(
        'relative inline-flex rounded-full w-2.5 h-2.5', color
      )}/>
    </span>
  )
}
