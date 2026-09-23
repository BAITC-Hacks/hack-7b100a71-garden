// Frontend view models. Business values are supplied by an API adapter.
import type { ActivityRecordDTO, EmployeeDTO, ExplanationDTO, HRAnalyticsDTO, RankedRecommendationDTO, RecommendationResultDTO, RecommendationStatus, ReconstructionDTO } from './transport'
export type { CompletionReceipt, RecommendationStatus } from './transport'
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
  version?: number
  asOf?: string
  workFormat?: string
  tenureMonths?: number
  lastReviewDate?: string
  assessmentSkills?: Record<string, number>
  raw?: EmployeeDTO
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
export interface Activity { id: string; title: string; type: string; durationMinutes: number; format?: string }
export interface ActivityHistory {
  id: string; eventId: string; status: ActivityStatus; updatedAt: string
  title?: string; date?: string; completedAt?: string | null; completedOn?: string | null
  completionPct?: number; score?: number | null; feedbackRating?: number | null; assignedBy?: string
  raw?: ActivityRecordDTO
}
export interface RecommendationFactor { id: string; label: string; value: number }
export interface RecommendationExplanation { text: string | null; factors: RecommendationFactor[]; language?: Language; source?: 'deterministic' | 'openai' }
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
  rank?: number
  format?: string
  raw?: RankedRecommendationDTO
}
export interface CareerOverview {
  employeeId: string
  target: CareerTarget | null
  trajectory: CareerTrajectory | null
  readiness: CareerReadiness | null
  skillGaps: SkillGap[]
  recommendations: Recommendation[]
  version?: number
  asOf?: string
  status?: RecommendationStatus
  targetRequirements?: SkillGap[]
  explanationSummary?: ExplanationDTO
  reconstruction?: ReconstructionDTO
  skillsEstimated?: boolean
  warnings?: string[]
  raw?: RecommendationResultDTO
}
export interface HRAnalytics extends HRAnalyticsDTO { version?: number; asOf?: string }
export type DatasetMode = 'append' | 'replace'
export type DatasetFiles = Partial<Record<'employees_file' | 'activity_history_file' | 'events_file' | 'skills_file', File>>
export interface DatasetValidationResult {
  valid: boolean
  counts: Record<string, number>
  errors: Array<{ code: string; location: string; message: string }>
  mode: DatasetMode
  version: number
}
export interface DatasetUploadResult { uploaded: boolean; counts: Record<string, number>; mode: DatasetMode; version: number }
