import { useMatch, useNavigate } from 'react-router'
import { useEmployees } from '../hooks/useEmployees'
import { copy } from '../i18n/en'
import { getAccessIssue } from '../utils/accessError'

export function EmployeeSelector() {
  const { data: employees, isPending, isError, error, isFetching, refetch } = useEmployees()
  const access = getAccessIssue(error, 'directory')
  const match = useMatch('/employees/:employeeId')
  const navigate = useNavigate()
  const selected = employees?.some((employee) => employee.id === match?.params.employeeId) ? match?.params.employeeId : ''
  return <div className="employee-selector">
    <label htmlFor="employee-select">{copy.selector}</label>
    <select id="employee-select" value={access ? '' : selected ?? ''} disabled={isPending || isError || !employees?.length}
      aria-describedby={access ? 'employee-select-access' : undefined}
      onChange={(event) => { if (event.target.value) void navigate(`/employees/${encodeURIComponent(event.target.value)}`) }}>
      <option value="" disabled>{access ? access.selectorLabel : isPending ? copy.selectorLoading : isError ? copy.selectorError : !employees?.length ? copy.selectorEmpty : copy.selectorPlaceholder}</option>
      {!access && employees?.map((employee) => <option value={employee.id} key={employee.id}>{employee.name}</option>)}
    </select>
    {access && <span id="employee-select-access" className="sr-only">{access.selectorNote}</span>}
    {isError && !access && <button type="button" className="selector-retry" disabled={isFetching} onClick={() => void refetch()}>{isFetching ? copy.retrying : copy.selectorRetry}</button>}
  </div>
}
