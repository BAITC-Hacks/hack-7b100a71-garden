import { Link } from 'react-router'
import { useEmployees } from '../hooks/useEmployees'
import { copy } from '../i18n/en'
import { Avatar, Button, LoadingPanel, StatePanel } from '../components/UI'
import { Icon } from '../components/Icon'

export function EmployeeDirectory() {
  const { data: employees, isPending, isError, error, refetch } = useEmployees()
  return <>
    <section className="welcome-hero">
      <div className="hero-copy"><p className="eyebrow">{copy.homeEyebrow}</p><h1>{copy.homeTitle}</h1><p className="hero-description">{copy.homeDescription}</p><div className="hero-note"><span className="small-line" />{copy.heroNote}</div></div>
      <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><span className="orbit-dot dot-one" /><span className="orbit-dot dot-two" /><div className="direction-mark"><Icon name="arrow" /></div><span className="art-caption">GROW WITH INTENTION</span></div>
    </section>
    <section className="directory-section" aria-labelledby="directory-title">
      <div className="section-heading"><div><p className="eyebrow">{copy.peopleLabel}</p><h2 id="directory-title">{copy.peopleTitle}</h2><p>{copy.peopleDescription}</p></div><span className="subtle-pill"><Icon name="people" />{copy.demo}</span></div>
      {isPending ? <LoadingPanel /> : isError ? <StatePanel error title={copy.errorTitle} description={error.message}><Button onClick={() => void refetch()}>{copy.retry}</Button></StatePanel> : !employees?.length ? <StatePanel title={copy.emptyTitle} description={copy.emptyDescription} /> :
        <div className="profile-grid">{employees.map((employee) => <Link to={`/employees/${encodeURIComponent(employee.id)}`} className="profile-card surface" key={employee.id}>
          <div className="profile-top"><Avatar name={employee.name} large /><span className="grade-badge">{employee.grade}</span></div>
          <h3>{employee.name}</h3><p className="profile-role">{employee.role}</p><p className="profile-department">{employee.department}</p>
          <div className="profile-action">{copy.openProfile}<Icon name="arrow" /></div>
        </Link>)}</div>}
      <p className="demo-footnote"><span className="status-dot" />{copy.demoNote}</p>
    </section>
  </>
}
