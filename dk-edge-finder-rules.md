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

### When in doubt
- Shorter is better than longer
- Fewer searches is better than more
- Skipping a game with thin data is better than guessing
- Splitting across turns is better than one massive response
