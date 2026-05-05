import clsx from 'clsx'
import { ChevronDown, ChevronRight } from 'lucide-react'

import Button from '../../components/ui/Button'
import Card from '../../components/ui/Card'

const SCORE_LABELS = {
  eta_score: 'ETA Score',
  capacity_score: 'Capacity Score',
  specialty_score: 'Specialty Score',
  final_score: 'Final Score',
}

function formatScoreLabel(value) {
  return SCORE_LABELS[value] || String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatScoreValue(value) {
  const numeric = Number(value || 0)
  const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric
  return `${percent.toFixed(0)}%`
}

export default function ExplainabilityPanel({
  dispatch,
  expanded,
  onToggleExpanded,
  translationOriginalComplaint,
  translationLanguageName,
  translationModel,
  translationExpanded,
  onToggleTranslation,
}) {
  const explanation = dispatch?.explanation
  const legacyText = dispatch?.explanation_text

  return (
    <Card className="mt-3">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
        AI Explanation
      </p>
      <p
        className={clsx(
          'mt-3 text-sm leading-6 text-slate-300',
          !expanded && 'line-clamp-2'
        )}
      >
        {explanation?.selected_reason || legacyText || 'AI routing analysis will appear here.'}
      </p>

      {explanation?.score_breakdown ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {Object.entries(explanation.score_breakdown).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-border bg-slate-900/80 p-3">
              <span className="text-xs text-slate-500">{formatScoreLabel(key)}</span>
              <strong className="mt-1 block text-lg font-semibold text-white">
                {formatScoreValue(value)}
              </strong>
            </div>
          ))}
        </div>
      ) : null}

      {explanation?.rejected_hospitals?.length > 0 ? (
        <div className="mt-3">
          <p className="m-0 text-xs text-slate-500">Rejected alternatives:</p>
          <ul className="mt-2 space-y-1 pl-4">
            {explanation.rejected_hospitals.map((hospital) => (
              <li key={hospital.id} className="text-xs leading-5 text-slate-300">
                {hospital.name} - {hospital.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {translationOriginalComplaint && translationLanguageName ? (
        <div className="mt-4 rounded-xl border border-border bg-slate-900/80 p-3">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 text-left"
            onClick={onToggleTranslation}
          >
            <span className="text-xs font-medium text-slate-300">
              Show original ({translationLanguageName})
            </span>
            {translationExpanded ? (
              <ChevronDown size={14} className="text-slate-500" />
            ) : (
              <ChevronRight size={14} className="text-slate-500" />
            )}
          </button>
          {translationExpanded ? (
            <div className="mt-3 space-y-2">
              <p className="rounded-lg bg-slate-950 p-2 text-xs italic leading-5 text-slate-400">
                {translationOriginalComplaint}
              </p>
              <p className="text-[10px] text-slate-500">
                {translationModel
                  ? `Translated using Helsinki-NLP Opus-MT (offline) via ${translationModel}`
                  : 'Translated using Helsinki-NLP Opus-MT (offline)'}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      <Button
        className="mt-3"
        variant="ghost"
        size="sm"
        onClick={onToggleExpanded}
      >
        {expanded ? 'Show less' : 'Show more'}
      </Button>
    </Card>
  )
}
