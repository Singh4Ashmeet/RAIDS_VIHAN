import Card from './Card'

export default function MetricCard({ label, value, hint, icon: Icon }) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-400">{label}</p>
        {Icon ? <Icon size={18} className="text-slate-400" /> : null}
      </div>
      <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      {hint ? <p className="mt-2 text-xs text-slate-500">{hint}</p> : null}
    </Card>
  )
}
