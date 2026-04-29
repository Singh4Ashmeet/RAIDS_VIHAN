import Card from '../../components/ui/Card'
import EmptyState from '../../components/ui/EmptyState'
import { ShieldCheck } from 'lucide-react'

export default function OverrideHistory() {
  return (
    <Card>
      <EmptyState
        icon={ShieldCheck}
        title="Override history"
        subtitle="Approved human override audit records appear in Analytics and active dispatch panels."
      />
    </Card>
  )
}
