import type { DatasetValidationResult } from '../types/domain'

// Preset demonstration results. Never read or assess the selected files.
export const datasetValidationSuccess: DatasetValidationResult = {
  valid: true, validationId: 'demo-validation', errors: [],
  summary: { employees: 3, skills: 3, events: 3, activityHistory: 0, recordsProcessed: 9 },
  warnings: [{ file: 'activity_history.csv', message: 'No activity history records were provided in this sample response.' }],
}
export const datasetValidationFailure: DatasetValidationResult = {
  valid: false, validationId: null,
  errors: [
    { file: 'employees.json', record: 'employee-017', field: 'grade', message: 'The supplied grade is not supported.' },
    { file: 'activity_history.csv', row: 8, field: 'employee_id', record: 'history-004', message: 'The referenced employee could not be found.' },
    { file: 'activity_history.csv', row: 12, field: 'event_id', message: 'The referenced development event could not be found.' },
    { file: 'employees.json', record: 'employee-003', field: 'id', message: 'This ID is used by more than one employee record.' },
    { file: 'events.csv', row: 4, field: 'title', message: 'A required title is missing.' },
    { file: 'skills.json', message: 'The file could not be read as JSON. Check its formatting and try again.' },
  ],
}
export const datasetValidationPartial: DatasetValidationResult = {
  valid: true, validationId: 'demo-validation', summary: { employees: 0, skills: null },
}
export const datasetValidationIncomplete: DatasetValidationResult = { valid: true, validationId: null }
export const datasetValidationEmpty: DatasetValidationResult = {}
// Fixed QA list, repeated for pagination/long-message layout only; no file inspection.
export const datasetValidationLong: DatasetValidationResult = {
  valid: false, errors: Array.from({ length: 35 }, (_, index) => ({
    file: 'organization-development-history-for-the-current-reporting-period.csv', row: index + 2,
    field: 'employee_id', record: `sample-record-${index + 1}`,
    message: 'The employee reference in this sample response could not be resolved. Check that the employee is included in the supplied dataset, then select the corrected files and validate again.',
  })),
}
