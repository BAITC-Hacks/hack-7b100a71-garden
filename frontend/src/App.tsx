import { Link, Navigate, Route, Routes, useParams } from 'react-router'
import { AppShell } from './components/AppShell'
import { StatePanel } from './components/UI'
import { useSession } from './hooks/useSession'
import { EmployeeDirectory } from './pages/EmployeeDirectory'
import { EmployeeWorkspace } from './pages/EmployeeWorkspace'
import { HRWorkspace } from './pages/HRWorkspace'
import { NotFound } from './pages/NotFound'
import { SignIn } from './pages/SignIn'
import { canAccessEmployee, sessionHome } from './services/session'

function Forbidden() {
  const session = useSession()
  return <StatePanel error title="Access restricted" description="This workspace is not available to the current identity."><Link className="button" to={session ? sessionHome(session) : '/'}>Open my workspace</Link></StatePanel>
}

function EmployeeRoute() {
  const session = useSession()
  const { employeeId = '' } = useParams()
  return canAccessEmployee(session, employeeId) ? <EmployeeWorkspace /> : <Forbidden />
}

export function App() {
  const session = useSession()
  if (!session) return <SignIn />
  return <Routes><Route element={<AppShell />}>
    <Route index element={session.role === 'hr' ? <EmployeeDirectory /> : <Navigate to={sessionHome(session)} replace />} />
    <Route path="employees/:employeeId" element={<EmployeeRoute />} />
    <Route path="hr" element={session.role === 'hr' ? <HRWorkspace /> : <Forbidden />} />
    <Route path="*" element={<NotFound />} />
  </Route></Routes>
}
