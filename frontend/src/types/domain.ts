// Frontend view models. Business values are supplied by an API adapter.
export type Language = 'kk' | 'ru' | 'en'

export interface Skill {
  id: string
  name: string
  current: number
  scaleMax?: number | null
}

export interface Employee {
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
export interface SkillGap extends Skill {
  required: number
  gap: number
  critical: boolean
}
export type ActivityStatus = 'completed' | 'in_progress' | 'no_show' | 'dropped' | 'declined' | 'overdue'
export interface Activity { id: string; title: string; type: string; durationMinutes: number }
export interface ActivityHistory { id: string; eventId: string; status: ActivityStatus; updatedAt: string }
export interface RecommendationFactor { id: string; label: string; value: number }
export interface RecommendationExplanation { text: string | null; factors: RecommendationFactor[] }
export interface Recommendation {
  eventId: string
  title: string
  type: string
  durationMinutes: number
  careerImpact: string | null
  score: number | null
  skillImpact: Array<{ skillId: string; name: string; current: number; after: number; required: number; critical: boolean }>
  readinessBefore: number | null
  readinessAfter: number | null
  explanation: RecommendationExplanation
}
export interface CareerOverview {
  employeeId: string
  target: CareerTarget | null
  trajectory: CareerTrajectory | null
  readiness: CareerReadiness | null
  skillGaps: SkillGap[]
  recommendations: Recommendation[]
}
export interface HRAnalytics {
  totalEmployees: number
  employeesInDevelopment: number
  withoutNextStep: number
  participationRate: number
  commonSkillGaps: Array<{ skillId: string; name: string; employeeCount: number }>
  activityStatuses: Array<{ status: ActivityStatus; count: number }>
}
export interface DatasetValidationResult {
  valid: boolean
  validationId: string | null
  errors: Array<{ file: string; row: number | null; field: string | null; message: string }>
}
