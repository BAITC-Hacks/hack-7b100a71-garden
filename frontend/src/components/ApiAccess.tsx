import { createContext, useContext, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiMode } from '../services/api'
import { getApiToken, setApiToken } from '../services/apiSession'
import { apiCopy } from '../i18n/api'
import { Button } from './UI'
import { Icon } from './Icon'

const AccessContext = createContext<(() => Promise<boolean>) | null>(null)

export function ApiAccess({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [connected, setConnected] = useState(() => Boolean(getApiToken()))
  const [token, setToken] = useState('')
  const configured = Boolean(import.meta.env.VITE_API_BASE_URL?.trim())

  async function changeAccess() {
    // Do not change identity underneath an acknowledged/in-flight mutation.
    const busy = client.getQueryCache().getAll().some((query) => {
      const name = query.queryKey[0]
      const phase = (query.state.data as { phase?: string } | undefined)?.phase
      return (name === 'activity-completion' || name === 'dataset-upload') && ['submitting', 'validating', 'importing', 'refreshing', 'checking-import'].includes(phase ?? '')
    })
    if (busy) return false
    setConnected(false)
    setToken('')
    await client.cancelQueries()
    setApiToken('')
    client.clear()
    return true
  }

  if (apiMode !== 'real') return children
  return <AccessContext.Provider value={changeAccess}>
    {connected ? children : <main className="api-access-page">
      <section className="surface api-access-card" aria-labelledby="api-access-title">
        <span className="api-access-mark"><Icon name="compass" /></span>
        <p className="eyebrow">{apiCopy.eyebrow}</p><h1 id="api-access-title">{apiCopy.title}</h1><p>{apiCopy.description}</p>
        {!configured && <p className="api-access-error" role="alert">{apiCopy.missingAddress}</p>}
        <form onSubmit={(event) => { event.preventDefault(); if (configured && token.trim()) { setApiToken(token.trim()); setToken(''); setConnected(true) } }}>
          <label htmlFor="api-access-token">{apiCopy.token}</label>
          <input id="api-access-token" type="password" autoComplete="off" spellCheck={false} value={token}
            onChange={(event) => setToken(event.target.value)} required aria-describedby="api-access-privacy" disabled={!configured} />
          <p id="api-access-privacy">{apiCopy.privacy}</p>
          <Button type="submit" disabled={!configured || !token.trim()}>{apiCopy.connect}</Button>
        </form>
      </section>
    </main>}
  </AccessContext.Provider>
}

export function ApiSessionControls() {
  const changeAccess = useContext(AccessContext)
  const [blocked, setBlocked] = useState(false)
  if (!changeAccess) return null
  return <div className="api-session-controls">
    <button type="button" className="text-link" onClick={() => void changeAccess().then((changed) => setBlocked(!changed))}>{apiCopy.change}</button>
    {blocked && <span role="status">{apiCopy.busy}</span>}
  </div>
}
