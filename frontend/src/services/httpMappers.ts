import { ApiError } from '../types/api'
import type { ActivityStatus, CareerOverview, Employee, HRAnalytics, Language, Recommendation } from '../types/domain'

export type JsonObject = Record<string, unknown>
export function object(value: unknown, label = 'response'): JsonObject {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('INVALID_RESPONSE', `The API ${label} is incomplete.`)
  return value as JsonObject
}
export function rows(value: unknown, label = 'list'): unknown[] {
  if (!Array.isArray(value)) throw new ApiError('INVALID_RESPONSE', `The API ${label} is incomplete.`)
  return value
}
export function text(value: unknown, label = 'field'): string {
  if (typeof value !== 'string') throw new ApiError('INVALID_RESPONSE', `The API ${label} is incomplete.`)
  return value
}
export const number = (value: unknown): number | undefined => typeof value === 'number' && Number.isFinite(value) ? value : undefined
const optionalObject = (value: unknown): JsonObject | undefined => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : undefined
const optionalText = (value: unknown) => typeof value === 'string' ? value : undefined
const optionalBoolean = (value: unknown) => typeof value === 'boolean' ? value : undefined
const label = (value: string) => value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
const language = (value: unknown): Language | undefined => value === 'en' || value === 'kk' || value === 'ru' ? value : undefined
export type SkillNames = Map<string, string>

// This scale is explicitly defined by the pinned integration contract's domain
// schema (SkillLevel 0..5). It is not inferred from a record or scoring rule.
const contractSkillScaleMax = 5
export function mapEmployee(value: unknown, names: SkillNames, effective?: unknown, version?: number): Employee {
  const employee = object(value, 'employee')
  const levels = object(effective ?? employee.skills, 'skill levels')
  const goal = optionalObject(employee.career_goal)
  const preferredLanguage = language(employee.preferred_language)
  if (!preferredLanguage) throw new ApiError('INVALID_RESPONSE', 'The employee language is missing or unsupported.')
  return {
    id: text(employee.employee_id, 'employee ID'), name: text(employee.full_name, 'employee name'),
    role: text(employee.role), grade: text(employee.grade), department: text(employee.department), preferredLanguage,
    tenureLabel: number(employee.tenure_months) === undefined ? undefined : `${employee.tenure_months} months`,
    careerGoal: goal ? `${text(goal.target_grade)} · ${text(goal.target_role)}` : null,
    snapshotVersion: version,
    skills: Object.entries(levels).map(([id, current]) => {
      if (number(current) === undefined) throw new ApiError('INVALID_RESPONSE', 'The API supplied an invalid skill level.')
      return { id, name: names.get(id) ?? id, current: current as number, scaleMax: contractSkillScaleMax }
    }),
  }
}

function mapRecommendation(value: unknown, names: SkillNames): Recommendation {
  const item = object(value, 'recommendation')
  const simulation = optionalObject(item.simulation)
  const factors = optionalObject(item.factors)
  const explanation = optionalObject(item.explanation)
  const scoring = optionalObject(item.scoring_evidence)
  const targetImpacts = new Map((Array.isArray(simulation?.target_skill_impact) ? simulation.target_skill_impact : [])
    .map((impact) => { const row = object(impact); return [text(row.skill_id), row] as const }))
  const impactRows = Array.isArray(simulation?.skill_impact) ? simulation.skill_impact : []
  return {
    eventId: text(item.event_id, 'event ID'), title: text(item.title, 'recommendation title'), score: number(item.score),
    durationMinutes: number(scoring?.duration_hours) === undefined ? undefined : (scoring!.duration_hours as number) * 60,
    readinessBefore: simulation?.readiness_before == null ? null : number(simulation.readiness_before),
    readinessAfter: simulation?.readiness_after == null ? null : number(simulation.readiness_after),
    skillImpact: impactRows.map((value) => {
      const impact = object(value); const id = text(impact.skill_id); const target = targetImpacts.get(id)
      return { skillId: id, name: names.get(id) ?? id, current: number(impact.before), after: number(impact.after),
        gain: number(impact.actual_gain), required: number(target?.required), critical: optionalBoolean(target?.critical) }
    }),
    explanation: {
      text: optionalText(explanation?.text), language: language(explanation?.language), source: optionalText(explanation?.source),
      factors: factors ? Object.entries(factors).map(([id, value]) => {
        const factor = object(value)
        return { id, label: label(id), value: number(factor.normalized), raw: number(factor.raw), normalized: number(factor.normalized),
          weight: number(factor.weight), contribution: number(factor.contribution) }
      }) : [],
      facts: Array.isArray(explanation?.facts) ? explanation.facts.map((value) => {
        const fact = object(value)
        return { id: text(fact.fact_id), code: text(fact.code), values: optionalObject(fact.values) ?? {},
          evidencePaths: Array.isArray(fact.evidence_paths) ? fact.evidence_paths.map((path) => text(path)) : [] }
      }) : [],
    },
    supportingEvidence: ['evidence', 'scoring_evidence', 'history_signals', 'simulation'].flatMap((id) => {
      const values = optionalObject(item[id]); return values ? [{ id, label: label(id), values }] : []
    }),
  }
}

export function mapOverview(value: unknown, names: SkillNames, expectedId: string): CareerOverview {
  const data = object(value, 'career response')
  const employeeId = text(data.employee_id)
  if (employeeId !== expectedId) throw new ApiError('INVALID_RESPONSE', 'The career response belongs to another employee.')
  const target = optionalObject(data.target)
  const readiness = optionalObject(data.career_readiness)
  const state = optionalObject(data.career_state)
  const reconstruction = optionalObject(state?.skills_reconstruction)
  const summary = optionalObject(data.explanation_summary)
  return {
    employeeId, snapshotVersion: number(data.version), status: optionalText(data.status),
    summary: optionalText(summary?.text), skillsEstimated: optionalBoolean(reconstruction?.is_estimate),
    warnings: Array.isArray(reconstruction?.warnings) ? reconstruction.warnings.map((value) => {
      const warning = object(value)
      return { code: text(warning.code), message: text(warning.message),
        recordIds: Array.isArray(warning.record_ids) ? warning.record_ids.map((id) => text(id)) : undefined }
    }) : [],
    target: target ? { role: text(target.role), grade: text(target.grade) } : null,
    // The backend supplies current/target positions, not employment history or a
    // guaranteed progression path. The view displays its existing anchor state.
    trajectory: null,
    readiness: number(readiness?.current) === undefined ? null : { current: readiness!.current as number },
    skillGaps: rows(data.skill_gaps, 'skill gaps').map((value) => {
      const skill = object(value); const id = text(skill.skill_id)
      return { id, name: names.get(id) ?? id, current: number(skill.current), required: number(skill.required),
        gap: number(skill.gap), critical: optionalBoolean(skill.critical), scaleMax: contractSkillScaleMax }
    }),
    recommendations: rows(data.recommendations, 'recommendations').map((item) => mapRecommendation(item, names)),
  }
}

const statuses: ActivityStatus[] = ['completed', 'in_progress', 'no_show', 'dropped', 'declined', 'overdue']
export function mapHRAnalytics(value: unknown, version?: number): HRAnalytics {
  const data = object(value, 'HR analytics')
  const coverage = optionalObject(data.employees_without_next_step)
  const participation = optionalObject(data.activity_participation)
  const summary = optionalObject(data.participation_summary)
  return {
    snapshotVersion: version, totalEmployees: number(data.employee_count), gapBasis: optionalText(data.gap_basis),
    withoutNextStep: coverage?.count == null ? null : number(coverage.count),
    nextStepCoverage: coverage ? { available: optionalBoolean(coverage.available), count: coverage.count == null ? null : number(coverage.count),
      evaluatedCount: number(coverage.evaluated_count), pendingCount: number(coverage.pending_count), complete: optionalBoolean(coverage.complete) } : undefined,
    participatingEmployees: number(summary?.participating_employees), participationRecordCount: number(summary?.total_records),
    commonSkillGaps: Array.isArray(data.common_skill_gaps) ? data.common_skill_gaps.map((value) => {
      const skill = object(value)
      return { skillId: text(skill.skill_id), name: text(skill.skill_name), employeeCount: number(skill.employee_count) }
    }) : undefined,
    activityStatuses: participation ? Object.entries(participation).flatMap(([status, count]) => statuses.includes(status as ActivityStatus)
      ? [{ status: status as ActivityStatus, count: number(count) }] : []) : undefined,
    // Neither development count, per-activity participation nor a rate is supplied.
    // In particular, participating_employees is not "employees in development".
  }
}
