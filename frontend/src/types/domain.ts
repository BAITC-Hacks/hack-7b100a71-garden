// Frontend view models. Business values are supplied by an API adapter.
export type Language = 'kk' | 'ru' | 'en'

export interface Skill {
  id: string
  name: string
  current: number
  scaleMax?: number | null
}

export interface Employee {
  snapshotVersion?: number
  id: string
  name: string
  role: string
  grade: string
  department: string
  tenureLabel?: string | null
  careerGoal?: string | null
  preferredLanguage: Language
  skills: Skill[]
}

export interface CareerTarget { role: string; grade: string }
export interface CareerPosition extends CareerTarget {
  state: 'past' | 'current' | 'intermediate' | 'target' | 'future'
}
export interface CareerTrajectory {
  kind: 'promotion' | 'transition'
  // Ordered and labelled by the adapter; never infer progression from grades.
  positions: CareerPosition[]
}
export interface CareerReadiness {
  // Agreed frontend unit: 0–1. Formatting it as a percentage is presentation only.
  current: number
}
export interface SkillGap extends Omit<Skill, 'current'> {
  current?: number | null
  required?: number | null
  gap?: number | null
  critical?: boolean | null
}
export type ActivityStatus = 'completed' | 'in_progress' | 'no_show' | 'dropped' | 'declined' | 'overdue'
export interface Activity { id: string; title: string; type: string; durationMinutes: number }
export interface ActivityHistory { id: string; eventId: string; status: ActivityStatus; updatedAt?: string; enrolledOn?: string; completedOn?: string | null }
export interface RecommendationFactor { id: string; label: string; value?: number | null; raw?: number; normalized?: number; weight?: number; contribution?: number }
export interface RecommendationExplanation {
  text?: string | null
  factors?: RecommendationFactor[] | null
  language?: Language
  source?: string
  facts?: Array<{ id: string; code: string; values: Record<string, unknown>; evidencePaths: string[] }>
}
export interface RecommendationSkillImpact {
  skillId: string
  name: string
  current?: number | null
  after?: number | null
  required?: number | null
  critical?: boolean | null
  // Optional supplied evidence. Never derive gain by subtracting skill levels.
  gain?: number | null
}
export interface Recommendation {
  eventId: string
  title: string
  type?: string | null
  durationMinutes?: number | null
  careerImpact?: string | null
  score?: number | null
  skillImpact?: RecommendationSkillImpact[] | null
  readinessBefore?: number | null
  readinessAfter?: number | null
  explanation?: RecommendationExplanation | null
  supportingEvidence?: Array<{ id: string; label: string; values: Record<string, unknown> }>
}
export interface CareerOverview {
  snapshotVersion?: number
  status?: string
  summary?: string
  skillsEstimated?: boolean
  warnings?: Array<{ code: string; message: string; recordIds?: string[] }>
  employeeId: string
  target: CareerTarget | null
  trajectory: CareerTrajectory | null
  readiness: CareerReadiness | null
  skillGaps: SkillGap[]
  recommendations: Recommendation[]
}
export interface HRAnalytics {
  snapshotVersion?: number
  gapBasis?: string
  participatingEmployees?: number
  participationRecordCount?: number
  nextStepCoverage?: { available?: boolean; count?: number | null; evaluatedCount?: number; pendingCount?: number; complete?: boolean }
  // Omitted/null metrics are unavailable, not zero. All aggregates belong to the adapter.
  totalEmployees?: number | null
  employeesInDevelopment?: number | null
  withoutNextStep?: number | null
  // Presentation unit: 0–1. The adapter owns the definition and denominator.
  participationRate?: number | null
  commonSkillGaps?: Array<{ skillId: string; name: string; employeeCount?: number | null }> | null
  // Provisional optional view model until the live activity-analytics contract is agreed.
  activityParticipation?: Array<{ activityId: string; title: string; participantCount?: number | null }> | null
  activityStatuses?: Array<{ status: ActivityStatus; count?: number | null }> | null
}
export interface DatasetIssue {
  code?: string | null
  location?: string | null
  file?: string | null
  row?: number | null
  record?: string | number | null
  field?: string | null
  message?: string | null
}
export interface DatasetValidationResult {
  // Partial responses never authorize an import. The adapter owns validation.
  valid?: boolean | null
  // Frontend-local receipt binding the checked selection; not a backend token.
  validationId?: string | null
  mode?: 'append' | 'replace'
  version?: number
  errors?: DatasetIssue[] | null
  warnings?: DatasetIssue[] | null
  // Optional display fields, pending the live dataset response contract.
  summary?: {
    employees?: number | null
    skills?: number | null
    roleProfiles?: number | null
    events?: number | null
    activityHistory?: number | null
    recordsProcessed?: number | null
  } | null
}
