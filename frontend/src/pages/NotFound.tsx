import { copy } from '../i18n/en'
import { BackLink, StatePanel } from '../components/UI'

export function NotFound() {
  return <StatePanel title={copy.notFoundTitle} description={copy.notFoundDescription}><BackLink /></StatePanel>
}
