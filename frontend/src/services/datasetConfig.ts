// Supported by the mock upload contract. Confirm formats with the live adapter
// before enabling real endpoints. This is file-selection UX, not schema validation.
export const datasetFileExtensions = ['.json', '.csv'] as const
export const datasetFileAccept = datasetFileExtensions.join(',')
export function isSupportedDatasetFile(file: File) {
  return datasetFileExtensions.some((extension) => file.name.toLowerCase().endsWith(extension))
}
