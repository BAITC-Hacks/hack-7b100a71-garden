import { useEffect, useRef } from 'react'
import { copy } from '../../i18n/en'
import { useDatasetUpload } from '../../hooks/useDatasetUpload'
import { isDatasetSelectionReady } from '../../services/datasetConfig'
import { isDatasetBusy, isDatasetImported, isDatasetUncertain, type DatasetUploadState } from '../../types/dataset'
import { datasetCopy } from '../../i18n/dataset'
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
    case 'import-error': return { title: datasetCopy.rejected, description: state.error || datasetCopy.rejectedHelp, error: true }
    case 'import-uncertain': return { title: datasetCopy.uncertain, description: state.error || datasetCopy.uncertainHelp, error: true }
    case 'checking-import': return { title: datasetCopy.uncertain, description: datasetCopy.checking }
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
  const uncertain = isDatasetUncertain(state)
  const feedback = feedbackFor(state)
  const feedbackRef = useRef<HTMLDivElement>(null)
  const previousPhase = useRef(state.phase)
  useEffect(() => {
    if (previousPhase.current !== state.phase && !isDatasetBusy(state) && state.phase !== 'idle') feedbackRef.current?.focus()
    previousPhase.current = state.phase
  }, [state])
  const canImport = state.phase === 'validated' || state.phase === 'importing'
  const step = imported || canImport ? 2 : state.files.length ? 1 : 0

  return <div className="dataset-workspace">
    <ol className="dataset-steps" aria-label={copy.dataset.stepLabel}>{copy.dataset.steps.map((label, index) =>
      <li key={label} aria-current={index === step ? 'step' : undefined} className={index < step ? 'is-complete' : ''}><span aria-hidden="true">{index + 1}</span>{label}</li>)}</ol>
    <DatasetFiles files={state.files} locked={busy || imported || uncertain} mode={state.mode} fileRoles={state.fileRoles} onMode={upload.selectMode} onRole={upload.selectRole}
      onSelect={upload.selectFiles} onRemove={upload.removeFile} onClear={upload.reset} />
    {feedback && <section className="surface dataset-results" aria-label={copy.dataset.resultTitle}>
      <div ref={feedbackRef} tabIndex={-1} className={`dataset-feedback ${feedback.error ? 'is-error' : ''}`}
        role={feedback.error ? 'alert' : 'status'} aria-live={feedback.error ? 'assertive' : 'polite'} aria-busy={busy}>
        <span className={`dataset-feedback-mark ${busy ? 'is-busy' : ''}`} aria-hidden="true">{busy ? '…' : feedback.error ? '!' : '✓'}</span>
        <div><h2>{feedback.title}</h2><p>{feedback.description}</p></div>
      </div>
      {state.result && <DatasetValidationDetails key={state.result.validationId ?? state.phase} result={state.result} />}
    </section>}
    <div className="dataset-actions">
      {!imported && !uncertain && <Button className={canImport ? 'dataset-secondary' : ''} disabled={busy || !isDatasetSelectionReady(state.files, state.fileRoles, state.mode)} onClick={() => void upload.validate()}>
        {state.phase === 'validating' ? copy.dataset.validating : state.phase === 'idle' ? copy.dataset.validate : copy.dataset.validateAgain}
      </Button>}
      {canImport && <Button disabled={busy || Boolean(upload.importBlockedReason)} aria-describedby={upload.importBlockedReason ? 'dataset-operation-blocked' : undefined} onClick={() => void upload.importDataset()}>{state.phase === 'importing' ? copy.dataset.importing : state.mode === 'replace' ? datasetCopy.replaceAction : copy.dataset.import}</Button>}
      {uncertain && <Button disabled={busy} onClick={() => void upload.checkImport()}>{busy ? datasetCopy.checking : datasetCopy.check}</Button>}
      {state.phase === 'refresh-error' && <Button disabled={Boolean(upload.importBlockedReason)} onClick={() => void upload.retryRefresh()}>{copy.dataset.retryRefresh}</Button>}
      {imported && <Button className="dataset-secondary" disabled={busy || state.phase === 'refresh-error'} onClick={upload.reset}>{copy.dataset.another}</Button>}
    </div>
    {upload.importBlockedReason && <p id="dataset-operation-blocked" role="status">{upload.importBlockedReason}</p>}
  </div>
}
