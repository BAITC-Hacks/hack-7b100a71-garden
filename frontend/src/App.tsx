import { Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { EmployeeDirectory } from './pages/EmployeeDirectory'
import { EmployeeWorkspace } from './pages/EmployeeWorkspace'
import { HRWorkspace } from './pages/HRWorkspace'
import { NotFound } from './pages/NotFound'

export function App() {
  return <Routes><Route element={<AppShell />}>
    <Route index element={<EmployeeDirectory />} />
    <Route path="employees/:employeeId" element={<EmployeeWorkspace />} />
    <Route path="hr" element={<HRWorkspace />} />
    <Route path="*" element={<NotFound />} />
  </Route></Routes>
}
