import { useState, type DragEvent } from 'react'
import { copy } from '../../i18n/en'
import { datasetFileAccept, isSupportedDatasetFile } from '../../services/datasetConfig'
import { Button } from '../UI'
import { Icon } from '../Icon'

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(bytes / 1024)} KB`
  return `${new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024))} MB`
}

export function DatasetFiles({ files, locked, onSelect, onRemove, onClear }: {
  files: File[]; locked: boolean; onSelect: (files: File[]) => void; onRemove: (index: number) => void; onClear: () => void
}) {
  const [dragging, setDragging] = useState(false)
  function drop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    if (!locked && event.dataTransfer.files.length) onSelect(Array.from(event.dataTransfer.files))
  }
  return <section className="surface dataset-files" aria-labelledby="dataset-files-title">
    <header className="dataset-card-heading"><p className="eyebrow">01 / {copy.dataset.steps[0]}</p>
      <h2 id="dataset-files-title">{copy.dataset.filesTitle}</h2><p>{copy.dataset.filesDescription}</p>
    </header>
    <div className={`dataset-dropzone ${dragging && !locked ? 'is-dragging' : ''} ${locked ? 'is-locked' : ''}`}
      onDragOver={(event) => { event.preventDefault(); if (!locked) setDragging(true) }}
      onDragLeave={() => setDragging(false)} onDrop={drop}>
      <span className="dataset-upload-icon"><Icon name="upload" /></span>
      <p>{copy.dataset.dropTitle}</p><span id="dataset-file-help">{copy.dataset.dropDescription}</span>
      <label className={`button dataset-picker ${locked ? 'is-disabled' : ''}`}>
        {files.length ? copy.dataset.reselect : copy.dataset.choose}
        <input className="sr-only" type="file" accept={datasetFileAccept} multiple disabled={locked}
          aria-label={copy.dataset.input} aria-describedby="dataset-file-help"
          onChange={(event) => { const selected = Array.from(event.target.files ?? []); if (selected.length) onSelect(selected); event.target.value = '' }} />
      </label>
    </div>
    {files.length ? <>
      <ul className="dataset-file-list" aria-label={copy.dataset.fileList}>
        {files.map((file, index) => <li key={`${index}-${file.name}`} className={!isSupportedDatasetFile(file) ? 'dataset-file-invalid' : ''}>
          <Icon name="file" /><div className="dataset-file-info"><strong>{file.name}</strong><span>{fileSize(file.size)}</span>
            {!isSupportedDatasetFile(file) && <p>{copy.dataset.unsupported}</p>}
          </div>
          <button type="button" className="dataset-remove" disabled={locked} aria-label={`${copy.dataset.remove} ${file.name}`} onClick={() => onRemove(index)}><Icon name="close" /></button>
        </li>)}
      </ul>
      {!files.every(isSupportedDatasetFile) && <p className="dataset-selection-error" role="alert">{copy.dataset.unsupportedSummary}</p>}
      <Button className="dataset-secondary dataset-clear" disabled={locked} onClick={onClear}>{copy.dataset.clear}</Button>
    </> : <div className="dataset-no-files"><strong>{copy.dataset.empty}</strong><p>{copy.dataset.emptyDescription}</p></div>}
  </section>
}
