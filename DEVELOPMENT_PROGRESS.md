# Development progress

## Current phase

Phases 1 through 7 are implemented. Backend pytest, frontend Vitest, TypeScript, and ESLint pass. The signed-in UI was exercised in the browser against the local SQLite API: sample upload, cleaning, overview KPIs, a region filter, a grounded assistant answer, report generation, and notifications.

Docker Compose has not been booted because Docker is not installed on this machine. Online Retail II is loaded in the local workspace: 1,067,371 raw rows, quality score 98.4, and a cleaned version with 1,067,366 KPI rows. The workbook stays in gitignored `data/uci`.

## Completed

- Authentication, workspaces, refresh-token rotation, and membership checks
- CSV and XLSX upload, raw file storage, profiling, column roles, preview, and deletion
- Cleaned version separate from the raw file, with returns and cancellations kept and invalid rows flagged
- Documented quality score and outlier report
- Generated sample dataset, labeled as a fixture rather than the UCI extract
- Sales, customer, and product analytics from the cleaned table, with date and filter controls
- K-means segmentation, inferred churn with logistic regression, random forest, and XGBoost, and a chronological forecast
- Churn ranks, with a count of customers who were too new to label
- Background jobs for cleaning, training, and the UCI import, polled from the UI
- Workspace invitations for existing accounts and for emails that have not registered yet
- Login rate limits stored in Redis when `REDIS_URL` is set
- Assistant plans that compile to a single read-only query, or quote a saved model
- PDF, Excel, and CSV reports
- Alembic revisions `001_auth_foundation`, `002_datasets`, and `003_jobs_and_invites`
- Pytest, Vitest, Playwright spec, and GitHub Actions workflow
- Browser check of the sample path, sales filter, assistant total, and executive report

## Pending

- Boot Docker Compose and confirm PostgreSQL, Redis, and the container health checks. Docker is not installed here
- Train segments, churn, and the forecast on the cleaned Online Retail II table. The import and clean are done; those models have only been trained on the sample
- A shared worker for more than one API process. Jobs currently run inside the API process
- SHAP values. The churn screen uses the selected model's own feature importance and says so

## Known bugs

- None confirmed in the flows exercised above.
- The first cleaned-version write on the SQLite file locked the database when it used a second connection. Writes now use the request connection. Pytest covers the pipeline on SQLite, and the browser clean succeeded after the change.
- XGBoost does not load on macOS until `libomp` is available. The churn run still returns logistic regression and random forest, and records the XGBoost load error.

## Next development tasks

1. Install Docker and run `docker compose up --build`.
2. Let the Online Retail II clean finish, then compare a KPI with a hand calculation on a small slice.
