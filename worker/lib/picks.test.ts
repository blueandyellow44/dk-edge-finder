import { describe, test, expect } from 'vitest'
import type { Env } from '../env'
import { getLatestScanDate, getPicksResponse, loadDataJson } from './picks'

type DataJsonInput = Record<string, unknown>

function makeEnv(dataJson: DataJsonInput, lastModified?: string | null): Env {
  const fetcher = {
    async fetch(input: Request | string): Promise<Response> {
      const url = typeof input === 'string' ? input : input.url
      if (url.endsWith('/data.json')) {
        const headers = new Headers({ 'content-type': 'application/json' })
        if (lastModified) headers.set('last-modified', lastModified)
        return new Response(JSON.stringify(dataJson), { status: 200, headers })
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

const minimalPick = {
  rank: 1,
  sport: 'MLB',
  event: 'NYY @ BOS',
  market: 'Moneyline',
  pick: 'NYY',
  odds: '-110',
  implied: 52.4,
  model: 60.0,
  edge: 7.6,
  ev_per_dollar: 0.072,
  tier: 'HIGH',
  wager: 12.5,
  notes: '',
  sources: '',
  confidence: '',
  dk_link: 'https://sportsbook.draftkings.com/event/123',
  type: 'game',
  start_time: '2026-04-30T19:05:00Z',
}

describe('getPicksResponse — em-dash strip', () => {
  test('strips em-dash from scan_subtitle', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: 'Thursday, April 30, 2026 — MLB (11), NBA (3), NHL (2)',
      games_analyzed: 16,
      best_bet: null,
      picks: [],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.scan_subtitle).toBe('Thursday, April 30, 2026 - MLB (11), NBA (3), NHL (2)')
    expect(res.scan_subtitle).not.toContain('—')
  })

  test('strips em-dash from pick string fields', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [
        {
          ...minimalPick,
          event: 'NYY — BOS',
          notes: 'Strong line — high confidence',
          sources: 'oddsshark — sagarin',
        },
      ],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].event).toBe('NYY - BOS')
    expect(res.picks[0].notes).toBe('Strong line - high confidence')
    expect(res.picks[0].sources).toBe('oddsshark - sagarin')
    expect(JSON.stringify(res.picks[0])).not.toContain('—')
  })

  test('strips em-dash from no_edge_games and best_bet', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: { title: 'Top pick — MLB', desc: 'Edge of 7.6% — wager $12.50' },
      picks: [],
      no_edge_games: [
        { sport: 'NBA', event: 'NY — ATL', line: 'NY -2.5', reason: 'Edge below 3% — skipped' },
      ],
    })
    const res = await getPicksResponse(env)
    expect(res.best_bet?.title).toBe('Top pick - MLB')
    expect(res.best_bet?.desc).toBe('Edge of 7.6% - wager $12.50')
    expect(res.no_edge_games[0].event).toBe('NY - ATL')
    expect(res.no_edge_games[0].reason).toBe('Edge below 3% - skipped')
  })
})

describe('getPicksResponse — percent-string coercion', () => {
  test('coerces "35.7%" string to 35.7 number for implied / model / edge', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [
        {
          ...minimalPick,
          implied: '35.7%',
          model: '42.3%',
          edge: '6.6%',
        },
      ],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].implied).toBe(35.7)
    expect(res.picks[0].model).toBe(42.3)
    expect(res.picks[0].edge).toBe(6.6)
  })

  test('passes through numeric implied / model / edge unchanged', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, implied: 52.4, model: 60.0, edge: 7.6 }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].implied).toBe(52.4)
    expect(res.picks[0].model).toBe(60.0)
    expect(res.picks[0].edge).toBe(7.6)
  })

  test('falls back to 0 for non-numeric / non-string implied', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, implied: null, model: undefined, edge: 'not-a-number' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].implied).toBe(0)
    expect(res.picks[0].model).toBe(0)
    expect(res.picks[0].edge).toBe(0)
  })

  test('reads implied from implied_prob fallback key', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, implied: undefined, implied_prob: '52.4%', model: undefined, model_prob: 60.0 }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].implied).toBe(52.4)
    expect(res.picks[0].model).toBe(60.0)
  })
})

describe('getPicksResponse — dollars-string coercion', () => {
  test('coerces "$11.41" string to 11.41 number for wager', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, wager: '$11.41' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].wager).toBe(11.41)
  })

  test('coerces from "bet" fallback key (legacy emit shape)', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, wager: undefined, bet: '$25.00' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].wager).toBe(25.0)
  })

  test('passes through numeric wager unchanged', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, wager: 12.5 }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].wager).toBe(12.5)
  })

  test('strips embedded commas in dollar string', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, wager: '$1,234.56' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].wager).toBe(1234.56)
  })

  test('falls back to 0 for missing wager', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, wager: undefined, bet: undefined }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].wager).toBe(0)
  })
})

describe('getPicksResponse — odds string coercion', () => {
  test('passes through American odds string unchanged', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, odds: '-110' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].odds).toBe('-110')
  })

  test('coerces positive numeric odds to "+165" string', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, odds: 165 }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].odds).toBe('+165')
  })

  test('coerces negative numeric odds to "-110" string', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, odds: -110 }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].odds).toBe('-110')
  })
})

describe('getPicksResponse — missing-field defaults', () => {
  test('fills sparse pick with safe defaults and still passes schema', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{}],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks).toHaveLength(1)
    const p = res.picks[0]
    expect(p.rank).toBe(1)
    expect(p.sport).toBe('')
    expect(p.event).toBe('')
    expect(p.market).toBe('')
    expect(p.pick).toBe('')
    expect(p.odds).toBe('')
    expect(p.implied).toBe(0)
    expect(p.model).toBe(0)
    expect(p.edge).toBe(0)
    expect(p.ev_per_dollar).toBe(0)
    expect(p.tier).toBe('')
    expect(p.wager).toBe(0)
    expect(p.notes).toBe('')
    expect(p.sources).toBe('')
    expect(p.confidence).toBe('')
    expect(p.dk_link).toBe('')
    expect(p.type).toBe('game')
    expect(p.start_time).toBe('')
  })

  test('assigns fallback rank from array index when rank field is missing', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 2,
      best_bet: null,
      picks: [{}, {}],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].rank).toBe(1)
    expect(res.picks[1].rank).toBe(2)
  })

  test('coerces unknown type values to "game"', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, type: 'something-weird' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].type).toBe('game')
  })

  test('preserves type "prop" when explicitly set', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [{ ...minimalPick, type: 'prop' }],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.picks[0].type).toBe('prop')
  })

  test('top-level optional scan fields fall back to safe defaults', async () => {
    // scan_date is required (the Python model always emits it; absence would
    // surface as a Zod 500, see schema-validation block). Other top-level
    // fields default cleanly when the model omits them.
    const env = makeEnv({ scan_date: '2026-04-30' })
    const res = await getPicksResponse(env)
    expect(res.scan_subtitle).toBe('')
    expect(res.games_analyzed).toBe(0)
    expect(res.best_bet).toBeNull()
    expect(res.picks).toEqual([])
    expect(res.no_edge_games).toEqual([])
  })

  test('best_bet returns null for non-object input', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: 'not-an-object',
      picks: [],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.best_bet).toBeNull()
  })
})

describe('getPicksResponse — scan_age_seconds derivation', () => {
  test('derives scan_age_seconds from Last-Modified header', async () => {
    const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000).toUTCString()
    const env = makeEnv(
      {
        scan_date: '2026-04-30',
        scan_subtitle: '',
        games_analyzed: 1,
        best_bet: null,
        picks: [],
        no_edge_games: [],
      },
      tenMinutesAgo,
    )
    const res = await getPicksResponse(env)
    expect(res.scan_age_seconds).not.toBeNull()
    const age = res.scan_age_seconds as number
    expect(age).toBeGreaterThanOrEqual(599)
    expect(age).toBeLessThanOrEqual(601)
  })

  test('returns null when Last-Modified header absent', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: '',
      games_analyzed: 1,
      best_bet: null,
      picks: [],
      no_edge_games: [],
    })
    const res = await getPicksResponse(env)
    expect(res.scan_age_seconds).toBeNull()
  })

  test('returns null when Last-Modified header is unparseable', async () => {
    const env = makeEnv(
      {
        scan_date: '2026-04-30',
        scan_subtitle: '',
        games_analyzed: 1,
        best_bet: null,
        picks: [],
        no_edge_games: [],
      },
      'not-a-real-date',
    )
    const res = await getPicksResponse(env)
    expect(res.scan_age_seconds).toBeNull()
  })

  test('clamps negative age (future Last-Modified) to 0', async () => {
    const oneMinuteFromNow = new Date(Date.now() + 60 * 1000).toUTCString()
    const env = makeEnv(
      {
        scan_date: '2026-04-30',
        scan_subtitle: '',
        games_analyzed: 1,
        best_bet: null,
        picks: [],
        no_edge_games: [],
      },
      oneMinuteFromNow,
    )
    const res = await getPicksResponse(env)
    expect(res.scan_age_seconds).toBe(0)
  })
})

describe('getPicksResponse — empty-picks case (today\'s real shape)', () => {
  test('zero-edge scan returns empty picks array and full no_edge_games', async () => {
    const env = makeEnv({
      scan_date: '2026-04-30',
      scan_subtitle: 'Thursday, April 30, 2026 — MLB (11), NBA (3), NHL (2)',
      games_analyzed: 16,
      best_bet: null,
      picks: [],
      no_edge_games: [
        { sport: 'NBA', event: 'NY @ ATL', line: 'NY -2.5', reason: 'Edge below 3% threshold' },
        { sport: 'NBA', event: 'BOS @ PHI', line: 'BOS -6.5', reason: 'Edge below 3% threshold' },
      ],
    })
    const res = await getPicksResponse(env)
    expect(res.picks).toEqual([])
    expect(res.no_edge_games).toHaveLength(2)
    expect(res.games_analyzed).toBe(16)
    expect(res.best_bet).toBeNull()
    expect(res.scan_subtitle).not.toContain('—')
  })
})

describe('getPicksResponse — schema validation', () => {
  test('rejects malformed scan_date that cannot be coerced', async () => {
    const env = makeEnv({
      scan_date: 'not-a-date',
      scan_subtitle: '',
      games_analyzed: 0,
      best_bet: null,
      picks: [],
      no_edge_games: [],
    })
    await expect(getPicksResponse(env)).rejects.toThrow()
  })
})

describe('loadDataJson', () => {
  test('returns parsed data and lastModified Date', async () => {
    const lastMod = 'Thu, 30 Apr 2026 19:00:00 GMT'
    const env = makeEnv({ scan_date: '2026-04-30', picks: [] }, lastMod)
    const { data, lastModified } = await loadDataJson(env)
    expect(data.scan_date).toBe('2026-04-30')
    expect(lastModified).toBeInstanceOf(Date)
    expect(lastModified?.toUTCString()).toBe(lastMod)
  })

  test('throws on non-OK ASSETS response', async () => {
    const env: Env = {
      ASSETS: {
        async fetch() {
          return new Response('Not Found', { status: 404 })
        },
      } as unknown as Env['ASSETS'],
      EDGE_STATE: {} as Env['EDGE_STATE'],
      GITHUB_TOKEN: '',
    } as Env
    await expect(loadDataJson(env)).rejects.toThrow(/data\.json fetch failed: 404/)
  })
})

describe('getLatestScanDate', () => {
  test('returns scan_date string from data.json', async () => {
    const env = makeEnv({ scan_date: '2026-04-30', picks: [] })
    const date = await getLatestScanDate(env)
    expect(date).toBe('2026-04-30')
  })

  test('returns empty string when scan_date is missing or non-string', async () => {
    const env = makeEnv({ picks: [] })
    expect(await getLatestScanDate(env)).toBe('')

    const env2 = makeEnv({ scan_date: 123, picks: [] })
    expect(await getLatestScanDate(env2)).toBe('')
  })
})
