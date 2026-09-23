import { copy } from '../i18n/en'
import { StatePanel } from '../components/UI'

export function HRWorkspace() {
  return <>
    <div className="page-heading"><p className="eyebrow">{copy.hrEyebrow}</p><h1>{copy.hrTitle}</h1><p>{copy.hrDescription}</p></div>
    <StatePanel title={copy.hrPreview} description={copy.hrPreviewDescription} />
    <p className="demo-footnote">{copy.hrPrivacy}</p>
  </>
}
