import { useParams } from 'react-router'
import { useEmployeeDashboard } from '../hooks/useEmployeeDashboard'
import { useSession } from '../hooks/useSession'
import { ApiError } from '../types/api'
import { copy } from '../i18n/en'
import { BackLink, Button, LoadingPanel, StatePanel } from '../components/UI'
import { EmployeeProfile } from '../components/EmployeeProfile'
import { CareerReadiness } from '../components/CareerReadiness'
import { CareerTrajectory } from '../components/CareerTrajectory'
import { SkillGapList } from '../components/SkillGapList'
import { RecommendationList } from '../components/RecommendationList'
import { ActivityHistory } from '../components/ActivityHistory'
import { CompletionResult } from '../components/CompletionResult'

function ErrorDetails({ error }: { error: unknown }) {
  if (!(error instanceof Error)) return null
  return <div className="backend-error-details"><p>{error.message}</p>
    {error instanceof ApiError && <><p>{error.status ? `HTTP ${error.status} · ` : ''}{error.backendCode || error.code}</p>
      {error.details.length > 0 && <details><summary>Error details</summary><pre>{JSON.stringify(error.details, null, 2)}</pre></details>}</>}
  </div>
}

function errorTitle(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback
  if (error.code === 'UNAUTHENTICATED') return 'Authentication required'
  if (error.code === 'FORBIDDEN') return 'Access denied'
  if (error.code === 'CONFIGURATION') return 'Backend configuration required'
  if (error.code === 'UNAVAILABLE' || error.code === 'NETWORK') return 'Backend unavailable'
  if (error.code === 'NOT_FOUND') return copy.employeeMissing
  return fallback
}

export function EmployeeWorkspace() {
  const { employeeId = '' } = useParams()
  const session = useSession()
  const { employee: profile, career, history, completion, complete, refresh } = useEmployeeDashboard(employeeId)
  const labels = copy.dashboard
  const backLink = session?.role === 'hr' ? <BackLink /> : null

  if (profile.isPending) return <>{backLink}<LoadingPanel /></>
  if (!profile.data) {
    return <>{backLink}<StatePanel error title={errorTitle(profile.error, copy.errorTitle)} description="The requested profile could not be loaded.">
      <ErrorDetails error={profile.error} />
      <Button disabled={profile.isFetching} onClick={() => void profile.refetch()}>{profile.isFetching ? copy.retrying : copy.retry}</Button>
    </StatePanel></>
  }

  const employee = profile.data
  const overview = career.data
  const result = completion.data?.employeeId === employeeId ? completion.data : undefined
  const currentMutation = completion.variables?.employeeId === employeeId
  const snapshotMismatch = overview?.version !== undefined && employee.version !== undefined && overview.version !== employee.version
  const receiptPending = result && ((employee.version ?? 0) < result.receipt.version || (overview?.version ?? 0) < result.receipt.version)
  const refreshing = profile.isFetching || career.isFetching
  const disableCompletion = completion.isPending || refreshing || snapshotMismatch || Boolean(receiptPending) || profile.isError || career.isError || history.isPending || history.isError
  return (
    <div className="employee-dashboard">
      {backLink}
      <div className="page-heading dashboard-heading">
        <div><p className="eyebrow">{copy.employeeEyebrow}</p><h1>{copy.employeeTitle}</h1><p>{copy.employeeDescription}</p></div>
        <span className="subtle-pill"><span className="status-dot" />{refreshing ? 'Refreshing progress…' : `Snapshot ${employee.version ?? '—'}`}</span>
      </div>
      {result && <CompletionResult receipt={result.receipt} skills={employee.skills} />}
      {currentMutation && completion.isError && <StatePanel error title="Completion could not be confirmed" description="Retry the same action with its existing idempotency key.">
        <ErrorDetails error={completion.error} />
        <Button disabled={completion.isPending} onClick={() => complete(completion.variables.eventId, completion.variables.recordId)}>Retry completion</Button>
      </StatePanel>}
      {(profile.isError || career.isError || snapshotMismatch || receiptPending) && <div className="dashboard-alert" role="alert">
        <div><p>{snapshotMismatch || receiptPending ? 'Progress is being refreshed. Profile and recommendations must use the same snapshot.' : 'The latest refresh failed. Previously loaded data may be out of date.'}</p>
          {profile.isError && <ErrorDetails error={profile.error} />}{career.isError && <ErrorDetails error={career.error} />}</div>
        <Button disabled={refreshing} onClick={() => void refresh()}>Refresh progress</Button>
      </div>}
      <EmployeeProfile employee={employee} target={overview?.target} isTargetPending={career.isPending} />
      {career.isPending ? <LoadingPanel label={labels.careerLoading} /> : !overview ?
        <StatePanel error title={errorTitle(career.error, labels.careerError)} description={labels.careerErrorDescription}>
          <ErrorDetails error={career.error} />
          <Button disabled={career.isFetching} onClick={() => void career.refetch()}>{career.isFetching ? copy.retrying : copy.retry}</Button>
        </StatePanel> : snapshotMismatch || receiptPending ? <LoadingPanel label="Synchronizing career state" /> : <>
          {(overview.skillsEstimated || (overview.warnings?.length ?? 0) > 0) && <details className="reconstruction-note">
            <summary>{overview.skillsEstimated ? 'Skill reconstruction includes historical estimates' : 'Skill reconstruction notes'}</summary>
            <p>The backend reconstructs effective skills from the assessment and eligible completion history.</p>
            {overview.warnings?.length ? <ul>{overview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : null}
          </details>}
          <div className="career-grid" key={employee.id}>
            <CareerReadiness readiness={overview.readiness} target={overview.target} projection={overview.recommendations[0]} />
            <CareerTrajectory employee={employee} target={overview.target} trajectory={overview.trajectory} />
          </div>
          <div className="development-grid">
            <SkillGapList skills={overview.targetRequirements ?? overview.skillGaps} />
            <RecommendationList recommendations={overview.recommendations} status={overview.status} summary={overview.explanationSummary} raw={overview.raw}
              history={history.data} onComplete={complete} completingEventId={currentMutation && completion.isPending ? completion.variables.eventId : undefined} disabled={disableCompletion} />
          </div>
        </>}
      {history.isPending ? <LoadingPanel label="Loading activity history" /> : history.isError ? <StatePanel error title="Activity history unavailable" description="Profile and recommendations remain available.">
        <ErrorDetails error={history.error} /><Button onClick={() => void history.refetch()}>Retry history</Button>
      </StatePanel> : <ActivityHistory records={history.data ?? []} />}
    </div>
  )
}
