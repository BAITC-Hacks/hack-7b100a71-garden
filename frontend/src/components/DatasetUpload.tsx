import { useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { ApiError } from '../types/api'
import type { DatasetFiles, DatasetMode, DatasetUploadResult, DatasetValidationResult } from '../types/domain'
import { Button } from './UI'

const sections: Array<{ field: keyof DatasetFiles; label: string; accept: string }> = [
  { field: 'employees_file', label: 'employees.json', accept: '.json,application/json' },
  { field: 'skills_file', label: 'skills.json', accept: '.json,application/json' },
  { field: 'events_file', label: 'events.json', accept: '.json,application/json' },
  { field: 'activity_history_file', label: 'activity_history.csv', accept: '.csv,text/csv' },
]

function DatasetCounts({ counts }: { counts: Record<string, number> }) {
  return <dl className="dataset-counts">{Object.entries(counts).map(([key, count]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{count}</dd></div>)}</dl>
}

export function DatasetUpload() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<DatasetMode>('append')
  const [files, setFiles] = useState<DatasetFiles>({})
  const [validation, setValidation] = useState<DatasetValidationResult | null>(null)
  const [uploaded, setUploaded] = useState<DatasetUploadResult | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [pending, setPending] = useState<'validate' | 'upload' | null>(null)
  const hasFiles = Object.values(files).some(Boolean)
  const hasAllFiles = sections.every(({ field }) => files[field])
  const selectionComplete = mode === 'replace' ? hasAllFiles : hasFiles

  const resetResult = () => { setValidation(null); setUploaded(null); setError(null) }
  async function validate(event: FormEvent) {
    event.preventDefault()
    if (!selectionComplete || pending) return
    resetResult()
    setPending('validate')
    try { setValidation(await api.validateDataset(files, mode)) }
    catch (cause) { setError(cause instanceof Error ? cause : new Error('Dataset validation failed.')) }
    finally { setPending(null) }
  }
  async function upload() {
    if (!validation?.valid || pending) return
    setPending('upload'); setError(null); setUploaded(null)
    try {
      const result = await api.uploadDataset(files, mode)
      setUploaded(result); setValidation(null)
      await queryClient.invalidateQueries()
    } catch (cause) { setError(cause instanceof Error ? cause : new Error('Dataset upload failed.')) }
    finally { setPending(null) }
  }

  return <section className="surface hr-section dataset-upload" aria-labelledby="dataset-upload-title">
    <h2 id="dataset-upload-title">Validate & upload dataset</h2>
    <p className="hr-help">Validation previews the resulting dataset. Upload validates the files again before applying them atomically.</p>
    <form onSubmit={(event) => void validate(event)}>
      <fieldset disabled={pending !== null}>
        <legend>Import mode</legend>
        <div className="dataset-mode-options">{(['append', 'replace'] as const).map((value) => <label key={value}>
          <input type="radio" name="dataset-mode" value={value} checked={mode === value} onChange={() => { setMode(value); resetResult() }} />
          <span>{value === 'append' ? 'Append employees / history' : 'Replace complete dataset'}</span>
        </label>)}</div>
        <p className="hr-help">{mode === 'append'
          ? 'Add new employees or history. Existing IDs are not overwritten; any supplied catalog must match the active dataset.'
          : 'Replace the active dataset and clear its previous completion receipts. All four files are required.'}</p>
        <div className="dataset-files">{sections.map(({ field, label, accept }) => <label key={field} htmlFor={`dataset-${field}`}>
          <span>{label}{mode === 'replace' ? ' · required' : ''}</span>
          <input id={`dataset-${field}`} type="file" accept={accept} onChange={(event) => {
            setFiles((current) => ({ ...current, [field]: event.target.files?.[0] }))
            resetResult()
          }} />
        </label>)}</div>
      </fieldset>
      <div className="dataset-actions">
        <Button type="submit" disabled={!selectionComplete || pending !== null}>{pending === 'validate' ? 'Validating…' : 'Validate files'}</Button>
        <Button disabled={!validation?.valid || pending !== null} onClick={() => void upload()}>{pending === 'upload' ? 'Uploading…' : mode === 'replace' ? 'Upload replacement' : 'Upload validated files'}</Button>
      </div>
    </form>
    {pending && <p className="hr-help" role="status">{pending === 'upload' ? 'Applying dataset and refreshing views…' : 'Validating against the active dataset…'}</p>}
    {error && <div className="dataset-result dataset-result-error" role="alert">
      <h3>{error instanceof ApiError ? error.backendCode ?? error.code : 'Request failed'}</h3><p>{error.message}</p>
      {error instanceof ApiError && error.status && <p>HTTP {error.status}</p>}
      {error instanceof ApiError && error.details.length > 0 && <pre>{JSON.stringify(error.details, null, 2)}</pre>}
    </div>}
    {validation && <div className={`dataset-result ${validation.valid ? '' : 'dataset-result-error'}`} role={validation.valid ? 'status' : 'alert'}>
      <h3>{validation.valid ? 'Validation passed' : 'Validation failed'}</h3>
      <p>{validation.mode} · Checked against version {validation.version}. No data changed during validation.</p>
      {validation.valid && <><p>Review the resulting counts before upload:</p><DatasetCounts counts={validation.counts} /></>}
      {validation.errors.length > 0 && <ul>{validation.errors.map((issue, index) => <li key={`${issue.code}-${issue.location}-${index}`}>
        <strong>{issue.location}</strong>: {issue.message} <span>({issue.code})</span>
      </li>)}</ul>}
    </div>}
    {uploaded && <div className="dataset-result" role="status"><h3>Dataset uploaded</h3>
      <p>{uploaded.mode} · Active version {uploaded.version}. Employee, career, recommendation and HR views have been refreshed.</p>
      <DatasetCounts counts={uploaded.counts} />
    </div>}
  </section>
}
