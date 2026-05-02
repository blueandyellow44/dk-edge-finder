import { describe, test, expect } from 'vitest'
import type { Env } from '../env'
import { getActivityResponse } from './activity'

type DataJsonInput = Record<string, unknown>

function makeEnv(dataJson: DataJsonInput): Env {
  const fetcher = {
    async fetch(input: Request | string): Promise<Response> {
      const url = typeof input === 'string' ? input : input.url
      if (url.endsWith('/data.json')) {
        return new Response(JSON.stringify(dataJson), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      return new Response('Not Found', { status: 404 })
    },
  }
  return {
    ASSETS: fetcher as unknown as Env['ASSETS'],
    EDGE_STATE: {} as Env['EDGE_STATE'],
    GITHUB_TOKEN: '',
  } as Env
}

const minimalBet = {
  date: '2026-04-30',
  sport: 'MLB',
  event: 'NYY @ BOS',
  pick: 'NYY',
  odds: '-110',
  wager: 12.5,
  outcome: 'win',
  pnl: 11.36,
  final_score: 'NYY 5, BOS 3',
}

describe('getActivityResponse — em-dash strip', () => {
  test('strips em-dash from sport, event, pick, final_score', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        {
          ...minimalBet,
          sport: 'NBA — East',
          event: 'NY — ATL',
          pick: 'NY -2.5 — moneyline',
          final_score: 'NY 110 — ATL 105',
        },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].sport).toBe('NBA - East')
    expect(res.bets[0].event).toBe('NY - ATL')
    expect(res.bets[0].pick).toBe('NY -2.5 - moneyline')
    expect(res.bets[0].final_score).toBe('NY 110 - ATL 105')
    expect(JSON.stringify(res.bets[0])).not.toContain('—')
  })
})

describe('getActivityResponse — odds string coercion', () => {
  test('passes through American odds string unchanged', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, odds: '-110' }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].odds).toBe('-110')
  })

  test('coerces positive numeric odds to "+165" string', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, odds: 165 }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].odds).toBe('+165')
  })

  test('coerces negative numeric odds to "-110" string', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, odds: -110 }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].odds).toBe('-110')
  })

  test('falls back to empty string for non-numeric, non-string odds', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, odds: null }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].odds).toBe('')
  })
})

describe('getActivityResponse — outcome filter and coercion', () => {
  test('filters out pending bets', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        { ...minimalBet, date: '2026-04-30', outcome: 'win' },
        { ...minimalBet, date: '2026-04-29', outcome: 'pending' },
        { ...minimalBet, date: '2026-04-28', outcome: 'loss' },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets).toHaveLength(2)
    expect(res.bets.every((b) => b.outcome !== 'pending')).toBe(true)
  })

  test('coerces unknown outcome to "pending" (then filters it out)', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        { ...minimalBet, outcome: 'win' },
        { ...minimalBet, outcome: 'something-weird' },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets).toHaveLength(1)
    expect(res.bets[0].outcome).toBe('win')
  })

  test('preserves win, loss, and push outcomes', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        { ...minimalBet, date: '2026-04-30', outcome: 'win' },
        { ...minimalBet, date: '2026-04-29', outcome: 'loss' },
        { ...minimalBet, date: '2026-04-28', outcome: 'push' },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets).toHaveLength(3)
    expect(res.bets.map((b) => b.outcome)).toEqual(['win', 'loss', 'push'])
  })
})

describe('getActivityResponse — date-desc sort', () => {
  test('sorts bets newest date first', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        { ...minimalBet, date: '2026-04-15', outcome: 'win' },
        { ...minimalBet, date: '2026-04-30', outcome: 'win' },
        { ...minimalBet, date: '2026-04-22', outcome: 'win' },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets.map((b) => b.date)).toEqual(['2026-04-30', '2026-04-22', '2026-04-15'])
  })
})

describe('getActivityResponse — wager and pnl coercion', () => {
  test('passes through numeric wager and pnl', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, wager: 12.5, pnl: -12.5 }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].wager).toBe(12.5)
    expect(res.bets[0].pnl).toBe(-12.5)
  })

  test('falls back to 0 for non-numeric wager and pnl', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, wager: '$12.50', pnl: 'not-a-number' }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets[0].wager).toBe(0)
    expect(res.bets[0].pnl).toBe(0)
  })
})

describe('getActivityResponse — missing-field defaults', () => {
  test('fills sparse bet with safe defaults when date and outcome are valid', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ date: '2026-04-30', outcome: 'win' }],
    })
    const res = await getActivityResponse(env)
    expect(res.bets).toHaveLength(1)
    const b = res.bets[0]
    expect(b.sport).toBe('')
    expect(b.event).toBe('')
    expect(b.pick).toBe('')
    expect(b.odds).toBe('')
    expect(b.wager).toBe(0)
    expect(b.outcome).toBe('win')
    expect(b.pnl).toBe(0)
    expect(b.final_score).toBe('')
  })

  test('returns empty bets array when data.bets is missing', async () => {
    const env = makeEnv({ scan_date: '2026-04-30' })
    const res = await getActivityResponse(env)
    expect(res.bets).toEqual([])
  })

  test('returns empty bets array when data.bets is non-array', async () => {
    const env = makeEnv({ scan_date: '2026-04-30', bets: 'not-an-array' })
    const res = await getActivityResponse(env)
    expect(res.bets).toEqual([])
  })

  test('returns empty bets array when all bets are pending', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [
        { ...minimalBet, outcome: 'pending' },
        { ...minimalBet, outcome: 'pending' },
      ],
    })
    const res = await getActivityResponse(env)
    expect(res.bets).toEqual([])
  })
})

describe('getActivityResponse — schema validation', () => {
  test('rejects resolved bet with malformed date', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, date: 'not-a-date' }],
    })
    await expect(getActivityResponse(env)).rejects.toThrow()
  })

  test('rejects resolved bet with missing date', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      bets: [{ ...minimalBet, date: undefined }],
    })
    await expect(getActivityResponse(env)).rejects.toThrow()
  })
})
