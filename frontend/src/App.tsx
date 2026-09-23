import { Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { EmployeeDirectory } from './pages/EmployeeDirectory'
import { EmployeeWorkspace } from './pages/EmployeeWorkspace'
import { HRWorkspace } from './pages/HRWorkspace'
import { NotFound } from './pages/NotFound'
import { DatasetWorkspace } from './pages/DatasetWorkspace'
import { ApiAccess } from './components/ApiAccess'

export function App() {
  return <ApiAccess><Routes><Route element={<AppShell />}>
    <Route index element={<EmployeeDirectory />} />
    <Route path="employees/:employeeId" element={<EmployeeWorkspace />} />
    <Route path="hr" element={<HRWorkspace />} />
    <Route path="hr/dataset" element={<DatasetWorkspace />} />
    <Route path="*" element={<NotFound />} />
  </Route></Routes></ApiAccess>
}
