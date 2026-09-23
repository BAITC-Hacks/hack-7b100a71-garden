import { Link } from 'react-router'
import { DatasetUpload } from '../components/dataset/DatasetUpload'
import { Icon } from '../components/Icon'
import { copy } from '../i18n/en'
import { apiMode } from '../services/api'

export function DatasetWorkspace() {
  return <>
    <Link className="text-link back-link" to="/hr"><Icon name="arrow" />{copy.dataset.back}</Link>
    <div className="page-heading"><p className="eyebrow">{copy.dataset.eyebrow}</p><h1>{copy.dataset.title}</h1><p>{copy.dataset.description}</p></div>
    <p className="dataset-mode-note">{apiMode === 'mock' ? copy.dataset.mockNotice : copy.dataset.ownershipNote}</p>
    <DatasetUpload />
  </>
}
