// HTTP shapes mirror the approved FastAPI/engine boundary. Keep raw evidence.
export type Language = 'kk' | 'ru' | 'en'
export type RecommendationStatus = 'ok' | 'no_next_grade' | 'target_satisfied' | 'no_eligible_recommendations' | 'invalid_target_requirements'
export type ActivityStatus = 'completed' | 'in_progress' | 'no_show' | 'dropped' | 'declined' | 'overdue'
export interface SnapshotMeta { version: number; as_of_date: string; total?: number; offset?: number; limit?: number }
export interface Envelope<T> { data: T; meta?: SnapshotMeta }
export interface EmployeeDTO {
  employee_id: string; full_name: string; department: string; role: string; grade: string
  manager_id: string | null; hire_date: string; tenure_months: number; work_format: string
  preferred_language: Language; career_goal: { target_role: string; target_grade: string } | null
  skills: Record<string, number>; last_review_date: string
}
export interface SkillDTO { skill_id: string; name: string; type: string; category: string; description: string }
export interface RoleProfileDTO { role: string; grade: string; required_skills: Record<string, number>; critical_skills: string[] }
export interface EmployeeDetailDTO { employee: EmployeeDTO; role_profile: RoleProfileDTO | null; effective_skills: Record<string, number> }
export interface EventDTO {
  event_id: string; title: string; description: string; type: string; format: string
  duration_hours: number; mandatory: boolean; target_roles: string[]; target_grades: string[]
  develops_skills: Array<{ skill_id: string; gain: number; max_level: number }>
  prerequisites: Record<string, number>; upcoming_sessions: string[]
}
export interface ActivityRecordDTO {
  record_id: string; employee_id: string; event_id: string; date: string; due_date: string | null
  status: ActivityStatus; completion_pct: number; score: number | null; feedback_rating: number | null
  assigned_by: string; completed_on?: string | null; completed_at?: string | null; runtime_sequence?: number | null
}
export interface SkillGapDTO { skill_id: string; current: number; required: number; gap: number; critical: boolean }
export interface ReadinessDTO {
  current: number | null; status: 'available' | 'unavailable'; reason: string | null
  critical_weight: number; weighted_covered_levels: number; weighted_required_levels: number
  critical_requirements_met: boolean | null; remaining_critical_gaps: SkillGapDTO[]; all_requirements_met: boolean | null
}
export interface TargetDTO { role: string; grade: string; source: 'career_goal' | 'next_grade' }
export interface ExplanationDTO {
  language: Language; source: 'deterministic' | 'openai'; text: string
  facts: Array<{ fact_id: string; code: string; values: Record<string, unknown>; evidence_paths: string[] }>
  segments: Array<{ fact_id: string; text: string }>
}
export interface ReconstructionDTO {
  effective_skills: Record<string, number>; applied_record_ids: string[]; uncertain_record_ids: string[]
  skill_changes: Array<{ record_id: string; event_id: string; skill_id: string; before: number; after: number; gain_applied: number; date_basis: string }>
  warnings: Array<{ code: string; message: string; record_ids: string[] }>; date_policy: string; is_estimate: boolean
}
export interface FactorDTO { raw: number; normalized: number; weight: number; contribution: number }
export interface RankedRecommendationDTO {
  rank: number; event_id: string; title: string; score: number; factors: Record<string, FactorDTO>
  scoring_evidence: Record<string, unknown>
  simulation: {
    event_id: string; target: { role: string; grade: string }; simulated_skills_after: Record<string, number>
    target_skill_impact: Array<{ skill_id: string; current: number; required: number; after: number; critical: boolean; gap_before: number; gap_after: number; useful_gain: number }>
    skill_impact: Array<{ skill_id: string; before: number; after: number; actual_gain: number; advertised_gain: number; max_level: number }>
    readiness_before: number | null; readiness_after: number | null; readiness_delta: number | null
    total_gap_reduction: number; critical_gap_reduction: number; critical_requirements_closed: string[]
    [key: string]: unknown
  }
  evidence: {
    audience_match: 'current_role' | 'target_role' | 'both' | null
    current_role: string; target_role: string | null; target_grade: string | null; attained_grade: string
    availability: { next_session_date: string | null; days_until_next_session: number | null; self_paced: boolean; available: boolean; [key: string]: unknown }
    skills_are_estimated: boolean; [key: string]: unknown
  }
  history_signals: { compatibility: number; feedback_signal: number; evidence: Record<string, unknown>; [key: string]: unknown }
  explanation?: ExplanationDTO
}
export interface RecommendationResultDTO {
  employee_id: string; as_of: string; version: number; status: RecommendationStatus; target: TargetDTO | null
  career_readiness: ReadinessDTO | null; skill_gaps: SkillGapDTO[]
  career_state: {
    employee_id: string; as_of: string; status: string; target: TargetDTO | null
    career_readiness: ReadinessDTO | null; skill_gaps: SkillGapDTO[]; skills_reconstruction: ReconstructionDTO
  }
  candidate_count: number; recommendation_count: number; recommendations: RankedRecommendationDTO[]
  blocked_summary: Record<string, unknown> | null; explanation_summary?: ExplanationDTO
  explanation_meta?: { language: Language; provider_status: string; [key: string]: unknown }
}
export interface CompletionReceipt {
  activity: ActivityRecordDTO; effective_skills: Record<string, number>
  skill_changes: Array<{ skill_id: string; before: number; after: number; gain: number; event_gain: number; max_level: number }>
  version: number; replayed: boolean
}
export interface HRAnalyticsDTO {
  employee_count: number; gap_basis: string
  common_skill_gaps: Array<{ skill_id: string; skill_name: string; category: string; employee_count: number; total_levels_missing: number; critical_employee_count: number }>
  employees_without_next_step: { available: boolean; count: number | null; evaluated_count: number; pending_count: number; complete: boolean }
  activity_participation: Record<ActivityStatus, number>
  participation_summary: { total_records: number; participating_employees: number; voluntary: Record<ActivityStatus, number>; mandatory: Record<ActivityStatus, number> }
}
