import { useParams } from 'react-router'
import { useEmployee } from '../hooks/useEmployees'
import { ApiError } from '../types/api'
import { copy } from '../i18n/en'
import { Avatar, BackLink, Button, LoadingPanel, StatePanel } from '../components/UI'
import { Icon } from '../components/Icon'

export function EmployeeWorkspace() {
  const { employeeId = '' } = useParams()
  const { data: employee, isPending, error, refetch } = useEmployee(employeeId)
  if (isPending) return <><BackLink /><LoadingPanel /></>
  if (error) {
    const missing = error instanceof ApiError && error.code === 'NOT_FOUND'
    return <><BackLink /><StatePanel error title={missing ? copy.employeeMissing : copy.errorTitle} description={missing ? copy.employeeMissingDescription : error.message}>
      {!missing && <Button onClick={() => void refetch()}>{copy.retry}</Button>}
    </StatePanel></>
  }
  return <>
    <BackLink />
    <div className="page-heading"><p className="eyebrow">{copy.employeeEyebrow}</p><h1>{copy.employeeTitle}</h1><p>{copy.employeeDescription}</p></div>
    <section className="identity-card surface" aria-label={copy.profileLabel}>
      <div className="identity-name"><Avatar name={employee.name} large /><div><h2>{employee.name}</h2><p>{employee.department}</p></div></div>
      <div className="identity-position"><p className="eyebrow">{copy.currentPosition}</p><strong>{employee.role}</strong><span className="grade-badge">{employee.grade}</span></div>
    </section>
    <section className="foundation-panel surface"><div className="foundation-heading"><span className="state-icon"><Icon name="compass" /></span><span className="subtle-pill">{copy.foundationBadge}</span></div><h2>{copy.foundationTitle}</h2><p className="foundation-description">{copy.foundationDescription}</p>
      <div className="pillar-grid">{copy.pillars.map((pillar) => <div className="pillar" key={pillar.number}><span>{pillar.number}</span><h3>{pillar.title}</h3><p>{pillar.description}</p></div>)}</div>
    </section>
  </>
}
