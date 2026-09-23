import { useMatch, useNavigate } from 'react-router'
import { useEmployees } from '../hooks/useEmployees'
import { copy } from '../i18n/en'

export function EmployeeSelector() {
  const { data: employees, isPending, isError, isFetching, refetch } = useEmployees()
  const match = useMatch('/employees/:employeeId')
  const navigate = useNavigate()
  const selected = employees?.some((employee) => employee.id === match?.params.employeeId) ? match?.params.employeeId : ''
  return <div className="employee-selector">
    <label htmlFor="employee-select">{copy.selector}</label>
    <select id="employee-select" value={selected ?? ''} disabled={isPending || isError || !employees?.length}
      onChange={(event) => { if (event.target.value) void navigate(`/employees/${encodeURIComponent(event.target.value)}`) }}>
      <option value="" disabled>{isPending ? copy.selectorLoading : isError ? copy.selectorError : !employees?.length ? copy.selectorEmpty : copy.selectorPlaceholder}</option>
      {employees?.map((employee) => <option value={employee.id} key={employee.id}>{employee.name}</option>)}
    </select>
    {isError && <button type="button" className="selector-retry" disabled={isFetching} onClick={() => void refetch()}>{isFetching ? copy.retrying : copy.selectorRetry}</button>}
  </div>
}
