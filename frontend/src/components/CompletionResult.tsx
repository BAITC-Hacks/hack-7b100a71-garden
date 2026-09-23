import type { CompletionReceipt, Skill } from '../types/domain'

export function CompletionResult({ receipt, skills }: { receipt: CompletionReceipt; skills: Skill[] }) {
  const names = new Map(skills.map((skill) => [skill.id, skill.name]))
  return <section className="completion-result surface" role="status" aria-live="polite">
    <h2>{receipt.replayed ? 'Completion already recorded' : 'Completion recorded'}</h2>
    <p>{receipt.activity.event_id} · version {receipt.version}. {receipt.replayed ? 'The same action was replayed without awarding a second gain.' : 'The backend confirmed these changes.'}</p>
    {receipt.skill_changes.length > 0 ? <ul>{receipt.skill_changes.map((change) => <li key={change.skill_id}>
      <span>{names.get(change.skill_id) || change.skill_id}</span><strong>{change.before} → {change.after}</strong>
    </li>)}</ul> : <p>No additional skill gain was recorded.</p>}
    {receipt.activity.completed_at && <p className="completion-timing">Recorded at {receipt.activity.completed_at}{receipt.activity.completed_on ? ` · logical day ${receipt.activity.completed_on}` : ''}</p>}
  </section>
}
