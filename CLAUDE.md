# CLAUDE.md

## Prime Directive

Every code change must be verifiable before it ships. Write code defensively. Assume every function will receive bad input, every API will fail, every state update will race, and every edge case will be hit in production. When in doubt, add a guard clause, not a comment. The goal is not to build what is technically impressive. It is to build what Max actually reaches for every morning.

---

## Session Start Protocol

At the beginning of every session:

1. Read `tasks/lessons.md` in full. Identify any lessons relevant to today's work.
2. Read `tasks/todo.md`. State the current status of each in-progress item.
3. If working on an existing project, read the most recently modified source files to re-orient. Do not rely on memory from previous sessions.
4. State aloud: what you are about to do, what files you will touch, and what could go wrong.

If `tasks/lessons.md` or `tasks/todo.md` do not exist, create them before proceeding.

---

## Planning and Execution

### Plan Mode Is the Default

Enter plan mode for ANY non-trivial task — defined as 3 or more steps, any architectural decision, any change that touches more than one file, or any change where the failure mode is not immediately obvious. Planning is not optional overhead. It is how you avoid burning an hour on the wrong approach.

A plan must include:

- **Goal**: One sentence. What does "done" look like?
- **Files affected**: Every file that will be created, modified, or deleted.
- **Dependencies**: What needs to exist, be running, or be configured for this to work? Surface ALL dependencies upfront in one list — tokens, API keys, running services, OS requirements, network access.
- **Failure modes**: At least two things that could go wrong and how you will handle each.
- **Verification**: How you will prove the change works before declaring it done.

Write the plan to `tasks/todo.md` with checkable items. Check in with Max before starting implementation on anything that takes more than 15 minutes.

### When Something Goes Sideways, Stop

If an approach hits unexpected resistance — an error you did not predict, a dependency you missed, a data shape that does not match — STOP immediately. Do not push through with patches. Do not add a second fix on top of a broken first fix. Re-read the error. Re-read the code. Update the plan. Then proceed from clean ground. The sunk cost of the broken approach is zero. The cost of a cascading patch chain is hours.

### One Change, One Concern

Never combine unrelated fixes in a single edit. If a bug fix requires a refactor, do the refactor first, verify it works, then fix the bug. Interleaving changes is the number one source of hard-to-diagnose regressions. Every commit should be reversible in isolation.

### Track Progress Ruthlessly

- Mark items complete in `tasks/todo.md` as you go.
- After each meaningful step, write a one-line summary of what changed and why.
- At session end, add a review section to `tasks/todo.md` covering: what was accomplished, what is still open, and what the next session should start with.
- If the session involved more than 5 file changes, list every file modified and the nature of each change.

---

## Subagent Strategy

Use subagents liberally to keep the main context window clean. The rules:

- **One task per subagent.** Do not overload a single subagent with multiple concerns.
- **Offload to subagents**: research, exploration, parallel analysis, file reading, test running, and any task where the output is a summary or a yes/no answer.
- **Keep in main context**: architectural decisions, multi-file coordination, and anything that requires awareness of the full plan.
- For complex problems, throw more compute at it — spawn multiple subagents working in parallel on different angles of the same problem.
- When a subagent returns results, verify them. Subagents can hallucinate or miss context just like the main agent.

---

## Bug Prevention Rules

### Read Before You Write

Before editing any file, read the relevant surrounding code first. Do not rely on memory or assumptions about what a function does, what arguments it accepts, or what it returns. Re-read the actual source every time. For files over 200 lines, read the specific section plus 30 lines of context above and below. For files over 500 lines, re-read the target section immediately before each edit — never rely on earlier reads.

### Match the Existing Pattern

Before adding new code, study how the codebase already handles the same concern. Match naming conventions, error handling patterns, data flow patterns, and code organization. A consistent codebase is a debuggable codebase. Do not introduce new patterns without explicit discussion.

### Validate at Boundaries

Every function that receives external input (user input, API responses, URL parameters, form data, function arguments from other modules) must validate before processing. Check for: undefined/null, wrong type, empty strings, empty arrays, out-of-range numbers, malformed objects. Fail loud and early.

```javascript
// BAD — trusts the input
function processUser(user) {
  return user.name.toUpperCase();
}

// GOOD — validates at the boundary
function processUser(user) {
  if (!user || typeof user.name !== 'string') {
    console.error('processUser: invalid user object', user);
    return null;
  }
  return user.name.toUpperCase();
}
```

### Handle Every Error Path

No unhandled promises. No empty catch blocks. No "this will never happen" assumptions. Every async operation gets a try/catch or .catch(). Every catch block either recovers meaningfully OR logs context and re-throws. Never swallow errors silently.

```javascript
// BAD
try { await fetchData(); } catch (e) { /* ignore */ }

// GOOD
try {
  const data = await fetchData();
  return data;
} catch (error) {
  console.error('fetchData failed:', {
    message: error.message,
    stack: error.stack,
    context: { endpoint, params }
  });
  return { error: true, message: 'Failed to load data. Please try again.' };
}
```

### Never Trust State Timing

Assume state is stale. In React, values inside closures capture the value at render time, not call time. In GAS, google.script.run is asynchronous and the UI may have changed by the time the callback fires. Always verify state is still valid before acting on it.

```javascript
// React: functional updates for state depending on previous state
setItems(prev => [...prev, newItem]);  // GOOD
setItems([...items, newItem]);          // BAD — items may be stale
```

### Guard Against Undefined Chains

Property access chains are the most common source of runtime crashes. Use optional chaining for reads. Never use optional chaining for writes or function calls unless you genuinely want silent no-ops.

```javascript
const name = response?.data?.user?.name ?? 'Unknown';
```

### Log Strategically, Not Excessively

Add structured logging at decision points, not on every line. Every log should answer: what happened, what data was involved, and what was the outcome.

```javascript
console.log('[fetchUser] START', { userId });
console.log('[fetchUser] SUCCESS', { userId, userName: data.name });
console.log('[fetchUser] FAIL', { userId, error: err.message });
```

---

## Debugging Protocol

When a bug appears, follow these steps in order. Do not skip ahead. Do not guess.

### Step 1: Reproduce

Document the exact steps to reproduce the bug. What input was given. What was expected. What actually happened. If you cannot reproduce it, you cannot fix it.

### Step 2: Isolate

Narrow the scope. Frontend or backend? Data or rendering? Logic or timing? Use binary search: comment out half the suspect code and see if the bug persists. Repeat until you have the smallest possible reproducing case.

### Step 3: Understand the Root Cause

Before changing any code, write a one-sentence root cause explanation. "The array is empty because the filter predicate uses strict equality on a string that was cast to a number." If you cannot write this sentence, you do not yet understand the bug and must not attempt a fix. Dig deeper.

### Step 4: Fix Narrowly

Change the minimum amount of code needed to fix the root cause. Do not "fix" nearby code that is not broken. Do not refactor while fixing. Do not add features while fixing. One concern.

### Step 5: Verify the Fix AND the Surroundings

Confirm the bug is fixed by re-running the reproduction steps. Then test the two nearest related features to make sure nothing else broke. Regressions from bug fixes are the most common source of new bugs.

### Step 6: Document the Pattern

If this bug was caused by a pattern that could recur, add it to `tasks/lessons.md` immediately. Write the lesson as a rule, not a story: "Always wrap JSON.parse in try/catch when reading from PropertiesService" — not "I had a bug where PropertiesService returned invalid JSON."

---

## Verification Before Done

Never mark a task complete without proving it works. This is non-negotiable.

- **Run it.** Execute the code. Do not just read it and decide it looks correct.
- **Test the unhappy path first.** Pass null. Pass undefined. Pass an empty string. Click the button twice fast. Submit the form with missing fields. If the unhappy paths work, the happy path almost always works too.
- **Test with realistic data volumes.** If it works with 3 items, does it work with 300? Does it work with 0?
- **Diff your changes.** Review every modified line. Check for: accidental deletions, leftover debug code, inconsistent naming, missing error handling, broken imports. If the diff is larger than expected, investigate before proceeding.
- **Check downstream.** If you changed a data format, what else reads that data? If you changed a function signature, what else calls that function? Update everything in one commit.
- **Ask yourself: "Would a staff engineer approve this?"** If the answer is "probably, with caveats," fix the caveats first.

---

## Anticipate the Next Problem

After building anything, ask these questions before presenting the work:

1. **What breaks if the user's Mac is off?** What breaks if they are on their phone? What breaks if they share this with someone who has never seen it?
2. **What is the obvious next question Max will ask?** Answer it in the same message.
3. **What did you build that only works halfway?** If a scraper returns 0 results, if an automation resolves but does not scan, if a form saves but does not validate — flag the gap immediately and offer to close it.
4. **What dependencies does this have?** Surface ALL of them in one list: tokens, API keys, services that need to be running, environment variables, OS-specific requirements.
5. **Think two steps ahead.** If you change a data format, what else reads that data? If you add a new tool, what happens when the user has 50 items instead of 5?

Propose the fix in the same message. Do not wait for Max to connect the dots.

---

## Shipping and Deployment Discipline

### Before Every Deploy

1. Verify the build completes without errors or new warnings.
2. Test in the actual target environment, not just local dev. GAS in the Apps Script editor. Netlify via deploy preview. Vite via `npm run build && npm run preview`.
3. Check that environment variables, API keys, and secrets are set in the deploy target — not just in your local .env.
4. If deploying a site or app that Max shows to other people (portfolio, pitch site, demo), test on mobile. Load it on a phone-sized viewport. If it does not look right at 375px wide, it is not ready.

### After Every Deploy

1. Hit the live URL. Verify the change is actually there (caching can hide it).
2. Open the browser console. Check for errors.
3. Test the primary user flow end-to-end. Not a unit test — the actual thing a human does.
4. If the deploy broke something, roll back immediately. Debug from the rolled-back state, not from the broken live state.

### Version Control Hygiene

- Commit messages follow the format: `[scope] what changed` with a body explaining why and what could regress.
- Never commit secrets, API keys, tokens, or .env files. Use .gitignore aggressively.
- If a file is over 100KB or binary, question whether it belongs in the repo.
- Every project has a .gitignore from day one. Not after the first accidental commit of node_modules.

---

## Performance and UX Standards

These apply to every app and site Max ships, whether portfolio piece or production tool.

### Loading and Perceived Speed

- Every async operation shows a loading indicator. No blank screens while data loads.
- If a network request takes more than 300ms, show a skeleton or spinner. If it takes more than 3 seconds, show a progress message that explains what is happening.
- Lazy load heavy components and images. Do not make the user download 2MB of JavaScript for a page they can see in 200KB.
- Never block the main thread with synchronous computation. If processing takes more than 50ms, use requestAnimationFrame, Web Workers, or chunked processing.

### Error States as First-Class UI

- Every screen that loads data must handle three states: loading, success, and error. If any of these three is missing, the feature is not done.
- Error messages must be human-readable. "Failed to load" is not enough. "Could not load your lessons. Check your internet connection and try again." is minimum.
- Failed actions should be recoverable. If a form submission fails, the form should still contain the user's input so they do not have to retype it.

### Responsive Design Is Not Optional

- Every page and component works at 375px (phone), 768px (tablet), and 1440px (desktop) minimum.
- Touch targets are at least 44px by 44px on mobile.
- Text is readable without zooming on mobile (minimum 16px base font).
- Horizontal scrolling on mobile is a bug, not a design choice.
- Test with actual device emulation, not just a resized browser window.

### Accessibility Baseline

- All images have alt text. Decorative images use `alt=""`.
- All form inputs have associated labels (not just placeholder text).
- Color is never the only way to convey information (add text or icons).
- Interactive elements are keyboard-navigable (Tab, Enter, Escape).
- Contrast ratio meets WCAG AA minimum (4.5:1 for normal text).

---

## Portfolio and Demo Quality Standards

For any project that goes in the portfolio, on a pitch site, or gets shown to a potential employer or client:

### First Impression Test

Open the project cold. No context, no explanation. Within 5 seconds, can you tell: what this does, who it is for, and how to start using it? If not, the landing state needs work.

### The Bar Test

Imagine Max opening this on his phone at a bar with friends. Does it make sense? Can he show it off? Does it work without explanation? Does it load fast on a cell connection? If the answer to any of these is no, it is not demo-ready.

### Polish Checklist

- [ ] Favicon is set (not the default Vite/React icon)
- [ ] Page title is descriptive (not "Vite + React" or "index")
- [ ] No placeholder text or Lorem ipsum visible anywhere
- [ ] No console errors or warnings in production
- [ ] Loading states look intentional, not broken
- [ ] Empty states have helpful messaging (not a blank screen)
- [ ] The app works with no data (first-run experience is clean)
- [ ] All links work. No dead 404 links.
- [ ] If there is a dark mode toggle, both modes look complete
- [ ] Meta tags are set (title, description, og:image for link previews)

### README Standard

Every portfolio project has a README that includes:

- One-sentence description of what it does
- Screenshot or GIF of the app in use
- Tech stack listed clearly
- How to run it locally (if applicable)
- What problem it solves and for whom

The README is the first thing a hiring manager reads. It should take 30 seconds to understand the project.

---

## API and Data Handling

### External API Calls

- Always set timeouts. Default timeout of 10 seconds for any external API call. Do not let a slow third-party service hang your app indefinitely.
- Cache responses when the data does not change frequently. Even a 60-second cache prevents hammering an API during development.
- Handle rate limits gracefully. Implement exponential backoff with jitter. Max 3 retries.
- Never trust the shape of an API response. Validate the structure before accessing nested properties. APIs change without notice.

### Data Persistence

- If data matters, it needs a backup path. LocalStorage can be cleared by the user. Browser state disappears on refresh unless you save it. PropertiesService has a 9KB limit per value.
- Validate data before saving AND after loading. Data can get corrupted between the write and the read.
- When reading stored data, always wrap JSON.parse in try/catch. Corrupted storage should not crash the entire app.
- Design data schemas with future changes in mind. Include a version field. When you add new fields, handle the case where old data does not have them.

```javascript
// GOOD — versioned, defensive loading
function loadSettings() {
  try {
    const raw = localStorage.getItem('settings');
    if (!raw) return getDefaultSettings();
    const parsed = JSON.parse(raw);
    // Handle old schema versions
    if (!parsed.version || parsed.version < 2) {
      return migrateV1toV2(parsed);
    }
    return parsed;
  } catch (error) {
    console.error('[loadSettings] corrupt data, resetting', error);
    return getDefaultSettings();
  }
}
```

### Secrets and Credentials

- Never hardcode API keys, tokens, or secrets in source code. Use environment variables.
- Never commit .env files. Add .env to .gitignore on project creation, before the first commit.
- For client-side apps, understand that any key shipped to the browser is visible to users. If the key must stay secret, route through a server or serverless function.
- Rotate any key that was accidentally committed, even if you force-pushed to remove it. Git history retains it.

---

## Elegance Check (When to Apply It)

**Skip this for**: one-line changes, typo corrections, clear bug patches, anything where the correct fix is obvious.

**Apply this for**: new features, architectural decisions, data model changes, anything that will be built on top of later. Before presenting the work, ask:

- "Is there a simpler way to achieve the same result with fewer moving parts?"
- "Will this be obvious to read in three months?"
- "Am I introducing a new pattern when an existing one would work?"

If a fix feels hacky and it touches code that will be modified again soon, flag it: "This works but it is not elegant. Here is what the cleaner version would look like and what it would take to get there." Let Max decide whether to invest the time. Do not over-engineer unprompted.

---

## Self-Improvement Loop

After ANY correction from Max — whether a bug report, a "this is clunky," a screenshot of something broken, or a request to redo something — immediately:

1. **Do not defend.** Fix it.
2. **Identify the pattern.** Was this a failure of planning, verification, assumption, or execution?
3. **Write a rule in `tasks/lessons.md`** that would have prevented this specific mistake. Format: `[Date] [Project] Rule: <actionable instruction>`. Example: `[2026-03-19] [Chalk] Rule: Always test GAS functions with empty PropertiesService values before deploying.`
4. **Check if this pattern appears elsewhere** in the current project. Fix all instances, not just the one Max noticed.

Complaints are more valuable than compliments. When Max says "this is clunky" or "hmm" or sends a screenshot of something broken — that is the real feedback. The goal is to drive the mistake rate to zero by accumulating specific, actionable rules.

---

## Autonomous Execution

When Max gives a goal, propose the full system — do not build half and wait for him to notice what is missing. When given a bug report, fix it without hand-holding: point at logs, errors, failing tests, then resolve them. Zero context switching required from Max.

The method for autonomous bug fixing:

1. Read the error or bug report.
2. Locate the relevant code and logs.
3. Follow the Debugging Protocol (reproduce, isolate, root cause, fix narrowly, verify).
4. Present: what the bug was, what caused it, what you changed, and how you verified it.
5. If the fix has any risk of side effects, name them.

Do not ask Max "where should I look?" or "can you paste the error?" Find it yourself. That is what autonomous means.

But: pay attention to Max. When he enters a prompt, stop what you are doing and respond to it. Do not continue a background task when he is trying to redirect.

---

## Stack-Specific Rules

### React / Vite

- **Keys in lists**: Stable, unique keys only. Never array index as key if the list can be reordered or modified.
- **useEffect cleanup**: Every useEffect that subscribes, listens, or starts a timer MUST return a cleanup function.
- **Derived state**: If a value can be computed from props or other state, compute it during render. Do not duplicate it into separate state.
- **Conditional hooks**: Never call hooks inside conditions, loops, or nested functions.
- **Fetch in useEffect**: Always handle the unmounted-before-resolved case.

```javascript
useEffect(() => {
  let cancelled = false;
  async function load() {
    const data = await fetchData(id);
    if (!cancelled) setData(data);
  }
  load();
  return () => { cancelled = true; };
}, [id]);
```

- **Build before deploying**: Run `npm run build` locally and fix any warnings or errors before pushing to deploy. Do not discover build failures in production.
- **Import hygiene**: Remove unused imports. They create confusion and can cause bundle bloat.

### Google Apps Script (GAS)

- **Server/client boundary**: google.script.run is async and returns nothing directly. Always use withSuccessHandler and withFailureHandler.
- **HtmlService limitations**: No ES modules. No import/export. No top-level await. Single HTML file uses script tags and global scope or IIFEs.
- **PropertiesService limits**: Strings only, 9KB per value. JSON.stringify before storing, JSON.parse after retrieving. Always wrap parse in try/catch.
- **Execution time limits**: 6 minutes for simple triggers, 30 minutes for installable. Implement batch processing with continuation tokens for long operations.
- **HTML template pitfalls**: `<?= ?>` auto-escapes HTML. Use `<?!= ?>` for raw output (and sanitize inputs yourself).
- **Token expiration**: ScriptApp.getOAuthToken() tokens expire. Never cache across function calls.
- **Deployment gotcha**: After `clasp push`, you must create a new deployment or update the existing one for changes to appear at the deployed URL. Pushing alone does not update the live version.

### Claude API / AI Integrations

- **Always set max_tokens explicitly.** Never rely on defaults.
- **Parse responses defensively.** Check for the content array, iterate to find text blocks, handle tool_use blocks separately.
- **Rate limits**: Exponential backoff with jitter. Do not retry immediately. Max 3 retries.
- **Prompt injection defense**: Never interpolate raw user input into system prompts. Wrap user content in delimiters and instruct the model to treat it as data.
- **Cost awareness**: Log token usage. Large prompts with long system instructions burn through credits fast. Monitor and optimize prompt length when costs grow.

### CSS / Tailwind

- **Specificity conflicts**: Use browser dev tools, not guesswork.
- **Responsive**: Test at 375px, 768px, 1440px minimum.
- **Dark mode**: Every color utility needs a dark: variant or it will look broken.
- **Z-index**: Define a scale in one place. No arbitrary z-index values scattered across components.
- **Tailwind purge**: Ensure your Tailwind config scans all files that use Tailwind classes. Missing a directory means missing styles in production.

### Netlify / Static Deploys

- **Build command and publish directory** must be set correctly. Vite builds to `dist/`, not `build/`.
- **Redirects for SPAs**: If using client-side routing (React Router), add a `_redirects` file: `/* /index.html 200`. Without this, direct URL access returns 404.
- **Environment variables**: Set in Netlify dashboard, not in committed files. Prefix with `VITE_` for Vite projects so they are available client-side.
- **Deploy previews**: Use them. Every PR or branch gets a preview URL. Test there before merging to main.

---

## Code Review Checklist (Before Declaring "Done")

- [ ] No console.log debugging left in production code (structured logs are fine)
- [ ] All new functions have error handling
- [ ] All async functions have try/catch or .catch()
- [ ] No hardcoded secrets, keys, or tokens
- [ ] All user-facing strings handle empty/null/undefined gracefully
- [ ] Array operations handle empty arrays (accessing [0] on [] is a crash)
- [ ] New state variables are initialized with sensible defaults
- [ ] Loading, error, and empty states are handled in the UI
- [ ] The change works with no data, one item, and many items
- [ ] No circular dependencies introduced
- [ ] Imports resolve correctly (no typos in paths, no missing extensions)
- [ ] Downstream consumers of any changed function/data are updated
- [ ] No leftover debug code, TODO comments, or commented-out blocks
- [ ] Mobile viewport tested if the change touches UI
- [ ] Build completes without new warnings

---

## Anti-Patterns to Flag Immediately

| Anti-Pattern | Why It Is Dangerous | Fix |
|---|---|---|
| `catch (e) {}` | Silent failure hides bugs | Log and handle or re-throw |
| `any` type in TS | Defeats the type system | Use proper types or `unknown` |
| `eslint-disable` without comment | Hides real problems | Fix the underlying issue |
| `// TODO: fix later` | It never gets fixed later | Fix now or file an issue |
| `setTimeout` for timing | Fragile, non-deterministic | Proper async coordination |
| Copy-pasted code blocks | Maintenance nightmare | Extract shared function |
| Magic numbers | Unreadable, error-prone | Named constants |
| Nested ternaries | Unreadable | if/else or early returns |
| Mutating function arguments | Spooky action at a distance | Clone, then modify |
| Shipping broken code and moving on | Compounds into system rot | Fix before calling done |
| No loading state for async UI | Looks broken to the user | Always show loading/error/empty |
| Hardcoded strings in components | Maintenance and i18n nightmare | Extract to constants or config |

---

## When You Are Stuck

If a bug resists diagnosis after 15 minutes of focused effort:

1. **Write down everything you know.** What works. What does not. What you have tried.
2. **Check your assumptions.** Add a log and verify. Do not trust your mental model.
3. **Reduce the problem.** Remove components one at a time until you find the one that matters.
4. **Explain it out loud.** Describe the bug as if teaching someone.
5. **Check the boring causes first.** Typos. Wrong variable name. Stale cache. Wrong file. Wrong branch. Import from wrong module. These account for more bugs than clever logic errors.
6. **Search for the exact error message.** Do not paraphrase — search the exact string.

---

## File Modification Safety (Large Files)

For files over 500 lines:

1. Re-read the target section immediately before editing. Earlier reads may be stale.
2. Use unique, specific search strings for targeted edits. Generic patterns match multiple locations.
3. Verify after editing by reading the modified section. Confirm the change landed correctly.
4. One edit at a time. Make an edit, verify, then proceed. Do not batch and hope.

---

## Project Setup Checklist (New Projects)

When starting any new project from scratch:

- [ ] Initialize git repo with .gitignore before first code
- [ ] .gitignore includes: node_modules, .env, dist/build, .DS_Store, *.log
- [ ] Create `tasks/todo.md` and `tasks/lessons.md`
- [ ] Set up linter/formatter (ESLint + Prettier or equivalent)
- [ ] Create a README with: one-line description, tech stack, how to run
- [ ] If deploying: verify build command and deploy target work before writing features
- [ ] If using APIs: set up environment variable handling from the start
- [ ] If portfolio piece: set favicon, page title, and meta tags on day one

---

## Project-Specific Appendix Pattern

This CLAUDE.md is universal. For project-specific rules, create a `PROJECT_RULES.md` in the project root with:

```markdown
# PROJECT_RULES.md — [Project Name]

## Key Files
- [list the 3-5 most important files and what they do]

## Data Shapes
- [document the main data structures the app works with]

## Known Gotchas
- [list project-specific traps from tasks/lessons.md]

## Deploy Process
- [exact steps to ship a new version]
```

Keep this file under 50 lines. If it grows larger, the project's architecture needs simplifying, not more documentation.

---

## Core Principles (Always Active)

- **Simplicity first.** Make every change as simple as possible. Touch minimal code.
- **Find root causes.** No temporary fixes. No "this works but I do not know why." Senior developer standards.
- **Minimal blast radius.** Changes should only touch what is necessary. Avoid introducing new bugs while fixing old ones.
- **Build complete systems.** Max gives the goal. Claude proposes and builds the full solution — not half of one.
- **Respect Max's attention.** When he enters a prompt, stop and respond. Do not continue background work when he is trying to redirect. Do not ask leading questions. Observe friction and fix it before he hits it.
- **Ship quality.** Every project Max shows someone is a reflection of his judgment. Broken demos, placeholder text, and console errors are not acceptable. If it is not ready to show, say so.