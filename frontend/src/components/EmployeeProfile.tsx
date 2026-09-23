import { copy } from '../i18n/en'
import type { CareerTarget, Employee } from '../types/domain'
import { Icon } from './Icon'
import { Avatar } from './UI'

type Props = { employee: Employee; target: CareerTarget | null | undefined; isTargetPending: boolean }

export function EmployeeProfile({ employee, target, isTargetPending }: Props) {
  const labels = copy.dashboard
  return (
    <section className="employee-profile surface" aria-label={labels.profile}>
      <div className="employee-profile-main">
        <div className="employee-profile-identity">
          <Avatar name={employee.name} large />
          <div>
            <h2>{employee.name}</h2>
            <p className="employee-position">{employee.role}<span className="grade-badge">{employee.grade}</span></p>
          </div>
        </div>
        <dl className="employee-facts">
          <div><dt>{labels.department}</dt><dd>{employee.department}</dd></div>
          {employee.tenureLabel && <div><dt>{labels.tenure}</dt><dd>{employee.tenureLabel}</dd></div>}
          {employee.workFormat && <div><dt>Work format</dt><dd>{employee.workFormat}</dd></div>}
          <div><dt>Explanation language</dt><dd>{employee.preferredLanguage.toUpperCase()}</dd></div>
        </dl>
      </div>
      <div className="employee-goal-row">
        <Icon name="compass" />
        <div className="employee-goal"><span>{labels.goal}</span><p>{employee.careerGoal || labels.noGoal}</p></div>
        <div className="employee-target">
          <span>{labels.target}</span>
          {target ? <p>{target.role} <strong>{target.grade}</strong></p> :
            <p className="muted">{isTargetPending ? labels.targetLoading : target === null ? labels.noTarget : labels.targetUnavailable}</p>}
        </div>
      </div>
      <details className="effective-skills" open>
        <summary>Current effective skills <span>{employee.skills.length}</span></summary>
        <p>Current levels include completed activities reflected by the backend.</p>
        {employee.skills.length ? <ul className="effective-skill-list">{employee.skills.map((skill) =>
          <li key={skill.id}><span>{skill.name}</span><strong>{skill.current}<small> / {skill.scaleMax ?? '—'}</small></strong></li>,
        )}</ul> : <p>No effective skills supplied for this profile.</p>}
      </details>
    </section>
  )
}
