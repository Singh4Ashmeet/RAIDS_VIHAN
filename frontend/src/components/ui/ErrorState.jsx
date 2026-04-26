import Button from './Button'
import { AlertCircle } from 'lucide-react'

export default function ErrorState({ message, onRetry }) {
  return (
    <div className="border border-red-500/30 bg-red-500/10
      rounded-xl p-5 flex items-start gap-3">
      <AlertCircle size={20} className="text-red-400 flex-shrink-0
        mt-0.5"/>
      <div className="flex-1">
        <p className="text-red-300 text-sm font-medium">
          Something went wrong
        </p>
        <p className="text-red-400/70 text-xs mt-1">{message}</p>
      </div>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
