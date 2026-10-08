# Contributing

1. Create a branch from `main` and describe the intended change.
2. For strategy changes, name the old/new rule, information cutoff, evaluation version and data needed. Keep prospective trials distinct.
3. Keep private data and credentials out of the patch. Use synthetic fixtures for shared tests.
4. Run `python scripts/validate_portable.py`. Report omitted historical checks honestly.
5. Open a pull request with the problem, resulting behavior, tests and material limitations. Passing CI is not permission to enable trading.

Do not silently update strategy versions, approve your own policy exceptions or publish copier notes. The reference schemas and trading mandate require their own recorded acceptance.
