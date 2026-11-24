# Environments and promotion routine

## The three environments

| Environment | Database | Where | Selected by |
|---|---|---|---|
| Dev | bank_dev | local server | default (APP_ENV not set) |
| Test | bank_test | cloud server (Aiven) | APP_ENV=test |
| Prod | bank_prod | cloud server (Aiven) | APP_ENV=prod |

Settings live in `.env.dev`, `.env.test` and `.env.prod`. These files are git-ignored and never committed, pasted into issues or shared in chat. `.env.example` documents the settings with placeholder values only.

## Promotion routine

1. **Dev:** build and test on a feature branch with APP_ENV unset.
2. **Review:** open a pull request, review the Files changed tab, merge into `main`.
3. **Test:** switch to `main` and run the scripts with `APP_ENV=test`. The first line printed must say `Connected to test database bank_test`.
4. **Verify Test:** every script prints SUCCESS, ingestion_audit shows only SUCCESS rows for this run, and `docs/compare_environments.sql` gives the same counts and fingerprints in Test and in Dev.
5. **Prod:** only after step 4 passes, run the same scripts with `APP_ENV=prod`. The first line printed must say `Connected to prod database bank_prod`.
6. **Verify Prod:** repeat the checks from step 4 against Prod.
7. **Record:** post the commands and results as a comment on the issue.

## Rules

- Never run scripts against Prod from a feature branch; Prod only runs code that is merged into `main`.
- Never change Prod data by hand; Prod changes go through the scripts.
- Never run Prod before Test has passed.
- Always clear the setting afterwards with `Remove-Item Env:APP_ENV`, so the next command defaults to Dev.
- Read the first printed line before trusting a run: it names the environment.
- Credentials stay in the local `.env.*` files only, never in Git, comments or chat.
