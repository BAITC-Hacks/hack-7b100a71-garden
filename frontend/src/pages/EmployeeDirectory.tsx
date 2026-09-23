import { Link } from 'react-router'
import { useState } from 'react'
import { useEmployees } from '../hooks/useEmployees'
import { copy } from '../i18n/en'
import { Avatar, Button, LoadingPanel, StatePanel } from '../components/UI'
import { Icon } from '../components/Icon'
import { useSession } from '../hooks/useSession'
import { ApiError } from '../types/api'

export function EmployeeDirectory() {
  const session = useSession()
  const [search, setSearch] = useState('')
  const { data: employees, isPending, isError, error, refetch } = useEmployees()
  if (session?.role !== 'hr') return <StatePanel error title="Access restricted" description="The employee directory is available to HR." />
  const needle = search.trim().toLocaleLowerCase()
  const visible = employees?.filter((employee) => [employee.id, employee.name, employee.role, employee.department].some((value) => value.toLocaleLowerCase().includes(needle)))
  const errorTitle = error instanceof ApiError && error.code === 'UNAUTHENTICATED' ? 'Authentication required'
    : error instanceof ApiError && error.code === 'FORBIDDEN' ? 'Access restricted' : copy.errorTitle
  return <>
    <section className="welcome-hero">
      <div className="hero-copy"><p className="eyebrow">{copy.homeEyebrow}</p><h1>{copy.homeTitle}</h1><p className="hero-description">{copy.homeDescription}</p><div className="hero-note"><span className="small-line" />{copy.heroNote}</div></div>
      <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><span className="orbit-dot dot-one" /><span className="orbit-dot dot-two" /><div className="direction-mark"><Icon name="arrow" /></div><span className="art-caption">GROW WITH INTENTION</span></div>
    </section>
    <section className="directory-section" aria-labelledby="directory-title">
      <div className="section-heading"><div><p className="eyebrow">PEOPLE & DEVELOPMENT</p><h2 id="directory-title">Employee directory</h2><p>Open a profile to explore skills, career direction, and recommended next steps.</p></div><span className="subtle-pill"><Icon name="people" />{employees ? `${employees.length} employees` : 'HR access'}</span></div>
      {!!employees?.length && <label className="directory-search">Find an employee<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, ID, role, or team" /></label>}
      {isPending ? <LoadingPanel /> : isError ? <StatePanel error title={errorTitle} description={error.message}><Button onClick={() => void refetch()}>{copy.retry}</Button></StatePanel> : !employees?.length ? <StatePanel title={copy.emptyTitle} description={copy.emptyDescription} /> : !visible?.length ? <StatePanel title="No matching profiles" description="Try another name, ID, role, or team." /> :
        <div className="profile-grid">{visible.map((employee) => <Link to={`/employees/${encodeURIComponent(employee.id)}`} className="profile-card surface" key={employee.id}>
          <div className="profile-top"><Avatar name={employee.name} large /><span className="grade-badge">{employee.grade}</span></div>
          <h3>{employee.name}</h3><p className="profile-role">{employee.role}</p><p className="profile-department">{employee.department}</p>
          <div className="profile-action">{copy.openProfile}<Icon name="arrow" /></div>
        </Link>)}</div>}
      <p className="demo-footnote"><span className="status-dot" />Profiles in the active dataset. This directory is available to HR.</p>
    </section>
  </>
}
