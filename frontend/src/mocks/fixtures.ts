import type { Activity, ActivityHistory, CareerOverview, Employee, HRAnalytics, SkillGap } from '../types/domain'

// Synthetic demonstration records, not official employee or dataset content.
// Every score, gap, target, ordering and impact below is a fixed response fixture.
export const employees: Employee[] = [
  {
    id: 'demo-aigerim', name: 'Aigerim Sapar', role: 'Backend Engineer', grade: 'Middle',
    department: 'Digital Products', preferredLanguage: 'en',
    tenureLabel: '2 years, 4 months', careerGoal: 'Grow into a Senior Backend Engineer role',
    skills: [
      { id: 'system-design', name: 'System Design', current: 2, scaleMax: 5 },
      { id: 'api-design', name: 'API Design', current: 3, scaleMax: 5 },
      { id: 'technical-communication', name: 'Technical Communication', current: 3, scaleMax: 5 },
    ],
  },
  {
    id: 'demo-daniyar', name: 'Daniyar Omar', role: 'Data Analyst', grade: 'Middle',
    department: 'Data & Insights', preferredLanguage: 'kk',
    tenureLabel: '1 year, 8 months', careerGoal: 'Move from data insights into product leadership',
    skills: [{ id: 'product-discovery', name: 'Product Discovery', current: 2, scaleMax: 5 }],
  },
  {
    id: 'demo-madina', name: 'Madina Serik', role: 'Platform Engineer', grade: 'Lead',
    department: 'Technology', preferredLanguage: 'ru', skills: [],
  },
]

export const activities: Activity[] = [
  { id: 'demo-system-design', title: 'Designing High-Load Systems', type: 'Workshop', durationMinutes: 120 },
  { id: 'demo-api-design', title: 'Build APIs That Scale', type: 'Course', durationMinutes: 90 },
  { id: 'demo-communication', title: 'Communicating Technical Decisions', type: 'Mentoring', durationMinutes: 45 },
]

export const careerOverviews: Record<string, CareerOverview> = {
  'demo-aigerim': {
    employeeId: 'demo-aigerim', target: { role: 'Backend Engineer', grade: 'Senior' },
    trajectory: { kind: 'promotion', positions: [
      { role: 'Backend Engineer', grade: 'Junior', state: 'past' },
      { role: 'Backend Engineer', grade: 'Middle', state: 'current' },
      { role: 'Backend Engineer', grade: 'Senior', state: 'target' },
      { role: 'Backend Engineer', grade: 'Lead', state: 'future' },
    ] },
    readiness: { current: 0.67 },
    skillGaps: [
      { id: 'system-design', name: 'System Design', current: 2, scaleMax: 5, required: 4, gap: 2, critical: true },
      { id: 'api-design', name: 'API Design', current: 3, scaleMax: 5, required: 4, gap: 1, critical: false },
      { id: 'technical-communication', name: 'Technical Communication', current: 3, scaleMax: 5, required: 4, gap: 1, critical: false },
    ],
    recommendations: [{
      eventId: 'demo-system-design', title: 'Designing High-Load Systems', type: 'Workshop', durationMinutes: 120,
      careerImpact: 'High', score: 0.87,
      skillImpact: [{ skillId: 'system-design', name: 'System Design', current: 2, after: 3, required: 4, critical: true }],
      readinessBefore: 0.67, readinessAfter: 0.79,
      explanation: {
        text: 'This workshop addresses the System Design gap for the Senior Backend Engineer target.',
        factors: [{ id: 'critical-skill-impact', label: 'Critical skill impact', value: 1 }],
      },
    }, {
      eventId: 'demo-api-design', title: 'Build APIs That Scale', type: 'Course', durationMinutes: 90,
      careerImpact: 'High', score: 0.81,
      skillImpact: [{ skillId: 'api-design', name: 'API Design', current: 3, after: 4, required: 4, critical: false }],
      readinessBefore: 0.67, readinessAfter: 0.73,
      explanation: { text: 'Practice designing resilient APIs for the requirements of your target role.', factors: [] },
    }, {
      eventId: 'demo-communication', title: 'Communicating Technical Decisions', type: 'Mentoring', durationMinutes: 45,
      careerImpact: 'Moderate', score: 0.72,
      skillImpact: [{ skillId: 'technical-communication', name: 'Technical Communication', current: 3, after: 4, required: 4, critical: false }],
      readinessBefore: 0.67, readinessAfter: 0.71,
      explanation: { text: null, factors: [] },
    }],
  },
  'demo-daniyar': {
    employeeId: 'demo-daniyar', target: { role: 'Product Manager', grade: 'Middle' },
    trajectory: { kind: 'transition', positions: [
      { role: 'Data Analyst', grade: 'Middle', state: 'current' },
      { role: 'Product Analyst', grade: 'Middle', state: 'intermediate' },
      { role: 'Product Manager', grade: 'Middle', state: 'target' },
    ] },
    readiness: { current: 0.42 },
    skillGaps: [{ id: 'product-discovery', name: 'Product Discovery', current: 2, scaleMax: 5, required: 4, gap: 2, critical: true }],
    recommendations: [],
  },
  'demo-madina': {
    employeeId: 'demo-madina', target: null, trajectory: null, readiness: null, skillGaps: [], recommendations: [],
  },
}

// Fixed QA responses: optional/mixed scales are not inferred from the skill values.
export const skillScaleExamples: SkillGap[] = [
  { id: 'scale-100', name: 'System Design', current: 35, required: 80, gap: 45, critical: true, scaleMax: 100 },
  { id: 'scale-10', name: 'API Design', current: 6.5, required: 8, gap: 1.5, critical: false, scaleMax: 10 },
  { id: 'scale-unknown', name: 'Technical Communication', current: 2, required: 4, gap: 2, critical: false },
]

export const employeeHistories: Record<string, ActivityHistory[]> = {
  'demo-aigerim': [], 'demo-daniyar': [], 'demo-madina': [],
}

export const hrAnalytics: HRAnalytics = {
  employee_count: 3, gap_basis: 'effective_skills_against_current_role_and_grade', common_skill_gaps: [],
  employees_without_next_step: { available: false, count: null, evaluated_count: 0, pending_count: 3, complete: false },
  activity_participation: { completed: 0, in_progress: 0, dropped: 0, no_show: 0, declined: 0, overdue: 0 },
  participation_summary: { total_records: 0, participating_employees: 0,
    voluntary: { completed: 0, in_progress: 0, dropped: 0, no_show: 0, declined: 0, overdue: 0 },
    mandatory: { completed: 0, in_progress: 0, dropped: 0, no_show: 0, declined: 0, overdue: 0 } },
}
