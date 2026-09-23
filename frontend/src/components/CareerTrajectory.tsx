import { copy } from '../i18n/en'
import type { CareerPosition, CareerTarget, CareerTrajectory as Trajectory, Employee } from '../types/domain'
import { Icon } from './Icon'

const positionLabels: Record<CareerPosition['state'], string> = {
  past: copy.dashboard.pastStep,
  current: copy.dashboard.currentStep,
  intermediate: copy.dashboard.intermediateStep,
  target: copy.dashboard.targetStep,
  future: copy.dashboard.futureStep,
}

export function CareerTrajectory({ employee, target, trajectory }: {
  employee: Employee; target: CareerTarget | null; trajectory: Trajectory | null
}) {
  const labels = copy.dashboard
  const positions = trajectory?.positions ?? []
  const hasPath = positions.length > 0
  // Missing anchors are shown as separate facts, never inserted into the supplied path.
  const needsSummary = !positions.some((position) => position.state === 'current') ||
    (target !== null && !positions.some((position) => position.state === 'target'))
  return (
    <section className="trajectory-card surface" aria-labelledby="trajectory-heading">
      <div className="dashboard-card-heading">
        <div><p className="eyebrow">{labels.trajectoryEyebrow}</p><h2 id="trajectory-heading">{labels.trajectory}</h2></div>
        {trajectory && <span className="subtle-pill">{trajectory.kind === 'transition' ? labels.transition : labels.promotion}</span>}
      </div>
      {needsSummary && <dl className="trajectory-summary" aria-label={labels.positionSummary}>
        <div><dt>{labels.currentStep}</dt><dd>{employee.role}<span className="grade-badge">{employee.grade}</span></dd></div>
        {target && <div><dt>{labels.targetStep}</dt><dd>{target.role}<span className="grade-badge">{target.grade}</span></dd></div>}
      </dl>}
      {hasPath ? <ol className={`trajectory-path ${positions.length > 2 ? 'trajectory-path-extended' : ''}`} aria-label={labels.trajectoryList}>
        {positions.map((position, index) => <li className={`trajectory-${position.state}`}
          key={`${position.state}-${position.role}-${position.grade}-${index}`} aria-current={position.state === 'current' ? 'step' : undefined}>
          <span className="trajectory-node" aria-hidden="true">
            {position.state === 'target' ? <Icon name="arrow" /> : position.state === 'past' ? '✓' : <span />}
          </span>
          <div className="trajectory-step-content">
            <p className="trajectory-step-label">{positionLabels[position.state]}</p>
            <div className="trajectory-position"><h3>{position.role}</h3><span className="grade-badge">{position.grade}</span></div>
          </div>
        </li>)}
      </ol> : <div className="trajectory-unavailable">
        <h3>{labels.trajectoryUnavailable}</h3><p>{labels.trajectoryUnavailableDescription}</p>
      </div>}
      {!target ? <div className="trajectory-no-target"><h3>{labels.noTargetTitle}</h3><p>{labels.noTargetDescription}</p></div> :
        hasPath && <p className="trajectory-note">{labels.trajectoryNote}</p>}
    </section>
  )
}
