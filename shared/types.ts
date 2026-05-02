import type { z } from 'zod'
import type {
  PickSchema,
  NoEdgeGameSchema,
  BestBetSchema,
  PicksResponseSchema,
  LifetimeStatsSchema,
  BankrollResponseSchema,
  MeResponseSchema,
  PlacementSchema,
  SyncQueueEntrySchema,
  ManualBetSchema,
  StateRecordSchema,
  BalanceOverrideRecordSchema,
  StateResponseSchema,
  PlacementCreateRequestSchema,
  ManualBetCreateRequestSchema,
  BalanceOverrideRequestSchema,
  ResolvedBetSchema,
  ActivityResponseSchema,
} from './schemas'

export type Pick = z.infer<typeof PickSchema>
export type NoEdgeGame = z.infer<typeof NoEdgeGameSchema>
export type BestBet = z.infer<typeof BestBetSchema>
export type PicksResponse = z.infer<typeof PicksResponseSchema>

export type LifetimeStats = z.infer<typeof LifetimeStatsSchema>
export type BankrollResponse = z.infer<typeof BankrollResponseSchema>

export type Me = z.infer<typeof MeResponseSchema>

export type Placement = z.infer<typeof PlacementSchema>
export type SyncQueueEntry = z.infer<typeof SyncQueueEntrySchema>
export type ManualBet = z.infer<typeof ManualBetSchema>
export type StateRecord = z.infer<typeof StateRecordSchema>
export type BalanceOverrideRecord = z.infer<typeof BalanceOverrideRecordSchema>
export type StateResponse = z.infer<typeof StateResponseSchema>

export type PlacementCreateRequest = z.infer<typeof PlacementCreateRequestSchema>
export type ManualBetCreateRequest = z.infer<typeof ManualBetCreateRequestSchema>
export type BalanceOverrideRequest = z.infer<typeof BalanceOverrideRequestSchema>

export type ResolvedBet = z.infer<typeof ResolvedBetSchema>
export type ActivityResponse = z.infer<typeof ActivityResponseSchema>
