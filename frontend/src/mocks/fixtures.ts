import type { Activity, ActivityHistory, CareerOverview, Employee, HRAnalytics } from '../types/domain'

// Synthetic demonstration records, not official employee or dataset content.
// Every score, gap, target, ordering and impact below is a fixed response fixture.
export const employees: Employee[] = [
  {
    id: 'demo-aigerim', name: 'Aigerim Sapar', role: 'Backend Engineer', grade: 'Middle',
    department: 'Digital Products', preferredLanguage: 'en',
    skills: [
      { id: 'system-design', name: 'System Design', current: 2, scaleMax: 5 },
      { id: 'api-design', name: 'API Design', current: 3, scaleMax: 5 },
    ],
  },
  {
    id: 'demo-daniyar', name: 'Daniyar Omar', role: 'Data Analyst', grade: 'Middle',
    department: 'Data & Insights', preferredLanguage: 'kk',
    skills: [{ id: 'product-discovery', name: 'Product Discovery', current: 2, scaleMax: 5 }],
  },
  {
    id: 'demo-madina', name: 'Madina Serik', role: 'Platform Engineer', grade: 'Lead',
    department: 'Technology', preferredLanguage: 'ru', skills: [],
  },
]

export const activities: Activity[] = [
  { id: 'demo-system-design', title: 'Designing High-Load Systems', type: 'Workshop', durationMinutes: 120 },
]

export const careerOverviews: Record<string, CareerOverview> = {
  'demo-aigerim': {
    employeeId: 'demo-aigerim', target: { role: 'Backend Engineer', grade: 'Senior' },
    trajectory: { kind: 'promotion', positions: [
      { role: 'Backend Engineer', grade: 'Middle', state: 'current' },
      { role: 'Backend Engineer', grade: 'Senior', state: 'target' },
    ] },
    readiness: { current: 0.67 },
    skillGaps: [
      { id: 'system-design', name: 'System Design', current: 2, scaleMax: 5, required: 4, gap: 2, critical: true },
      { id: 'api-design', name: 'API Design', current: 3, scaleMax: 5, required: 4, gap: 1, critical: false },
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
    }],
  },
  'demo-daniyar': {
    employeeId: 'demo-daniyar', target: { role: 'Product Manager', grade: 'Middle' },
    trajectory: { kind: 'transition', positions: [
      { role: 'Data Analyst', grade: 'Middle', state: 'current' },
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

export const employeeHistories: Record<string, ActivityHistory[]> = {
  'demo-aigerim': [], 'demo-daniyar': [], 'demo-madina': [],
}

export const hrAnalytics: HRAnalytics = {
  totalEmployees: 3, employeesInDevelopment: 0, withoutNextStep: 2, participationRate: 0,
  commonSkillGaps: [
    { skillId: 'system-design', name: 'System Design', employeeCount: 1 },
    { skillId: 'api-design', name: 'API Design', employeeCount: 1 },
    { skillId: 'product-discovery', name: 'Product Discovery', employeeCount: 1 },
  ],
  activityStatuses: [],
}
