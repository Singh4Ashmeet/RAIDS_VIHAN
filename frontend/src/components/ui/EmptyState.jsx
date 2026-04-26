export default function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center
      py-16 text-center gap-4">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-slate-700/50
          flex items-center justify-center">
          <Icon size={28} className="text-slate-400"/>
        </div>
      )}
      <div>
        <p className="text-slate-200 font-medium text-base">{title}</p>
        {subtitle && (
          <p className="text-slate-500 text-sm mt-1">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
