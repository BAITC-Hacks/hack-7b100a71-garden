import { copy } from '../i18n/en'
import type { SkillGap } from '../types/domain'
import { Icon } from './Icon'

function SkillGapRow({ skill }: { skill: SkillGap }) {
  const labels = copy.dashboard
  const scaleMax = skill.scaleMax
  const hasScale = typeof scaleMax === 'number' && Number.isFinite(scaleMax)
  const validScale = hasScale && scaleMax > 0 &&
    Number.isFinite(skill.current) && skill.current >= 0 && skill.current <= scaleMax &&
    Number.isFinite(skill.required) && skill.required >= 0 && skill.required <= scaleMax
  return (
    <li className="skill-row">
      <div className="skill-row-heading">
        <h3>{skill.name}</h3>
        <span className={`skill-status ${skill.critical ? 'skill-critical' : ''}`}>{skill.critical ? labels.critical : labels.standard}</span>
      </div>
      {validScale ? <div className="skill-comparison" aria-hidden="true">
        <div className="skill-required-bar" style={{ width: `${skill.required / scaleMax * 100}%` }} />
        <div className="skill-current-bar" style={{ width: `${skill.current / scaleMax * 100}%` }} />
        <span className="skill-target-marker" style={{ left: `${skill.required / scaleMax * 100}%` }} />
      </div> : <p className="comparison-unavailable">{hasScale ? labels.scaleUnavailable : labels.scaleMissing}</p>}
      <dl className="skill-values">
        <div><dt>{labels.currentLevel}</dt><dd>{skill.current}</dd></div>
        <div><dt>{labels.requiredLevel}</dt><dd>{skill.required}</dd></div>
        <div className="skill-gap-value"><dt>{labels.gap}</dt><dd>{skill.gap}</dd></div>
      </dl>
      {hasScale && <p className="skill-scale"><span>{labels.scaleMaximum}</span><strong>{scaleMax}</strong></p>}
    </li>
  )
}

export function SkillGapList({ skills }: { skills: SkillGap[] }) {
  const labels = copy.dashboard
  return (
    <section className="skills-card surface" aria-labelledby="skills-heading">
      <div className="dashboard-section-heading">
        <p className="eyebrow">{labels.skillsEyebrow}</p><h2 id="skills-heading">{labels.skills}</h2><p>{labels.skillsDescription}</p>
      </div>
      {skills.length ? <>
        <div className="skill-legend"><span><i />{labels.currentLegend}</span><span><i />{labels.targetLegend}</span></div>
        <ul className="skill-list">{skills.map((skill) => <SkillGapRow skill={skill} key={skill.id} />)}</ul>
      </> : <div className="dashboard-empty"><Icon name="grid" /><h3>{labels.noGaps}</h3><p>{labels.noGapsDescription}</p></div>}
    </section>
  )
}
