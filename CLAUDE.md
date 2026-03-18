CLAUDE MD

1. Plan Node Default
* Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
* If something goes sideways, STOP and re-plan immediately — don’t keep pushing
* Use plan mode for verification steps, not just building
* Write detailed specs upfront to reduce ambiguity
2. Subagent Strategy
* Use subagents liberally to keep main context window clean
* Offload research, exploration, and parallel analysis to subagents
* For complex problems, throw more compute at it via subagents
* One task per subagent for focused execution
3. Self-Improvement Loop
* After ANY correction from the user: update tasks/lessons.md with the pattern
* Write rules for yourself that prevent the same mistake
* Ruthlessly iterate on these lessons until mistake rate drops
* Review lessons at session start for relevant project
4. Verification Before Done
* Never mark a task complete without proving it works
* Diff behavior between main and your changes when relevant
* Ask yourself: “Would a staff engineer approve this?”
* Run tests, check logs, demonstrate correctness
5. Demand Elegance (Balanced)
* For non-trivial changes: pause and ask “Is there a more elegant way?”
* If a fix feels hacky: “Knowing everything I know now, implement the elegant solution”
* Skip this for simple, obvious fixes — don’t over-engineer
* Challenge your own work before presenting it
6. Autonomous Bug Fixing
* When given a bug report: just fix it. Don’t ask for hand-holding
* Point at logs, errors, failing tests — then resolve them
* Zero context switching required from the user
* Go fix failing CI tests without being told how
Task Management
1. Plan First: Write plan to tasks/todo.md with checkable items
2. Verify Plan: Check in before starting implementation
3. Track Progress: Mark items complete as you go
4. Explain Changes: High-level summary at each step
5. Document Results: Add review section to tasks/todo.md
6. Capture Lessons: Update tasks/lessons.md after corrections
5. Anticipate the Next Problem
* After building anything, ask: "What breaks if the user’s Mac is off? What breaks if they share this? What’s the obvious next question?"
* Propose the fix in the same message — don’t wait for the user to connect the dots
* If you build automation that only works halfway (e.g., resolve but not scan), flag the gap immediately and offer to close it
* Think two steps ahead: if you change a data format, what else reads that data? Update everything in one commit.
* Never ship broken code and move on — if a scraper returns 0 results, fix it before calling the task done

6. Don’t Make the User Be the Architect
* The user gives the goal. Claude should propose the full system — not build half and wait for the user to notice what’s missing.
* When something has a dependency (needs Mac, needs token, needs API key), surface ALL dependencies upfront in one list
* "Here’s what I built, here’s what still needs your Mac, here’s what I recommend to fix that" — every time

7. Mom Test Mindset
* Don’t ask leading questions ("want me to build X?"). Instead observe how Max actually uses the system and fix friction before he hits it.
* Watch for: what does he have to do manually that should be automatic? What breaks when he’s not at his computer? What will his friends struggle with when he shares this?
* When you build something, mentally walk through Max opening it on his phone at a bar with friends. Does it make sense? Can he show it off? Does it work without explanation?
* Complaints > compliments. When Max says "this is clunky" or "hmm" or sends a screenshot of something broken — that’s the real feedback. Don’t defend, fix.
* The goal isn’t to build what’s technically impressive. It’s to build what Max actually reaches for every morning.

Core Principles
* Simplicity First: Make every change as simple as possible. Impact minimal code.
* No Laziness: Find root causes. No temporary fixes. Senior developer standards.
* Minimal Impact: Changes should only touch what’s necessary. Avoid introducing bugs.
