import { useQuery } from '@tanstack/react-query'
import { HRAnalyticsPanel } from '../components/HRAnalyticsPanel'
import { DatasetUpload } from '../components/DatasetUpload'
import { Button, LoadingPanel, StatePanel } from '../components/UI'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { ApiError } from '../types/api'
import { useSession } from '../hooks/useSession'
import '../styles/hr.css'

export function HRWorkspace() {
  const session = useSession()
  const analytics = useQuery({
    queryKey: queryKeys.hr,
    queryFn: ({ signal }) => api.getHRAnalytics({ signal }),
    enabled: session?.role === 'hr',
  })
  if (session?.role !== 'hr') return <StatePanel error title="HR access required" description="Sign in with an HR identity to view analytics and manage the dataset." />
  return <>
    <div className="page-heading"><p className="eyebrow">PEOPLE & DEVELOPMENT</p><h1>HR workspace</h1>
      <p>Current skill gaps, activity participation and dataset management.</p></div>
    {analytics.isPending && <LoadingPanel label="Loading HR analytics" />}
    {analytics.isError && <StatePanel error title="Analytics unavailable" description={analytics.error.message}>
      {analytics.error instanceof ApiError && <p>{analytics.error.backendCode ?? analytics.error.code}{analytics.error.status ? ` · HTTP ${analytics.error.status}` : ''}</p>}
      <Button onClick={() => void analytics.refetch()}>Retry analytics</Button>
    </StatePanel>}
    {analytics.data && <HRAnalyticsPanel analytics={analytics.data} />}
    <DatasetUpload />
    <p className="demo-footnote">Aggregate reporting only. These figures do not rank employees or guarantee promotion eligibility.</p>
  </>
}
