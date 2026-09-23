import { copy } from '../i18n/en'
import { Link } from 'react-router'
import { Button, LoadingPanel, StatePanel } from '../components/UI'
import { HRMetricCards } from '../components/hr/HRMetricCards'
import { HRNextStep, HRParticipation, HRSkillGaps, HRStatusDistribution } from '../components/hr/HRInsights'
import { useHRAnalytics } from '../hooks/useHRAnalytics'
import { apiMode } from '../services/api'
import { isAggregateValue, isParticipationRate } from '../utils/formatAnalytics'

export function HRWorkspace() {
  const analytics = useHRAnalytics()
  const data = analytics.data
  const hasData = data && (
    [data.totalEmployees, data.employeesInDevelopment, data.withoutNextStep].some(isAggregateValue)
    || isParticipationRate(data.participationRate)
    || Boolean(data.commonSkillGaps?.length || data.activityParticipation?.length || data.activityStatuses?.length)
  )
  const refresh = <Button disabled={analytics.isFetching} onClick={() => void analytics.refetch()}>
    {analytics.isFetching ? copy.hr.refreshing : copy.hr.refresh}
  </Button>
  return <>
    <div className="hr-page-heading">
      <div className="page-heading"><p className="eyebrow">{copy.hrEyebrow}</p><h1>{copy.hrTitle}</h1><p>{copy.hrDescription}</p></div>
      <div className="hr-header-actions"><Link className="button" to="/hr/dataset">{copy.dataset.nav}</Link>{data && refresh}</div>
    </div>
    {analytics.isPending ? <LoadingPanel label={copy.hr.loading} />
      : analytics.isError && !data ? <StatePanel error title={copy.hr.error} description={copy.hr.errorDescription}>
        <Button disabled={analytics.isFetching} onClick={() => void analytics.refetch()}>{analytics.isFetching ? copy.retrying : copy.retry}</Button>
      </StatePanel>
        : <>
          {analytics.isError && <p className="hr-refresh-error" role="alert">{copy.hr.refreshError}</p>}
          <span className="sr-only" role="status">{analytics.isFetching ? copy.hr.refreshing : ''}</span>
          {hasData && data ? <section className="hr-dashboard" aria-label={copy.hr.scope}>
            <HRMetricCards analytics={data} />
            <div className="hr-priority-grid"><HRSkillGaps gaps={data.commonSkillGaps} /><HRNextStep count={data.withoutNextStep} /></div>
            <div className="hr-detail-grid"><HRParticipation activities={data.activityParticipation} rate={data.participationRate} /><HRStatusDistribution statuses={data.activityStatuses} /></div>
            <p className="hr-chart-note">{copy.hr.chartNote}</p>
          </section> : <StatePanel title={copy.hr.empty} description={copy.hr.emptyDescription} />}
        </>}
    {apiMode === 'mock' && <p className="hr-sample-note">{copy.hr.sample}</p>}
    <p className="demo-footnote">{copy.hrPrivacy}</p>
  </>
}
