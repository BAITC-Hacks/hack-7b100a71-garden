import type { DatasetFileRole, DatasetMode } from '../types/dataset'

// Confirmed multipart contract. These checks concern file selection only;
// record parsing, schema validation and referential integrity belong to the server.
export const datasetFileExtensions = ['.json', '.csv'] as const
export const datasetFileAccept = datasetFileExtensions.join(',')
export function isSupportedDatasetFile(file: File) {
  return datasetFileExtensions.some((extension) => file.name.toLowerCase().endsWith(extension))
}

export const datasetFileRoles: DatasetFileRole[] = ['employees', 'activityHistory', 'events', 'skills']
export function suggestDatasetRole(file: File): DatasetFileRole | '' {
  const name = file.name.toLowerCase()
  if (name.includes('history')) return 'activityHistory'
  if (name.includes('employee')) return 'employees'
  if (name.includes('event')) return 'events'
  if (name.includes('skill')) return 'skills'
  return ''
}
export function isDatasetSelectionReady(files: File[], fileRoles: Array<DatasetFileRole | ''>, mode: DatasetMode): boolean {
  if (!files.length || files.length !== fileRoles.length || !files.every(isSupportedDatasetFile)) return false
  if (fileRoles.some((role) => !role) || new Set(fileRoles).size !== fileRoles.length) return false
  return mode === 'replace' ? datasetFileRoles.every((role) => fileRoles.includes(role))
    : fileRoles.every((role) => role === 'employees' || role === 'activityHistory')
}
