# Five-minute research-agent demo

**Session 2: Thursday 15 October 2026.** Rehearsal plan, not evidence that the homework is complete. Read [the homework checklist](HOMEWORK_CHECKLIST_2026-10-09.md) first.

Use a clean checkout at a recorded commit. Have safe source/configuration identities and generated output ready. Keep private vendor files, account identifiers and credentials off screen. Demonstrate only what actually runs; explicitly identify missing pieces.

| Time | Show | Say or verify |
| --- | --- | --- |
| 0:00-0:30 | One-sentence hypothesis and strategy scope | Draft for owner review: prior-session directional flow corroborated by research, Hidden Angles and TA predicts positive net close-to-next-open stock returns above an exposure-matched benchmark because information-driven repricing persists overnight. This is unproven. Identify the separately evaluated earnings sleeve. |
| 0:30-2:00 | Clean-checkout regeneration command and matching specification figures | Use the genuine daily rebuild only when implemented. Today, `python scripts/validate_portable.py` demonstrates software checks and synthetic fixtures; clearly say it does **not** regenerate the missing daily Sharpe, turnover, break-even or deflated Sharpe figures. Do not relabel this as completed homework. |
| 2:00-3:00 | Trial log and counts | Show every actual run, baseline identity, single change, period and required metrics once connected. The existing protocol can demonstrate attempt retention using synthetic events. Do not call synthetic fixture counts genuine strategy trials. If no genuine unrequested run exists, say so; do not create one solely for the presentation. |
| 3:00-4:00 | Real-loader continuation through one added year | When built, show the extension's delisting/halt rows, new-period output and the sign-off hook. At present state the gap honestly: the daily continuation test is not implemented; future-extension metadata is not a substitute. |
| 4:00-4:40 | One actual mistake and how it was caught | Choose a documented error with a visible correction. One available example is the earlier belief that Task 1 required an external reference schema: the supplied homework instead asks us to design our own validator and preserve its field names. Show this checklist and the actual corrected documentation after it is committed. Do not invent a trade or an agent error. |
| 4:40-5:00 | Verified facts, unresolved items and signature status | Separate tested software behavior from economic evidence. State whether the owner actually reproduced the figures, whether the specification is genuinely signed and whether the untouched holdout has been opened. Leave all three unclaimed until evidence exists. |

## Before rehearsing

- [ ] Freeze the exact demo commit and identify which command is an economic rebuild versus a software check.
- [ ] Check that every displayed figure comes from the recorded run and agrees with the specification.
- [ ] Show the complete trial accounting, including unsuccessful and unviewed runs, without exposing private data.
- [ ] Confirm the continuation uses the real loader and records new-period output before claiming it passes.
- [ ] Keep the specification unsigned until the owner completes the required verification. Preserve the first holdout-opening chronology.
- [ ] Rehearse with a clock; record the actual duration.
- [ ] Have the owner send the repository link to the programme contact before Session 2. This document does not send it.

If the required daily study remains incomplete, present an honest progress demo and request guidance on the specific data or implementation gap. Passing shadow operating tests or adding the top three improvements does not make research results complete.
