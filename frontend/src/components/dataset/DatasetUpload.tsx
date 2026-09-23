import { useEffect, useRef } from 'react'
import { copy } from '../../i18n/en'
import { useDatasetUpload } from '../../hooks/useDatasetUpload'
import { isSupportedDatasetFile } from '../../services/datasetConfig'
import { isDatasetBusy, isDatasetImported, type DatasetUploadState } from '../../types/dataset'
import { Button } from '../UI'
import { DatasetFiles } from './DatasetFiles'
import { DatasetValidationDetails } from './DatasetValidationDetails'

function feedbackFor(state: DatasetUploadState) {
  switch (state.phase) {
    case 'validating': return { title: copy.dataset.validating, description: copy.dataset.validatingDescription }
    case 'validated': return { title: copy.dataset.validated, description: copy.dataset.validatedDescription }
    case 'invalid': return { title: copy.dataset.invalid, description: copy.dataset.invalidDescription, error: true }
    case 'incomplete': return { title: copy.dataset.incomplete, description: copy.dataset.incompleteDescription, error: true }
    case 'validation-error': return { title: copy.dataset.validationError, description: state.error || copy.dataset.validationErrorDescription, error: true }
    case 'importing': return { title: copy.dataset.importing, description: copy.dataset.importingDescription }
    case 'import-error': return { title: copy.dataset.importError, description: state.error || copy.dataset.importErrorDescription, error: true }
    case 'refreshing': return { title: copy.dataset.imported, description: copy.dataset.refreshing }
    case 'refresh-error': return { title: copy.dataset.refreshError, description: copy.dataset.refreshErrorDescription, error: true }
    case 'success': return { title: copy.dataset.imported, description: copy.dataset.refreshed }
    default: return null
  }
}

export function DatasetUpload() {
  const upload = useDatasetUpload()
  const { state } = upload
  const busy = isDatasetBusy(state)
  const imported = isDatasetImported(state)
  const feedback = feedbackFor(state)
  const feedbackRef = useRef<HTMLDivElement>(null)
  const previousPhase = useRef(state.phase)
  useEffect(() => {
    if (previousPhase.current !== state.phase && !isDatasetBusy(state) && state.phase !== 'idle') feedbackRef.current?.focus()
    previousPhase.current = state.phase
  }, [state])
  const canImport = state.phase === 'validated' || state.phase === 'importing' || state.phase === 'import-error'
  const step = imported || canImport ? 2 : state.files.length ? 1 : 0

  return <div className="dataset-workspace">
    <ol className="dataset-steps" aria-label={copy.dataset.stepLabel}>{copy.dataset.steps.map((label, index) =>
      <li key={label} aria-current={index === step ? 'step' : undefined} className={index < step ? 'is-complete' : ''}><span aria-hidden="true">{index + 1}</span>{label}</li>)}</ol>
    <DatasetFiles files={state.files} locked={busy || imported} onSelect={upload.selectFiles} onRemove={upload.removeFile} onClear={upload.reset} />
    {feedback && <section className="surface dataset-results" aria-label={copy.dataset.resultTitle}>
      <div ref={feedbackRef} tabIndex={-1} className={`dataset-feedback ${feedback.error ? 'is-error' : ''}`}
        role={feedback.error ? 'alert' : 'status'} aria-live={feedback.error ? 'assertive' : 'polite'} aria-busy={busy}>
        <span className={`dataset-feedback-mark ${busy ? 'is-busy' : ''}`} aria-hidden="true">{busy ? '…' : feedback.error ? '!' : '✓'}</span>
        <div><h2>{feedback.title}</h2><p>{feedback.description}</p></div>
      </div>
      {state.result && <DatasetValidationDetails key={state.result.validationId ?? state.phase} result={state.result} />}
    </section>}
    <div className="dataset-actions">
      {!imported && <Button className={canImport ? 'dataset-secondary' : ''} disabled={busy || !state.files.length || !state.files.every(isSupportedDatasetFile)} onClick={() => void upload.validate()}>
        {state.phase === 'validating' ? copy.dataset.validating : state.phase === 'idle' ? copy.dataset.validate : copy.dataset.validateAgain}
      </Button>}
      {canImport && <Button disabled={busy} onClick={() => void upload.importDataset()}>{state.phase === 'importing' ? copy.dataset.importing : state.phase === 'import-error' ? copy.dataset.retryImport : copy.dataset.import}</Button>}
      {state.phase === 'refresh-error' && <Button onClick={() => void upload.retryRefresh()}>{copy.dataset.retryRefresh}</Button>}
      {imported && <Button className="dataset-secondary" disabled={busy || state.phase === 'refresh-error'} onClick={upload.reset}>{copy.dataset.another}</Button>}
    </div>
  </div>
}
