import type { ActivityHistory as HistoryRecord } from '../types/domain'

export function ActivityHistory({ records }: { records: HistoryRecord[] }) {
  return <details className="activity-history surface">
    <summary>Activity history <span>{records.length}</span></summary>
    <p>Each row is a separate participation. Enrollment dates and completion times have different meanings.</p>
    {records.length ? <div className="history-table-scroll"><table>
      <thead><tr><th>Activity / record</th><th>Status</th><th>Progress</th><th>Enrollment</th><th>Completion</th><th>Source</th></tr></thead>
      <tbody>{records.map((record) => <tr key={record.id}>
        <td>{record.title || record.eventId}<small>{record.id}</small></td>
        <td>{record.status}</td><td>{record.completionPct === undefined ? '—' : `${record.completionPct}%`}</td>
        <td>{record.date || '—'}</td><td>{record.completedAt || record.completedOn || 'Not recorded'}{record.completedAt && record.completedOn && <small>Logical day: {record.completedOn}</small>}</td>
        <td>{record.assignedBy || '—'}</td>
      </tr>)}</tbody>
    </table></div> : <p>No activity history for this profile.</p>}
  </details>
}
