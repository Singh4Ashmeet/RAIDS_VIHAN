import ActiveIncidentsList from './subcomponents/ActiveIncidentsList'
import DispatchDecisionCard from './subcomponents/DispatchDecisionCard'
import DispatchFeed from './subcomponents/DispatchFeed'
import ExplainabilityPanel from './subcomponents/ExplainabilityPanel'

export default function CommandCenter({
  ambulances,
  hospitals,
  latestDispatch,
  dispatchHistory,
  notifications,
}) {
  const explainabilityDispatch = latestDispatch
    ? {
        ...latestDispatch,
        explanation_text: 'Dispatch explanation is ready for review.',
      }
    : latestDispatch

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <DispatchDecisionCard
        dispatch={latestDispatch}
        ambulances={ambulances}
        hospitals={hospitals}
      />
      <ExplainabilityPanel
        dispatch={explainabilityDispatch}
        hospitals={hospitals}
        expanded={false}
      />
      <ActiveIncidentsList />
      <DispatchFeed dispatchHistory={[]} notifications={notifications} />
    </section>
  )
}
