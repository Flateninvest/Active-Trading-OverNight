# Contributing

## Propose and implement a change

1. Start from the latest `main` and create a short branch, for example `docs/reviewer-guide`, `feature/daily-research` or `fix/quote-age`.
2. Open an issue for work that needs discussion, using the project change form. For small fixes, the pull request can provide the change record.
3. Follow the [repository map](docs/REPOSITORY_MAP.md). Keep the weekly comparison in its existing folder; add future daily code in its own package when an implementation is ready.
4. Keep private data and credentials out of the patch. Use synthetic fixtures for shared tests and follow the [data policy](docs/DATA_POLICY.md).
5. Open a focused pull request describing the problem, resulting behavior, actual validation and remaining limitations. Link the issue if one exists. Review its final diff before merging.

## Keep the project consistent

| Change | Update together |
| --- | --- |
| Strategy rule, threshold, timing or universe | [Daily strategy](docs/DAILY_STRATEGY.md), [provisional specification](spec/strategy_spec.provisional.json), effective [complete prompt](prompts/README.md), applicable tests and approval record |
| Agent boundary or interface | [Architecture](docs/FOUR_COMPONENTS.md), specifications, implementation plan and affected instructions |
| New code or document | Relevant folder index, root links when useful, installation/run instructions if changed |
| Material project update | [CHANGELOG.md](CHANGELOG.md) with its date, scope and validation summary |

For strategy changes, state the old and new values, rationale, information cutoff, evaluation version and data needed. Keep daily, weekly and passive studies and prospective trials distinct. Update the standalone workshop addendum when its included section changes. Unresolved rule conflicts block reliance on the affected rule; review them explicitly.

Keep dated meeting PDFs and historical research as snapshots. Publish a new dated artifact when replacing one, preserve the previous version and update the relevant links. Do not rewrite old evidence as though it described the new design.

## Validate and merge

- Run `python scripts/validate_portable.py` for code or configuration changes. Its saved record identifies the checked commit; if relevant source is uncommitted it says so. Commit the code first, then record validation on that committed code in a separate commit when publishing new evidence.
- For documentation-only changes, check relative links, readability and consistency. GitHub still runs the portable check on the pull request.
- Report omitted historical checks honestly: those require separately supplied private datasets. Synthetic results do not establish profits or a completed daily runtime.
- Protected `main` requires a pull request, a passing `synthetic-checks` result on an up-to-date branch and resolved conversations. Force pushes and deletion are blocked, including for the owner.
- The owner can review and merge their own development pull requests. External approving reviews are not mandatory in this single-owner setup; CODEOWNERS identifies responsibility and does not grant access or enforce an approval by itself.
- Preserve the initial evaluation commit history when merging the baseline package so its validation record remains traceable. Use the appropriate merge method for later changes and preserve evidence provenance.

Readers should use the [sharing guide](docs/SHARING.md). A public viewer can suggest a change through an issue or a fork pull request; that does not give them write access to this repository.

Do not silently update strategy versions, approve your own policy exceptions or publish copier notes. The reference schemas and trading mandate require their own recorded acceptance.
