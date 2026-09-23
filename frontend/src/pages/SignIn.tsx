import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { Icon } from '../components/Icon'
import { Button } from '../components/UI'
import { apiMode } from '../services/api'
import { sessionHome, setSession, type Session } from '../services/session'
import '../styles/auth.css'

export function SignIn() {
  const [role, setRole] = useState<'employee' | 'hr'>('employee')
  const [employeeId, setEmployeeId] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const isMock = apiMode === 'mock'

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      const session: Session = role === 'hr'
        ? { role, token: isMock ? 'mock-preview' : token }
        : { role, employeeId: employeeId.trim(), token: isMock ? 'mock-preview' : token }
      setSession(session)
      void navigate(sessionHome(session), { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Check your identity details.')
    }
  }

  return <main className="signin-page">
    <section className="signin-intro">
      <div className="signin-brand"><span className="brand-mark"><Icon name="compass" /></span><span>Career Quest<span className="brand-dot">.</span></span></div>
      <p className="eyebrow">YOUR NEXT CHAPTER</p>
      <h1>A clear direction.<br />A meaningful next step.</h1>
      <p>Explore your skills, understand your career target, and turn the next recommendation into progress.</p>
      <div className="signin-path" aria-label="Development journey"><span>Profile</span><Icon name="arrow" /><span>Direction</span><Icon name="arrow" /><span>Progress</span></div>
    </section>
    <section className="signin-card surface" aria-labelledby="signin-title">
      <p className="eyebrow">{isMock ? 'MOCK PREVIEW' : 'LIVE WORKSPACE'}</p>
      <h2 id="signin-title">Open your workspace</h2>
      <p>{isMock ? 'Preview the interface using development fixtures.' : 'Use the identity and access token provided by your team.'}</p>
      <form onSubmit={submit}>
        <label htmlFor="session-role">Workspace</label>
        <select id="session-role" value={role} onChange={(event) => setRole(event.target.value as 'employee' | 'hr')}>
          <option value="employee">Employee</option><option value="hr">HR</option>
        </select>
        {role === 'employee' && <><label htmlFor="session-employee">Employee ID</label><input id="session-employee" name="employeeId" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} required autoComplete="off" spellCheck={false} /></>}
        {!isMock && <><label htmlFor="session-token">Access token</label><input id="session-token" name="token" type="password" value={token} onChange={(event) => setToken(event.target.value)} required autoComplete="off" spellCheck={false} /><p className="signin-note">Your token stays in this tab’s memory and is cleared when you leave or reload.</p></>}
        {error && <p className="signin-error" role="alert">{error}</p>}
        <Button type="submit">Open workspace<Icon name="arrow" /></Button>
      </form>
      <p className="signin-note">{isMock ? 'Mock mode does not connect to the backend.' : 'Workspace selection controls navigation. Your token determines the data you can access.'}</p>
    </section>
  </main>
}
