import { useParams } from 'react-router'
import { useEmployeeDashboard } from '../hooks/useEmployeeDashboard'
import { useActivityCompletion } from '../hooks/useActivityCompletion'
import { ApiError } from '../types/api'
import { copy } from '../i18n/en'
import { BackLink, Button, LoadingPanel, StatePanel } from '../components/UI'
import { EmployeeProfile } from '../components/EmployeeProfile'
import { CareerReadiness } from '../components/CareerReadiness'
import { CareerTrajectory } from '../components/CareerTrajectory'
import { SkillGapList } from '../components/SkillGapList'
import { RecommendationList } from '../components/RecommendationList'

export function EmployeeWorkspace() {
  const { employeeId = '' } = useParams()
  const { employee: profile, career } = useEmployeeDashboard(employeeId)
  const completion = useActivityCompletion(employeeId)
  const labels = copy.dashboard

  if (profile.isPending) return <><BackLink /><LoadingPanel /></>
  if (!profile.data) {
    const missing = profile.error instanceof ApiError && profile.error.code === 'NOT_FOUND'
    return <>
      <BackLink />
      <StatePanel error title={missing ? copy.employeeMissing : copy.errorTitle}
        description={missing ? copy.employeeMissingDescription : copy.errorDescription}>
        {!missing && <Button disabled={profile.isFetching} onClick={() => void profile.refetch()}>{profile.isFetching ? copy.retrying : copy.retry}</Button>}
      </StatePanel>
    </>
  }

  const employee = profile.data
  const overview = career.data
  return (
    <div className={`employee-dashboard ${completion.state.phase === 'success' ? 'dashboard-refreshed' : ''}`}>
      <BackLink />
      <div className="page-heading dashboard-heading">
        <div><p className="eyebrow">{copy.employeeEyebrow}</p><h1>{copy.employeeTitle}</h1><p>{copy.employeeDescription}</p></div>
        <span className="subtle-pill"><span className="status-dot" />{labels.title}</span>
      </div>
      {profile.isError && <div className="dashboard-alert" role="alert"><p>{labels.profileRefreshError}</p><Button disabled={profile.isFetching} onClick={() => void profile.refetch()}>{copy.retry}</Button></div>}
      <EmployeeProfile employee={employee} target={overview?.target} isTargetPending={career.isPending} />
      {career.isPending ? <LoadingPanel label={labels.careerLoading} /> : !overview ?
        <StatePanel error title={labels.careerError} description={labels.careerErrorDescription}>
          <Button disabled={career.isFetching} onClick={() => void career.refetch()}>{career.isFetching ? copy.retrying : copy.retry}</Button>
        </StatePanel> : <>
          {career.isError && <div className="dashboard-alert" role="alert"><p>{labels.careerRefreshError}</p><Button disabled={career.isFetching} onClick={() => void career.refetch()}>{copy.retry}</Button></div>}
          <div className="career-grid" key={employee.id}>
            <CareerReadiness readiness={overview.readiness} target={overview.target} projection={overview.recommendations[0]} />
            <CareerTrajectory employee={employee} target={overview.target} trajectory={overview.trajectory} />
          </div>
          <div className="development-grid">
            <SkillGapList skills={overview.skillGaps} />
            <RecommendationList key={employee.id} recommendations={overview.recommendations} target={overview.target}
              onStart={(recommendation) => void completion.complete(recommendation)} completion={completion.state}
              onRetry={() => void completion.retryCompletion()}
              onRefresh={() => void completion.retryRefresh()} />
          </div>
        </>}
    </div>
  )
}
