# DK Edge Finder — Session Rules

These rules exist to prevent the specific failure modes that have killed Cowork sessions before: output token spikes that blow past the ~8,000/min limit, context bloat that makes sessions unrecoverable, and runaway agentic loops that drain the rate limit bucket while accomplishing nothing.

Follow every rule below. No exceptions. If something conflicts with the main prompt, these rules win.

---

## Token Management

### Output discipline
- **Never generate more than ~3,000 tokens in a single response.** This is roughly 1.5 pages of text. If you need to say more, break it across multiple turns.
- **Dashboard artifacts count toward output tokens.** A full React dashboard with 15 rows of data can easily spike to 5,000+ tokens. Keep the artifact lean — 10 picks max in the initial render, with a "show more" toggle if needed.
- **Don't narrate your reasoning at length.** Short status updates between tool calls, not paragraphs. "Searching NBA odds..." is fine. A three-paragraph explanation of your search strategy is not.

### Search batching
- **Maximum 3 web searches per turn.** Fire 3, process results, respond, then continue in the next turn if more are needed.
- **Maximum 5 searches per sport.** If you can't find usable odds and model data in 5 searches, move on and note the gap.
- **Maximum 15 searches per full scan.** Even with 3 sports selected, stay under this ceiling. Prioritize quality queries over volume.

### Context hygiene
- **Don't paste full web page contents into your response.** Extract the 3–5 data points you need (odds, scores, stats) and discard the rest.
- **Don't repeat data the user already has.** If you showed odds in the text summary, the dashboard artifact shouldn't restate them in prose — just render the table.
- **Don't echo the prompt or rules back.** Assume you've read them. Act on them. Don't quote them.

---

## Session Structure

### Chunk the work
Every scan follows this cadence — one sport at a time, not all at once:

```
Turn 1: Load bankroll, resolve pending bets, ask which sports
Turn 2: User picks sports
Turn 3: Fetch odds for Sport 1 (2-3 searches), generate model probs
Turn 4: Fetch odds for Sport 2 (2-3 searches), generate model probs  
Turn 5: Fetch odds for Sport 3 (if selected)
Turn 6: Calculate all edges, deliver text summary
Turn 7: Build dashboard artifact
```

Do NOT try to do turns 3–7 in a single response. That's what causes the output token spikes.

### If you hit a rate limit
1. Stop immediately. Do not retry.
2. Tell the user: "Hit the rate limit. Wait 2 minutes, then say 'continue' and I'll pick up where I left off."
3. When the user says continue, resume from the last completed step — don't restart from scratch.

### If context is getting long
After ~15 turns in a single session, the accumulated context starts becoming a problem. At that point:
- Summarize the current state (bankroll, picks found, pending work) in a short block
- Suggest the user start a fresh chat and paste the summary in
- Save any picks to `~/dk-edge-finder/bankroll.json` before suggesting the switch

---

## Data Handling

### Odds data
- Record odds as American format integers: -110, +150, etc.
- Always note the source and approximate time the odds were observed
- If odds are more than 2 hours old for a game starting today, flag them as potentially stale
- Don't average odds from different times — use the most recent observation

### Model probabilities
- Always cite the source (ESPN BPI, Massey, 538 successor, consensus, etc.)
- If you only found one source, label the confidence as "Low — single source"
- If sources disagree by more than 10 percentage points, flag it as "Contested" and show the range
- Never round model probabilities to make an edge appear larger than it is
- Never invent a probability — if you couldn't find model data for a game, skip it

### Edge calculation
- Show your math. Implied prob, model prob, edge = model - implied. Every time.
- Don't present edges below the tier minimum — they're noise
- If an edge is between 3–5%, it's marginal even at High tier. Note that explicitly.

### Situational adjustments (applied AFTER base edge calculation)

#### Tanking detection (critical — added 2026-03-18)
Before flagging any spread bet on a team with a bottom-8 record:
1. **Check if they're eliminated from playoff contention** — if yes, flag as TANK RISK
2. **Check recent lineup patterns** — are starters getting reduced minutes? Are G-League/two-way players getting 20+ min?
3. **Apply tank penalty**: reduce model confidence by 3% for confirmed tankers, 1.5% for suspected
4. **If edge disappears after penalty, do NOT flag the bet**
5. **Never bet on a tanking team to cover a large spread** — tanking teams lose by MORE than expected because they pull starters early, run developmental lineups in Q4, and actively avoid winning close games
6. Tanking indicators: bottom-8 record after All-Star break, traded veteran starters at deadline, coach playing young players extended minutes, DNP-rest for healthy veterans
7. **Label in notes**: "TANK RISK: [reason]" so the user can make their own call

Example: Pacers (15-53) at +15.5 — model says 56% cover. But Pacers are confirmed tanking (traded Siakam, starting rookies, Haliburton DNP-rest). Apply -3% penalty → 53% cover. Implied at -108 is 51.9%. Edge drops to 1.1% — below 3% threshold. SKIP.

#### Rest / back-to-back / schedule fatigue
- **B2B penalty**: Team on second night of back-to-back gets -1.5% adjustment to cover probability (road B2B: -2.5%)
- **3-in-4 nights**: Additional -1% on top of B2B penalty if applicable
- **Rest advantage**: Team with 2+ days rest vs opponent on B2B gets +1.5% boost
- **Search NBA schedule for B2B status** during each scan — one search covers all games
- **Note in analysis**: "DEN on B2B (-1.5% adj)" or "MIL 3 days rest vs CLE on B2B (+1.5%)"

#### Line movement / sharp money
- **Check opening vs current line** during odds search. If line moved 1.5+ points, note direction.
- **Reverse line movement (RLM)**: If public is heavily on one side but line moves the other way, sharp money is likely on the contrarian side. Flag this.
- **If our pick conflicts with sharp action**: add warning "SHARP CONFLICT — line moving against this pick" and reduce Kelly fraction by 25%
- **If our pick aligns with sharp action**: note "SHARP ALIGNED" — increases confidence
- Sources for line movement: Action Network, Vegas Insider, Covers consensus

#### Motivation mismatches
- **Playoff-locked teams** (seed clinched, nothing to play for) may rest starters — model may overestimate their spread coverage
- **Play-in tournament teams** fighting for 7-10 seed: elevated motivation, model may underestimate
- **Elimination games**: teams facing playoff elimination tend to outperform models by 1-2%
- Note motivation context in analysis when relevant

### Closing Line Value (CLV) tracking — added 2026-03-18
After each bet resolves, record what the closing line was (the line at game time):
- Add `closing_line` field to each bet in data.json
- **CLV = our_line - closing_line** (positive = we got a better number)
- Track cumulative CLV in bankroll.json
- **CLV is the best predictor of long-term profitability** — a bettor who consistently beats the closing line will profit over time, even if individual bets lose
- If CLV is consistently negative (we're getting worse numbers than close), the model timing or source needs adjustment
- Weekly CLV summary in dashboard: "Avg CLV: +1.2 pts" or "Avg CLV: -0.5 pts (model may be lagging)"

---

## File Operations

### Bankroll file
- Location: `~/dk-edge-finder/bankroll.json`
- Read at session start. Write after any change. No exceptions.
- If the file doesn't exist, create it with the $500 default.
- If the file is corrupted or unreadable, tell the user and offer to reinitialize.
- Never overwrite without reading first — merge changes, don't clobber.

### Deduct on placement (critical rule — added 2026-03-17)
When the user confirms bets are placed, **immediately deduct total wager amount from current bankroll**. The dashboard must show available funds, not pre-bet balance. Money wagered is locked up and unavailable for future sizing.
- `available_bankroll = current_bankroll - sum(pending_wagers)`
- Update both `bankroll.json` and `data.json` to the post-placement amount
- Dashboard shows reduced bankroll as "Available" with pending bets noted separately
- On resolution: WIN adds back wager + profit. LOSS keeps the deduction. PUSH adds back wager.
- **Kelly sizing always uses available (post-deduction) bankroll** to prevent over-exposure.

### Pick log
- Append-only. Never delete historical picks.
- Structure: one JSON file per month at `~/dk-edge-finder/picks/YYYY-MM.json`
- Each file is an array of pick objects
- This makes it easy to review a month's performance without loading the full history

---

## Dashboard Artifact Rules

### Keep it light
- Max 10–12 rows in the main table. More data = more tokens = more risk of rate limit.
- Use `window.storage` for persistence, but don't read/write more than 3 keys per render.
- No external API calls from the artifact — all data gets baked in at render time.
- Single-file React. No separate CSS. Tailwind utility classes only.

### Required sections (in order)
1. **Status bar**: Bankroll, ROI, scan date, sports covered — one line
2. **Alerts**: Best bet, high-edge highlights, exposure warnings — only if applicable
3. **Picks table**: Ranked by edge, color-coded by tier, sortable
4. **Pending bets**: Unresolved picks from previous sessions

### Don't include
- Charts or visualizations (too token-heavy for Cowork)
- Historical performance graphs (save for standalone app graduation)
- Detailed model breakdowns per pick (put those in the text summary instead)

---

## Behavioral Rules

### Never do these things
- Don't scan a sport the user didn't ask for
- Don't auto-log picks without asking first
- Don't suggest the user increase their bankroll
- Don't present a pick without showing the edge math
- Don't skip the responsible betting footer
- Don't apologize for rate limits — just state the situation and the recovery plan
- Don't restart a scan from scratch after an interruption — pick up where you stopped

### Always do these things
- Start every session by loading bankroll and checking pending bets
- Ask which sports before scanning anything
- Show the text summary before building the artifact
- End every scan with: "All models carry uncertainty. Edge estimates are probabilistic, not guarantees. Bet responsibly."
- Save bankroll state before suggesting a session switch

### Never assume
- Don't assume the user hasn't pushed. If they say they pushed, they pushed.
- Don't assume data.json on disk matches what's live on Netlify. Check if asked.
- Don't assume the user wants to be asked before every action. Read the room.
- Don't assume your model is correct. If an edge looks too good (>10%), the model is probably wrong — investigate, don't cap.
- Don't assume a standard deviation or probability parameter — RESEARCH IT. If you can't find a measured value from academic literature, historical data, or verified sources, label it "UNVALIDATED" and note the uncertainty.
- Don't invent combined SD values by guessing model error. Measure it or skip the sport.
- Don't cap edges to hide a broken model. If the math produces a 27% edge, the model inputs are wrong — fix the inputs.
- When the user says "research this" — actually read papers, fetch data, find measured values. Don't summarize search result titles.

### When in doubt
- Shorter is better than longer
- Fewer searches is better than more
- Skipping a game with thin data is better than guessing
- Splitting across turns is better than one massive response
