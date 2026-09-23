import { copy } from '../i18n/en'
import type { Recommendation } from '../types/domain'

function SuppliedLevel({ value }: { value?: number | null }) {
  return typeof value === 'number' && Number.isFinite(value) ? value : <span className="impact-missing">{copy.dashboard.notProvided}</span>
}

export function ActivityImpact({ skills, expanded = false }: { skills: Recommendation['skillImpact']; expanded?: boolean }) {
  const labels = copy.dashboard
  if (!skills?.length) return <p className="impact-unavailable">{labels.noSkillImpact}</p>
  return <ul className="activity-skill-list" aria-label={labels.skillImpact}>
    {skills.map((skill) => <li key={skill.skillId}>
      <div className="activity-skill-heading"><span>{skill.name}</span>
        {skill.critical === true ? <span className="skill-status skill-critical">{labels.critical}</span> :
          expanded && skill.critical === false ? <span className="skill-status">{labels.standard}</span> : null}
      </div>
      <dl className="activity-skill-values">
        <div><dt>{labels.currentLevel}</dt><dd><SuppliedLevel value={skill.current} /></dd></div>
        <div><dt>{labels.expectedAfter}</dt><dd><SuppliedLevel value={skill.after} /></dd></div>
        <div><dt>{labels.targetRequirement}</dt><dd><SuppliedLevel value={skill.required} /></dd></div>
      </dl>
      {expanded && typeof skill.gain === 'number' && Number.isFinite(skill.gain) &&
        <dl className="activity-skill-gain"><div><dt>{labels.activityGain}</dt><dd>{skill.gain}</dd></div></dl>}
    </li>)}
  </ul>
}
