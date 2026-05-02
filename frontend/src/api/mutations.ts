import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { BalanceOverrideRecord, Placement } from '../../../shared/types'
import { apiDelete, apiPost } from './client'

export function useSkipPick() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key }: { key: string }) =>
      apiPost<Placement>('/api/state/placements', {
        key,
        action: 'skipped' as const,
        dispatch_status: 'ok' as const,
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['state'] }),
  })
}

export function useMarkPickAsPlaced() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key }: { key: string }) =>
      apiPost<Placement>('/api/state/placements', {
        key,
        action: 'placed' as const,
        dispatch_status: 'ok' as const,
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['state'] }),
  })
}

export function useSetBalanceOverride() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ amount, note }: { amount: number; note: string }) =>
      apiPost<BalanceOverrideRecord>('/api/balance-override', { amount, note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bankroll'] })
    },
  })
}

export function useDeleteManualBet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      apiDelete(`/api/state/manual-bets/${encodeURIComponent(id)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['state'] }),
  })
}
