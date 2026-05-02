import { useQuery } from '@tanstack/react-query'
import type {
  Me,
  PicksResponse,
  BankrollResponse,
  StateResponse,
  ActivityResponse,
} from '../../../shared/types'
import { apiGet } from './client'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiGet<Me>('/api/me'),
    staleTime: 5 * 60_000,
  })
}

export function usePicks() {
  return useQuery({
    queryKey: ['picks'],
    queryFn: () => apiGet<PicksResponse>('/api/picks'),
  })
}

export function useBankroll() {
  return useQuery({
    queryKey: ['bankroll'],
    queryFn: () => apiGet<BankrollResponse>('/api/bankroll'),
  })
}

export function useStateRecord() {
  return useQuery({
    queryKey: ['state'],
    queryFn: () => apiGet<StateResponse>('/api/state'),
  })
}

export function useActivity() {
  return useQuery({
    queryKey: ['activity'],
    queryFn: () => apiGet<ActivityResponse>('/api/activity'),
  })
}
