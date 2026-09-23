import type { CompletionReceipt } from '../types/domain'

export type CompletionAction = { employeeId: string; eventId: string; idempotencyKey: string; recordId?: string }
export type CompletionPorts = {
  submit: (employeeId: string, eventId: string, options: { idempotencyKey: string; recordId?: string }) => Promise<CompletionReceipt>
  refresh: (employeeId: string) => Promise<unknown>
}

// Keep this action through an uncertain network outcome. A retry is the same
// backend operation, not a second attempt to award skill gains.
export function createCompletionAction(employeeId: string, eventId: string, makeKey: () => string = () => crypto.randomUUID(), recordId?: string): CompletionAction {
  return { employeeId, eventId, idempotencyKey: makeKey(), ...(recordId ? { recordId } : {}) }
}

export async function runCompletionAction(action: CompletionAction, ports: CompletionPorts): Promise<CompletionReceipt> {
  const receipt = await ports.submit(action.employeeId, action.eventId, { idempotencyKey: action.idempotencyKey, ...(action.recordId ? { recordId: action.recordId } : {}) })
  await ports.refresh(action.employeeId)
  return receipt
}
