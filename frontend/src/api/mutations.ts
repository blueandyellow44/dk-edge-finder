import { useMutation, useQueryClient } from '@tanstack/react-query'
import type {
  BalanceOverrideRecord,
  Placement,
  PlaceBetResponse,
} from '../../../shared/types'
import { ApiError, apiDelete, apiPost } from './client'

export function usePlacePickBet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ pickIndex, key }: { pickIndex: number; key: string }) => {
      const idempotencyKey = crypto.randomUUID()
      let dispatchStatus: 'ok' | 'queued' = 'ok'
      try {
        await apiPost<PlaceBetResponse>('/api/place-bet', {
          pick_indices: [pickIndex],
          idempotency_key: idempotencyKey,
        })
      } catch (err) {
        if (err instanceof ApiError && err.status === 502) {
          dispatchStatus = 'queued'
        } else {
          throw err
        }
      }
      return apiPost<Placement>('/api/state/placements', {
        key,
        action: 'placed' as const,
        dispatch_status: dispatchStatus,
        idempotency_key: idempotencyKey,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['state'] })
    },
  })
}

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

export function useDeletePlacement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key }: { key: string }) =>
      apiDelete(`/api/state/placements/${encodeURIComponent(key)}`),
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

export function useRetrySyncQueue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key }: { key: string }) =>
      apiPost<PlaceBetResponse>('/api/state/sync-queue/retry', {
        key,
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['state'] }),
  })
}
